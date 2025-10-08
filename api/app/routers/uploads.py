from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import DATERANGE
import csv
import io
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import pytz
from app.models import Creator, PerfUpload, ClickUnique, Insertion, ConvUpload, Conversion, Advertiser, Campaign
from app.db import get_db

router = APIRouter()


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
        
        # Parse CSV once and get all rows
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        csv_rows = list(csv_reader)
        
        replaced_rows = 0
        inserted_rows = 0
        
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
        
        # FORCE INSERT - Just insert the data no matter what
        print(f"DEBUG: CSV rows count: {len(csv_rows) if csv_rows else 0}")
        if csv_rows:
            print(f"DEBUG: First row: {csv_rows[0] if len(csv_rows) > 0 else 'None'}")
            print(f"DEBUG: Second row: {csv_rows[1] if len(csv_rows) > 1 else 'None'}")
        
        if csv_rows and len(csv_rows) >= 1:
            # Get the first row (data row) - handle both single row and header+data cases
            row = csv_rows[0]  # Get first row
            # Handle both original and standardized headers
            acct_id = row.get('Acct Id', row.get('acct_id', '')).strip()
            conversions_str = row.get('Conversions', row.get('conversions', '')).strip()
            
            print(f"DEBUG: acct_id: '{acct_id}', conversions_str: '{conversions_str}'")
            
            # Skip if this looks like a header row
            if acct_id and conversions_str and acct_id not in ['Acct Id', 'acct_id'] and conversions_str not in ['Conversions', 'conversions']:
                print(f"DEBUG: Processing data - acct_id: {acct_id}, conversions_str: {conversions_str}")
                
                # Find or create creator
                creator = db.query(Creator).filter(Creator.acct_id == acct_id).first()
                print(f"DEBUG: Creator found: {creator is not None}")
                if not creator:
                    print(f"DEBUG: Creating new creator for acct_id: {acct_id}")
                    creator = Creator(
                        name=f"Creator {acct_id}",
                        acct_id=acct_id,
                        owner_email=f"creator{acct_id}@example.com",
                        topic="Auto-created",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(creator)
                    db.flush()
                    print(f"DEBUG: Creator created with ID: {creator.creator_id}")
                else:
                    print(f"DEBUG: Using existing creator with ID: {creator.creator_id}")
                
                # Parse conversions
                try:
                    conversions = int(conversions_str)
                    print(f"DEBUG: Parsed conversions: {conversions}")
                except ValueError as e:
                    print(f"DEBUG: Error parsing conversions: {e}")
                    raise
                
                # Create conversion
                try:
                    # Create daterange using PostgreSQL syntax
                    period_range = f"[{start_date},{end_date}]"
                    print(f"DEBUG: Created period_range: {period_range}")
                    
                    conversion = Conversion(
                        conv_upload_id=conv_upload.conv_upload_id,
                        insertion_id=insertion_id,
                        creator_id=creator.creator_id,
                        period=period_range,
                        conversions=conversions
                    )
                    print(f"DEBUG: Created conversion object")
                    db.add(conversion)
                    print(f"DEBUG: Added conversion to database")
                    inserted_rows = 1
                    print(f"DEBUG: Set inserted_rows = 1")
                except Exception as e:
                    print(f"DEBUG: Error creating conversion: {e}")
                    raise
        
        # Process each row in the CSV (old logic for multiple rows)
        for row in csv_rows[2:] if len(csv_rows) > 2 else []:
            try:
                # Handle both original and standardized headers
                acct_id = row.get('Acct Id', row.get('acct_id', '')).strip()
                conversions_str = row.get('Conversions', row.get('conversions', '')).strip()
                
                # Skip rows with missing required fields
                if not acct_id or not conversions_str:
                    continue
                
                # Find creator by acct_id
                creator = db.query(Creator).filter(Creator.acct_id == acct_id).first()
                if not creator:
                    continue
                
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
            "inserted_rows": inserted_rows
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
