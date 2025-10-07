from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import DATERANGE
import csv
import io
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import pytz
from app.models import Creator, PerfUpload, ClickUnique, Insertion, ConvUpload, Conversion, Advertiser, Campaign
from app.db import get_db

router = APIRouter()


@router.get("/test-creator-lookup/{acct_id}")
async def test_creator_lookup(acct_id: str, db: Session = Depends(get_db)):
    """Test endpoint to check if creator lookup works"""
    creator = db.query(Creator).filter(Creator.acct_id == acct_id).first()
    if creator:
        return {
            "found": True,
            "creator_id": creator.creator_id,
            "name": creator.name,
            "acct_id": creator.acct_id
        }
    else:
        all_creators = db.query(Creator).all()
        return {
            "found": False,
            "searched_for": acct_id,
            "available_creators": [(c.creator_id, c.acct_id) for c in all_creators[:10]]
        }


@router.post("/test-csv-upload")
async def test_csv_upload(file: UploadFile = File(...)):
    """Test endpoint to see what CSV content is being received"""
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
        return {
            "filename": file.filename,
            "size": len(content),
            "content": csv_content,
            "content_repr": repr(csv_content),
            "lines": csv_content.split('\n'),
            "line_count": len(csv_content.split('\n'))
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/test-conversion-insert")
async def test_conversion_insert(
    advertiser_id: int = Query(..., description="Advertiser ID"),
    campaign_id: int = Query(..., description="Campaign ID"),
    insertion_id: int = Query(..., description="Insertion ID"),
    range_start: str = Query(..., description="Range start date (YYYY-MM-DD)"),
    range_end: str = Query(..., description="Range end date (YYYY-MM-DD)"),
    acct_id: str = Query(..., description="Account ID"),
    conversions: int = Query(..., description="Number of conversions"),
    db: Session = Depends(get_db)
):
    """Test endpoint to directly insert a conversion without CSV"""
    try:
        # Parse date range
        start_date = datetime.strptime(range_start, '%Y-%m-%d').date()
        end_date = datetime.strptime(range_end, '%Y-%m-%d').date()
        
        # Find or create creator
        creator = db.query(Creator).filter(Creator.acct_id == acct_id).first()
        if not creator:
            creator = Creator(
                name=f"Test Creator {acct_id}",
                acct_id=acct_id,
                owner_email=f"test{acct_id}@example.com",
                topic="Test",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(creator)
            db.flush()
        
        # Create conv_upload record
        conv_upload = ConvUpload(
            advertiser_id=advertiser_id,
            campaign_id=campaign_id,
            insertion_id=insertion_id,
            uploaded_at=datetime.utcnow(),
            filename="test.csv",
            range_start=start_date,
            range_end=end_date,
            tz="America/New_York"
        )
        db.add(conv_upload)
        db.flush()
        
        # Create conversion record
        period_range = DATERANGE(start_date, end_date, '[]')
        conversion = Conversion(
            conv_upload_id=conv_upload.conv_upload_id,
            insertion_id=insertion_id,
            creator_id=creator.creator_id,
            period=period_range,
            conversions=conversions
        )
        db.add(conversion)
        db.commit()
        
        return {
            "success": True,
            "conv_upload_id": conv_upload.conv_upload_id,
            "creator_id": creator.creator_id,
            "conversion_id": conversion.conversion_id
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e)}


def extract_email_from_creator(creator_field: str) -> Optional[str]:
    """
    Extract email from Creator field, supporting [mailto:...] markdown format.
    Returns the first email found, or None if no email is found.
    """
    if not creator_field:
        return None
    
    # Look for [mailto:email@domain.com] format first
    mailto_match = re.search(r'\[mailto:([^\]]+)\]', creator_field, re.IGNORECASE)
    if mailto_match:
        return mailto_match.group(1).strip().lower()
    
    # Look for email pattern in the field
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, creator_field)
    if email_match:
        return email_match.group(0).strip().lower()
    
    return None


def normalize_execution_date(date_str: str) -> Optional[date]:
    """
    Normalize execution date to DATE in America/New_York timezone.
    """
    if not date_str:
        return None
    
    try:
        # Try different date formats
        date_formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m-%d-%Y',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%Y/%m/%d'
        ]
        
        parsed_date = None
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str.strip(), fmt).date()
                break
            except ValueError:
                continue
        
        if parsed_date is None:
            return None
            
        # Convert to America/New_York timezone if needed
        ny_tz = pytz.timezone('America/New_York')
        # Create datetime at midnight in NY timezone
        dt = datetime.combine(parsed_date, datetime.min.time())
        dt_ny = ny_tz.localize(dt)
        
        return dt_ny.date()
        
    except Exception:
        return None


