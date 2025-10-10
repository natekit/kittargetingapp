from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
import csv
import io
from typing import Dict, Any, List
from app.models import Creator, Keyword, CreatorKeyword
from app.db import get_db
from datetime import datetime

router = APIRouter()


def process_keywords(db: Session, creator_id: int, keywords_str: str) -> None:
    """Process and store keywords for a creator."""
    if not keywords_str:
        return
    
    # Split keywords by comma and clean them
    keyword_list = [kw.strip().lower() for kw in keywords_str.split(',') if kw.strip()]
    
    # Remove existing keywords for this creator
    db.query(CreatorKeyword).filter(CreatorKeyword.creator_id == creator_id).delete()
    
    for keyword_text in keyword_list:
        # Find or create keyword
        keyword = db.query(Keyword).filter(Keyword.keywords == keyword_text).first()
        if not keyword:
            keyword = Keyword(keywords=keyword_text)
            db.add(keyword)
            db.flush()  # Get the ID
        
        # Create creator-keyword relationship
        creator_keyword = CreatorKeyword(
            creator_id=creator_id,
            keyword_id=keyword.keyword_id
        )
        db.add(creator_keyword)


def process_batch(db: Session, batch: List[Dict[str, Any]]) -> int:
    """Process a batch of creators with upsert logic."""
    upserted = 0
    current_time = datetime.utcnow()
    
    for creator_data in batch:
        try:
            # Check if creator exists by owner_email (case-insensitive) or acct_id
            existing_creator = db.query(Creator).filter(
                (func.lower(Creator.owner_email) == creator_data['owner_email']) | 
                (Creator.acct_id == creator_data['acct_id'])
            ).first()
            
            if existing_creator:
                # Update existing creator
                existing_creator.name = creator_data['name'] or existing_creator.name
                existing_creator.topic = creator_data['topic'] or existing_creator.topic
                existing_creator.age_range = creator_data['age_range'] or existing_creator.age_range
                existing_creator.gender_skew = creator_data['gender_skew'] or existing_creator.gender_skew
                existing_creator.location = creator_data['location'] or existing_creator.location
                existing_creator.interests = creator_data['interests'] or existing_creator.interests
                existing_creator.updated_at = current_time
                # Update acct_id if it's different (in case we found by email)
                if existing_creator.acct_id != creator_data['acct_id']:
                    existing_creator.acct_id = creator_data['acct_id']
                # Update conservative click estimate if provided
                if creator_data['conservative_click_estimate'] is not None:
                    existing_creator.conservative_click_estimate = creator_data['conservative_click_estimate']
                
                # Process keywords
                process_keywords(db, existing_creator.creator_id, creator_data['keywords'])
                upserted += 1
            else:
                # Create new creator
                new_creator = Creator(
                    name=creator_data['name'],
                    acct_id=creator_data['acct_id'],
                    owner_email=creator_data['owner_email'],
                    topic=creator_data['topic'],
                    age_range=creator_data['age_range'],
                    gender_skew=creator_data['gender_skew'],
                    location=creator_data['location'],
                    interests=creator_data['interests'],
                    conservative_click_estimate=creator_data['conservative_click_estimate'],
                    created_at=current_time,
                    updated_at=current_time
                )
                db.add(new_creator)
                db.flush()  # Get the creator ID
                
                # Process keywords for new creator
                process_keywords(db, new_creator.creator_id, creator_data['keywords'])
                upserted += 1
        except Exception as e:
            print(f"DEBUG: Error processing creator {creator_data.get('acct_id', 'unknown')}: {e}")
            continue
    
    # Commit the batch
    db.commit()
    return upserted


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
        batch_size = 50  # Process in batches of 50
        batch = []
        
        # Debug: Print available headers
        if csv_reader.fieldnames:
            print(f"DEBUG: Available CSV headers: {csv_reader.fieldnames}")
        
        for row in csv_reader:
            try:
                # Debug: Print first row data
                if row:
                    print(f"DEBUG: First row data: {dict(row)}")
                
                # Extract data from CSV row with header standardization
                owner_email = (row.get('owner_email', '') or row.get('owner email', '') or row.get('email', '')).strip().lower()
                acct_id = (row.get('acct_id', '') or row.get('acct id', '') or row.get('account_id', '') or row.get('account id', '')).strip()
                name = (row.get('name', '') or row.get('creator_name', '') or row.get('creator name', '')).strip()
                topic = (row.get('topic', '') or row.get('category', '') or row.get('niche', '')).strip()
                
                # Extract new demographic fields
                age_range = (row.get('age_range', '') or row.get('age range', '') or row.get('age', '')).strip()
                gender_skew = (row.get('gender_skew', '') or row.get('gender skew', '') or row.get('gender', '')).strip()
                location = (row.get('location', '') or row.get('country', '') or row.get('region', '')).strip()
                interests = (row.get('interests', '') or row.get('interest', '') or row.get('tags', '')).strip()
                keywords = (row.get('keywords', '') or row.get('key_words', '') or row.get('key words', '')).strip()
                
                # Parse conservative click estimate with multiple header variations
                conservative_click_estimate = None
                estimate_fields = [
                    'conservative_click_estimate', 'conservative click estimate', 
                    'conservative_clicks', 'conservative clicks',
                    'click_estimate', 'click estimate'
                ]
                
                for field in estimate_fields:
                    if field in row and row[field].strip():
                        try:
                            conservative_click_estimate = int(row[field].strip())
                            break
                        except ValueError:
                            continue
                
                # Debug: Print extracted values
                print(f"DEBUG: Extracted - owner_email: '{owner_email}', acct_id: '{acct_id}', name: '{name}', topic: '{topic}', age_range: '{age_range}', gender_skew: '{gender_skew}', location: '{location}', interests: '{interests}', keywords: '{keywords}', conservative_click_estimate: {conservative_click_estimate}")
                
                # Skip rows with missing required fields
                if not owner_email or not acct_id:
                    print(f"DEBUG: Skipping row - missing required fields")
                    skipped += 1
                    continue
                
                # Add to batch for processing
                batch.append({
                    'owner_email': owner_email,
                    'acct_id': acct_id,
                    'name': name,
                    'topic': topic,
                    'age_range': age_range,
                    'gender_skew': gender_skew,
                    'location': location,
                    'interests': interests,
                    'keywords': keywords,
                    'conservative_click_estimate': conservative_click_estimate
                })
                
                # Process batch when it reaches batch_size
                if len(batch) >= batch_size:
                    upserted += process_batch(db, batch)
                    batch = []
                    
            except Exception as e:
                # Skip rows that cause errors
                skipped += 1
                continue
        
        # Process any remaining items in the final batch
        if batch:
            upserted += process_batch(db, batch)
        
        return {
            "upserted": upserted,
            "skipped": skipped
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
