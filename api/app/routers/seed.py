from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
import csv
import io
from typing import Dict, Any
from app.models import Creator
from app.db import get_db
from datetime import datetime

router = APIRouter()


@router.post("/seed/creators")
async def seed_creators(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Dict[str, int]:
    """
    Seed creators from CSV file.
    Upserts on owner_email (case-insensitive) and acct_id (unique).
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        upserted = 0
        skipped = 0
        
        for row in csv_reader:
            try:
                # Extract data from CSV row
                owner_email = row.get('owner_email', '').strip().lower()
                acct_id = row.get('acct_id', '').strip()
                name = row.get('name', '').strip()
                topic = row.get('topic', '').strip()
                
                # Parse conservative click estimate
                conservative_click_estimate = None
                if 'conservative_click_estimate' in row and row['conservative_click_estimate'].strip():
                    try:
                        conservative_click_estimate = int(row['conservative_click_estimate'].strip())
                    except ValueError:
                        # Skip invalid values
                        pass
                
                # Skip rows with missing required fields
                if not owner_email or not acct_id:
                    skipped += 1
                    continue
                
                # Check if creator exists by owner_email (case-insensitive) or acct_id
                existing_creator = db.query(Creator).filter(
                    (func.lower(Creator.owner_email) == owner_email) | 
                    (Creator.acct_id == acct_id)
                ).first()
                
                current_time = datetime.utcnow()
                
                if existing_creator:
                    # Update existing creator
                    existing_creator.name = name or existing_creator.name
                    existing_creator.topic = topic or existing_creator.topic
                    existing_creator.updated_at = current_time
                    # Update acct_id if it's different (in case we found by email)
                    if existing_creator.acct_id != acct_id:
                        existing_creator.acct_id = acct_id
                    # Update conservative click estimate if provided
                    if conservative_click_estimate is not None:
                        existing_creator.conservative_click_estimate = conservative_click_estimate
                    upserted += 1
                else:
                    # Create new creator
                    new_creator = Creator(
                        name=name,
                        acct_id=acct_id,
                        owner_email=owner_email,
                        topic=topic,
                        conservative_click_estimate=conservative_click_estimate,
                        created_at=current_time,
                        updated_at=current_time
                    )
                    db.add(new_creator)
                    upserted += 1
                    
            except Exception as e:
                # Skip rows that cause errors
                skipped += 1
                continue
        
        # Commit all changes
        db.commit()
        
        return {
            "upserted": upserted,
            "skipped": skipped
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