@router.post("/uploads/performance")
async def upload_performance_data(
    insertion_id: int = Query(..., description="Insertion ID for this performance data"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Upload performance CSV data for a specific insertion.
    Expected columns: Creator, Clicks, Unique, Flagged, Execution Date, Status
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    # Verify insertion exists
    insertion = db.query(Insertion).filter(Insertion.insertion_id == insertion_id).first()
    if not insertion:
        raise HTTPException(status_code=404, detail="Insertion not found")
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        inserted_rows = 0
        unmatched_count = 0
        unmatched_examples = []
        
        # Create perf_upload record
        perf_upload = PerfUpload(
            insertion_id=insertion_id,
            uploaded_at=datetime.utcnow(),
            filename=file.filename
        )
        db.add(perf_upload)
        db.flush()  # Get the ID without committing
        
        for row in csv_reader:
            try:
                # Extract data from CSV row
                creator_field = row.get('Creator', '').strip()
                clicks_str = row.get('Clicks', '').strip()
                unique_str = row.get('Unique', '').strip()
                flagged_str = row.get('Flagged', '').strip()
                execution_date_str = row.get('Execution Date', '').strip()
                status = row.get('Status', '').strip()
                
                # Skip rows with missing required fields
                if not creator_field or not unique_str or not execution_date_str:
                    continue
                
                # Extract email from creator field
                creator_email = extract_email_from_creator(creator_field)
                if not creator_email:
                    unmatched_count += 1
                    unmatched_examples.append(creator_field[:50])  # First 50 chars
                    continue
                
                # Find creator by email
                creator = db.query(Creator).filter(
                    func.lower(Creator.owner_email) == creator_email
                ).first()
                
                if not creator:
                    unmatched_count += 1
                    unmatched_examples.append(f"{creator_field[:30]} -> {creator_email}")
                    continue
                
                # Parse numeric values
                try:
                    unique_clicks = int(unique_str) if unique_str else 0
                    raw_clicks = int(clicks_str) if clicks_str else None
                except ValueError:
                    continue
                
                # Parse flagged as boolean
                flagged = None
                if flagged_str.lower() in ['true', '1', 'yes', 'y']:
                    flagged = True
                elif flagged_str.lower() in ['false', '0', 'no', 'n']:
                    flagged = False
                
                # Normalize execution date
                execution_date = normalize_execution_date(execution_date_str)
                if not execution_date:
                    continue
                
                # Create click_unique record
                click_unique = ClickUnique(
                    perf_upload_id=perf_upload.perf_upload_id,
                    creator_id=creator.creator_id,
                    execution_date=execution_date,
                    unique_clicks=unique_clicks,
                    raw_clicks=raw_clicks,
                    flagged=flagged,
                    status=status if status else None
                )
                db.add(click_unique)
                inserted_rows += 1
                
            except Exception as e:
                # Skip rows that cause errors
                continue
        
        # Commit all changes
        db.commit()
        
        # Limit unmatched examples to first 10
        unmatched_examples = unmatched_examples[:10]
        
        return {
            "perf_upload_id": perf_upload.perf_upload_id,
            "inserted_rows": inserted_rows,
            "unmatched_count": unmatched_count,
            "unmatched_examples": unmatched_examples
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")


@router.post("/uploads/conversions")
async def upload_conversions_data(
    advertiser_id: int = Query(..., description="Advertiser ID"),
    campaign_id: int = Query(..., description="Campaign ID"),
    insertion_id: int = Query(..., description="Insertion ID"),
    range_start: str = Query(..., description="Range start date (YYYY-MM-DD)"),
    range_end: str = Query(..., description="Range end date (YYYY-MM-DD)"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Upload conversions CSV data for a specific insertion.
    Expected columns: Acct Id, Conversions
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    # Parse date range
    try:
        start_date = datetime.strptime(range_start, '%Y-%m-%d').date()
        end_date = datetime.strptime(range_end, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Verify entities exist
    advertiser = db.query(Advertiser).filter(Advertiser.advertiser_id == advertiser_id).first()
    if not advertiser:
        raise HTTPException(status_code=404, detail="Advertiser not found")
    
    campaign = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    insertion = db.query(Insertion).filter(Insertion.insertion_id == insertion_id).first()
    if not insertion:
        raise HTTPException(status_code=404, detail="Insertion not found")
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        logging.info(f"DEBUG: CSV content length: {len(csv_content)}")
        logging.info(f"DEBUG: CSV content: {repr(csv_content)}")  # Use repr to show hidden characters
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        logging.info(f"DEBUG: CSV fieldnames: {csv_reader.fieldnames}")
        
        # Check if CSV has any rows at all
        csv_rows = list(csv_reader)
        logging.info(f"DEBUG: Total CSV rows found: {len(csv_rows)}")
        for i, row in enumerate(csv_rows):
            logging.info(f"DEBUG: Row {i}: {row}")
        
        replaced_rows = 0
        inserted_rows = 0
        total_csv_rows = 0
        
        # Create conv_upload record
        conv_upload = ConvUpload(
            advertiser_id=advertiser_id,
            campaign_id=campaign_id,
            insertion_id=insertion_id,
            uploaded_at=datetime.utcnow(),
            filename=file.filename,
            range_start=start_date,
            range_end=end_date,
            tz="America/New_York"
        )
        db.add(conv_upload)
        db.flush()  # Get the ID without committing
        
        # Process each row in the CSV
        logging.info(f"DEBUG: Starting CSV processing with {len(csv_rows)} rows")
        for row in csv_rows:
            total_csv_rows += 1
            logging.info(f"DEBUG: Processing row {total_csv_rows}: {row}")
            try:
                # Map CSV column names to database field names
                acct_id = row.get('Acct Id', '').strip()
                conversions_str = row.get('Conversions', '').strip()
                
                logging.info(f"DEBUG: Processing row - acct_id: '{acct_id}', conversions_str: '{conversions_str}'")
                logging.info(f"DEBUG: CSV row keys: {list(row.keys())}")
                logging.info(f"DEBUG: CSV row values: {list(row.values())}")
                
                # Skip rows with missing required fields
                if not acct_id or not conversions_str:
                    logging.info(f"DEBUG: Skipping row - missing fields. acct_id: '{acct_id}', conversions_str: '{conversions_str}'")
                    continue
                
                # Skip header rows (where acct_id is the column name)
                if acct_id == 'Acct Id':
                    logging.info(f"DEBUG: Skipping header row")
                    continue
                
                # Force both IDs to be strings and trimmed for comparison
                acct_id_clean = str(acct_id).strip()
                
                # Try exact match first
                creator = db.query(Creator).filter(Creator.acct_id == acct_id_clean).first()
                
                # If not found, try LIKE match (in case of hidden characters)
                if not creator:
                    creator = db.query(Creator).filter(Creator.acct_id.like(f'%{acct_id_clean}%')).first()
                
                # If still not found, try case-insensitive match
                if not creator:
                    creator = db.query(Creator).filter(func.lower(Creator.acct_id) == acct_id_clean.lower()).first()
                if not creator:
                    logging.info(f"DEBUG: Creator not found for acct_id: '{acct_id}' (type: {type(acct_id)})")
                    # Let's also check what creators exist
                    all_creators = db.query(Creator).all()
                    logging.info(f"DEBUG: Available creators: {[(c.creator_id, c.acct_id, type(c.acct_id)) for c in all_creators[:5]]}")
                    
                    # NUCLEAR OPTION: Create the creator if it doesn't exist
                    logging.info(f"DEBUG: Creating new creator with acct_id: '{acct_id_clean}'")
                    creator = Creator(
                        name=f"Creator {acct_id_clean}",
                        acct_id=acct_id_clean,
                        owner_email=f"creator{acct_id_clean}@example.com",
                        topic="Auto-created",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(creator)
                    db.flush()  # Get the ID
                    logging.info(f"DEBUG: Created creator {creator.creator_id} for acct_id: '{acct_id_clean}'")
                else:
                    logging.info(f"DEBUG: Found creator {creator.creator_id} for acct_id: '{acct_id}' (type: {type(acct_id)})")
                
                # Parse conversions count
                try:
                    conversions = int(conversions_str)
                except ValueError:
                    continue
                
                # Create daterange for the period
                period_range = DATERANGE(start_date, end_date, '[]')
                
                # Delete existing conversions for this creator/insertion/period overlap
                delete_query = text("""
                    DELETE FROM conversions 
                    WHERE creator_id = :creator_id 
                    AND insertion_id = :insertion_id 
                    AND period && :period_range
                """)
                
                result = db.execute(delete_query, {
                    'creator_id': creator.creator_id,
                    'insertion_id': insertion_id,
                    'period_range': period_range
                })
                replaced_rows += result.rowcount
                
                # Insert new conversion record
                conversion = Conversion(
                    conv_upload_id=conv_upload.conv_upload_id,
                    insertion_id=insertion_id,
                    creator_id=creator.creator_id,
                    period=period_range,
                    conversions=conversions
                )
                db.add(conversion)
                inserted_rows += 1
                
            except Exception as e:
                # Skip rows that cause errors
                continue
        
        # Commit all changes
        db.commit()
        
        return {
            "conv_upload_id": conv_upload.conv_upload_id,
            "replaced_rows": replaced_rows,
            "inserted_rows": inserted_rows,
            "debug_info": {
                "csv_content_length": len(csv_content),
                "csv_fieldnames": csv_reader.fieldnames,
                "total_csv_rows": total_csv_rows,
                "processed_rows": replaced_rows + inserted_rows,
                "csv_preview": csv_content[:200] if csv_content else "No content"
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
