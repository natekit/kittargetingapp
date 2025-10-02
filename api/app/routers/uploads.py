from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
import csv
import io
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import pytz
from app.models import Creator, PerfUpload, ClickUnique, Insertion
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
