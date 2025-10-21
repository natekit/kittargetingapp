from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
import csv
import io
import asyncio
from typing import Dict, Any, List
from app.models import Creator, CreatorTopic, CreatorKeyword, ClickUnique, Conversion, Placement, DeclinedCreator
from app.db import get_db
from datetime import datetime

router = APIRouter()


def wipe_all_creators(db: Session) -> int:
    """
    Completely wipe all creator data and related records.
    Returns the number of creators that were deleted.
    """
    try:
        print("DEBUG: Wiping all creator data...")
        
        # Get count before deletion for logging
        total_creators = db.query(Creator).count()
        print(f"DEBUG: Found {total_creators} creators to delete")
        
        # Delete all related data first (in order of dependencies)
        # 1. Delete creator topics
        topics_deleted = db.query(CreatorTopic).delete()
        print(f"DEBUG: Deleted {topics_deleted} creator topics")
        
        # 2. Delete creator keywords
        keywords_deleted = db.query(CreatorKeyword).delete()
        print(f"DEBUG: Deleted {keywords_deleted} creator keywords")
        
        # 3. Delete click data
        clicks_deleted = db.query(ClickUnique).delete()
        print(f"DEBUG: Deleted {clicks_deleted} click records")
        
        # 4. Delete conversion data
        conversions_deleted = db.query(Conversion).delete()
        print(f"DEBUG: Deleted {conversions_deleted} conversion records")
        
        # 5. Delete placements
        placements_deleted = db.query(Placement).delete()
        print(f"DEBUG: Deleted {placements_deleted} placement records")
        
        # 6. Delete declined creators
        declined_deleted = db.query(DeclinedCreator).delete()
        print(f"DEBUG: Deleted {declined_deleted} declined creator records")
        
        # 7. Finally delete all creators
        creators_deleted = db.query(Creator).delete()
        print(f"DEBUG: Deleted {creators_deleted} creator records")
        
        # Commit the wipe
        db.commit()
        print(f"DEBUG: Successfully wiped all creator data")
        return creators_deleted
        
    except Exception as e:
        print(f"DEBUG: Error wiping creator data: {e}")
        db.rollback()
        raise e


def safe_delete_creator(db: Session, creator_id: int) -> bool:
    """
    Safely delete a creator and all related data.
    Returns True if deletion was successful, False otherwise.
    """
    try:
        print(f"DEBUG: Deleting creator {creator_id} and related data...")
        
        # Delete in order of dependencies (child tables first)
        # 1. Delete creator topics
        topics_deleted = db.query(CreatorTopic).filter(CreatorTopic.creator_id == creator_id).delete()
        print(f"DEBUG: Deleted {topics_deleted} creator topics")
        
        # 2. Delete creator keywords
        keywords_deleted = db.query(CreatorKeyword).filter(CreatorKeyword.creator_id == creator_id).delete()
        print(f"DEBUG: Deleted {keywords_deleted} creator keywords")
        
        # 3. Delete click data
        clicks_deleted = db.query(ClickUnique).filter(ClickUnique.creator_id == creator_id).delete()
        print(f"DEBUG: Deleted {clicks_deleted} click records")
        
        # 4. Delete conversion data
        conversions_deleted = db.query(Conversion).filter(Conversion.creator_id == creator_id).delete()
        print(f"DEBUG: Deleted {conversions_deleted} conversion records")
        
        # 5. Delete placements
        placements_deleted = db.query(Placement).filter(Placement.creator_id == creator_id).delete()
        print(f"DEBUG: Deleted {placements_deleted} placement records")
        
        # 6. Finally delete the creator
        creator_deleted = db.query(Creator).filter(Creator.creator_id == creator_id).delete()
        print(f"DEBUG: Deleted {creator_deleted} creator record")
        
        if creator_deleted > 0:
            db.commit()
            print(f"DEBUG: Successfully deleted creator {creator_id}")
            return True
        else:
            print(f"DEBUG: Creator {creator_id} not found for deletion")
            return False
            
    except Exception as e:
        print(f"DEBUG: Error deleting creator {creator_id}: {e}")
        db.rollback()
        return False


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
                upserted += 1
        except Exception as e:
            print(f"DEBUG: Error processing creator {creator_data.get('acct_id', 'unknown')}: {e}")
            continue
    
    # Commit the batch
    db.commit()
    return upserted


def process_batch_optimized(db: Session, batch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process a batch of creators with optimized bulk operations and detailed logging."""
    upserted = 0
    skipped = 0
    skipped_details = []
    email_conflicts = []
    current_time = datetime.utcnow()
    
    try:
        # Extract emails and acct_ids for bulk lookup
        emails = [creator_data['owner_email'] for creator_data in batch]
        acct_ids = [creator_data['acct_id'] for creator_data in batch]
        
        # Bulk query for existing creators
        existing_creators = db.query(Creator).filter(
            (func.lower(Creator.owner_email).in_([email.lower() for email in emails])) |
            (Creator.acct_id.in_(acct_ids))
        ).all()
        
        # Create lookup dictionaries for fast access
        existing_by_email = {creator.owner_email.lower(): creator for creator in existing_creators}
        existing_by_acct_id = {creator.acct_id: creator for creator in existing_creators}
        
        creators_to_update = []
        creators_to_create = []
        
        for creator_data in batch:
            try:
                acct_id = creator_data['acct_id']
                email = creator_data['owner_email']
                name = creator_data['name']
                
                # Check for existing creators by both email and acct_id
                existing_by_email_match = existing_by_email.get(email.lower())
                existing_by_acct_id_match = existing_by_acct_id.get(acct_id)
                
                # Handle conflicts and determine which creator to use
                if existing_by_email_match and existing_by_acct_id_match:
                    if existing_by_email_match.creator_id == existing_by_acct_id_match.creator_id:
                        # Same creator found by both - safe to update
                        existing_creator = existing_by_email_match
                        print(f"DEBUG: Updating creator {name} (ID: {existing_creator.creator_id}) - found by both email and acct_id")
                    else:
                        # Different creators - conflict!
                        print(f"DEBUG: CONFLICT - Email {email} belongs to creator {existing_by_email_match.creator_id} but acct_id {acct_id} belongs to creator {existing_by_acct_id_match.creator_id}")
                        email_conflicts.append({
                            'email': email,
                            'acct_id': acct_id,
                            'name': name,
                            'email_creator_id': existing_by_email_match.creator_id,
                            'acct_id_creator_id': existing_by_acct_id_match.creator_id
                        })
                        skipped_details.append({
                            'acct_id': acct_id,
                            'name': name,
                            'reason': 'Email and acct_id belong to different existing creators'
                        })
                        skipped += 1
                        continue
                elif existing_by_acct_id_match:
                    # Found by acct_id - prioritize acct_id matching
                    existing_creator = existing_by_acct_id_match
                    print(f"DEBUG: Updating creator {name} (ID: {existing_creator.creator_id}) - found by acct_id")
                elif existing_by_email_match:
                    # Found by email only - check if acct_id would conflict
                    if existing_by_acct_id.get(acct_id):
                        print(f"DEBUG: CONFLICT - Email {email} belongs to creator {existing_by_email_match.creator_id} but acct_id {acct_id} already exists for another creator")
                        skipped_details.append({
                            'acct_id': acct_id,
                            'name': name,
                            'reason': f'Email belongs to creator {existing_by_email_match.creator_id} but acct_id {acct_id} already exists'
                        })
                        skipped += 1
                        continue
                    else:
                        # Safe to update - email match, acct_id is new
                        existing_creator = existing_by_email_match
                        print(f"DEBUG: Updating creator {name} (ID: {existing_creator.creator_id}) - found by email, updating acct_id to {acct_id}")
                else:
                    # No existing creator found - create new
                    print(f"DEBUG: Creating new creator {name} (acct_id: {acct_id})")
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
                    creators_to_create.append(new_creator)
                    upserted += 1
                    continue
                
                # Update existing creator (only non-unique fields)
                existing_creator.name = creator_data['name'] or existing_creator.name
                existing_creator.topic = creator_data['topic'] or existing_creator.topic
                existing_creator.age_range = creator_data['age_range'] or existing_creator.age_range
                existing_creator.gender_skew = creator_data['gender_skew'] or existing_creator.gender_skew
                existing_creator.location = creator_data['location'] or existing_creator.location
                existing_creator.interests = creator_data['interests'] or existing_creator.interests
                existing_creator.updated_at = current_time
                
                # Only update acct_id if it's different and safe to do so
                if existing_creator.acct_id != creator_data['acct_id']:
                    existing_creator.acct_id = creator_data['acct_id']
                    print(f"DEBUG: Updated acct_id from {existing_creator.acct_id} to {creator_data['acct_id']} for creator {name}")
                
                # Update conservative click estimate if provided
                if creator_data['conservative_click_estimate'] is not None:
                    existing_creator.conservative_click_estimate = creator_data['conservative_click_estimate']
                
                creators_to_update.append(existing_creator)
                upserted += 1
                    
            except Exception as e:
                print(f"DEBUG: Error processing creator {creator_data.get('acct_id', 'unknown')}: {e}")
                skipped_details.append({
                    'acct_id': creator_data.get('acct_id', 'unknown'),
                    'name': creator_data.get('name', 'unknown'),
                    'reason': f'Processing error: {str(e)}'
                })
                skipped += 1
                continue
        
        # Bulk operations
        if creators_to_create:
            db.add_all(creators_to_create)
        
        # Commit the batch
        db.commit()
        
        # Log summary
        if skipped_details:
            print(f"DEBUG: Skipped {len(skipped_details)} creators:")
            for detail in skipped_details:
                print(f"  - {detail['name']} (acct_id: {detail['acct_id']}): {detail['reason']}")
        
        if email_conflicts:
            print(f"DEBUG: Found {len(email_conflicts)} email/acct_id conflicts:")
            for conflict in email_conflicts:
                print(f"  - Email {conflict['email']} → Creator {conflict['email_creator_id']}, acct_id {conflict['acct_id']} → Creator {conflict['acct_id_creator_id']}")
        
        return {
            "upserted": upserted, 
            "skipped": skipped,
            "skipped_details": skipped_details,
            "email_conflicts": email_conflicts
        }
        
    except Exception as e:
        db.rollback()
        print(f"DEBUG: Batch processing error: {e}")
        return {
            "upserted": 0, 
            "skipped": len(batch),
            "skipped_details": [{"acct_id": "batch_failed", "name": "batch_failed", "reason": f"Batch error: {str(e)}"}],
            "email_conflicts": []
        }


@router.post("/seed/creators")
async def seed_creators(
    file: UploadFile = File(...),
    sync_mode: str = Form("upsert"),  # "upsert", "full_sync", or "full_reset"
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Seed creators from CSV file.
    
    sync_mode options:
    - "upsert": Only add/update creators (existing behavior)
    - "full_sync": Add/update creators AND remove creators not in CSV
    - "full_reset": Wipe all creators and reload from CSV (recommended)
    """
    print(f"DEBUG: Sync mode received: {sync_mode}")
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        # Handle full reset mode - wipe everything first
        wiped = 0
        if sync_mode == "full_reset":
            print(f"DEBUG: Full reset mode - wiping all existing creator data...")
            wiped = wipe_all_creators(db)
            print(f"DEBUG: Wiped {wiped} creators, now loading from CSV...")
        
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        upserted = 0
        skipped = 0
        batch_size = 100  # Increased batch size for better performance
        batch = []
        total_rows = 0
        
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
                print(f"DEBUG: Extracted - owner_email: '{owner_email}', acct_id: '{acct_id}', name: '{name}', topic: '{topic}', age_range: '{age_range}', gender_skew: '{gender_skew}', location: '{location}', interests: '{interests}', conservative_click_estimate: {conservative_click_estimate}")
                
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
                    'conservative_click_estimate': conservative_click_estimate
                })
                
                # Process batch when it reaches batch_size
                if len(batch) >= batch_size:
                    print(f"DEBUG: Processing batch of {len(batch)} creators")
                    batch_result = process_batch_optimized(db, batch)
                    upserted += batch_result['upserted']
                    skipped += batch_result['skipped']
                    batch = []
                    
            except Exception as e:
                # Skip rows that cause errors
                skipped += 1
                continue
        
        # Process any remaining items in the final batch
        if batch:
            print(f"DEBUG: Processing final batch of {len(batch)} creators")
            batch_result = process_batch_optimized(db, batch)
            upserted += batch_result['upserted']
            skipped += batch_result['skipped']
        
        deleted = 0
        
        # Handle full sync mode - delete creators not in CSV
        if sync_mode == "full_sync":
            print(f"DEBUG: Full sync mode - identifying creators to delete...")
            
            # Get all creator IDs from CSV (we need to re-read the CSV for this)
            csv_content_rewind = content.decode('utf-8')
            csv_reader_rewind = csv.DictReader(io.StringIO(csv_content_rewind))
            
            csv_acct_ids = set()
            csv_emails = set()
            
            for row in csv_reader_rewind:
                acct_id = (row.get('acct_id', '') or row.get('acct id', '') or row.get('account_id', '') or row.get('account id', '')).strip()
                owner_email = (row.get('owner_email', '') or row.get('owner email', '') or row.get('email', '')).strip().lower()
                
                if acct_id:
                    csv_acct_ids.add(acct_id)
                if owner_email:
                    csv_emails.add(owner_email)
            
            print(f"DEBUG: CSV contains {len(csv_acct_ids)} acct_ids and {len(csv_emails)} emails")
            
            # Find creators in database that are NOT in CSV
            creators_to_delete = db.query(Creator).filter(
                ~Creator.acct_id.in_(csv_acct_ids) & 
                ~func.lower(Creator.owner_email).in_(csv_emails)
            ).all()
            
            print(f"DEBUG: Found {len(creators_to_delete)} creators to delete")
            
            # Delete creators not in CSV
            for creator in creators_to_delete:
                if safe_delete_creator(db, creator.creator_id):
                    deleted += 1
                    print(f"DEBUG: Deleted creator {creator.name} (acct_id: {creator.acct_id})")
                else:
                    print(f"DEBUG: Failed to delete creator {creator.name} (acct_id: {creator.acct_id})")
        
        print(f"DEBUG: Sync completed - {upserted} upserted, {skipped} skipped, {deleted} deleted, {wiped} wiped")
        return {
            "upserted": upserted,
            "skipped": skipped,
            "deleted": deleted,
            "wiped": wiped,
            "total_processed": upserted + skipped,
            "message": f"Successfully processed {upserted} creators, skipped {skipped} due to conflicts" + 
                      (f", deleted {deleted} creators not in CSV" if deleted > 0 else "") +
                      (f", wiped {wiped} existing creators" if wiped > 0 else "")
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")


@router.post("/cleanup/orphaned-data")
async def cleanup_orphaned_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Clean up orphaned performance data (clicks, conversions, declined creators)
    that reference creators that no longer exist.
    """
    try:
        print("DEBUG: Starting orphaned data cleanup...")
        
        # Get all existing creator IDs
        existing_creator_ids = set(row[0] for row in db.query(Creator.creator_id).all())
        print(f"DEBUG: Found {len(existing_creator_ids)} existing creators")
        
        # Clean up orphaned clicks
        orphaned_clicks = db.query(ClickUnique).filter(
            ~ClickUnique.creator_id.in_(existing_creator_ids)
        ).count()
        if orphaned_clicks > 0:
            db.query(ClickUnique).filter(
                ~ClickUnique.creator_id.in_(existing_creator_ids)
            ).delete()
            print(f"DEBUG: Deleted {orphaned_clicks} orphaned click records")
        
        # Clean up orphaned conversions
        orphaned_conversions = db.query(Conversion).filter(
            ~Conversion.creator_id.in_(existing_creator_ids)
        ).count()
        if orphaned_conversions > 0:
            db.query(Conversion).filter(
                ~Conversion.creator_id.in_(existing_creator_ids)
            ).delete()
            print(f"DEBUG: Deleted {orphaned_conversions} orphaned conversion records")
        
        # Clean up orphaned declined creators
        orphaned_declined = db.query(DeclinedCreator).filter(
            ~DeclinedCreator.creator_id.in_(existing_creator_ids)
        ).count()
        if orphaned_declined > 0:
            db.query(DeclinedCreator).filter(
                ~DeclinedCreator.creator_id.in_(existing_creator_ids)
            ).delete()
            print(f"DEBUG: Deleted {orphaned_declined} orphaned declined creator records")
        
        db.commit()
        
        return {
            "status": "success",
            "orphaned_clicks": orphaned_clicks,
            "orphaned_conversions": orphaned_conversions,
            "orphaned_declined": orphaned_declined,
            "message": f"Cleaned up {orphaned_clicks} orphaned clicks, {orphaned_conversions} orphaned conversions, {orphaned_declined} orphaned declined records"
        }
        
    except Exception as e:
        db.rollback()
        print(f"DEBUG: Error cleaning up orphaned data: {e}")
        raise HTTPException(status_code=500, detail=f"Error cleaning up orphaned data: {str(e)}")


@router.post("/seed/creators/async")
async def seed_creators_async(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start async creator sync for large datasets.
    Returns immediately with job ID for progress tracking.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    # For now, just process normally but with better error handling
    # In the future, this could be enhanced with Redis/background job processing
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        # Count total rows first
        total_rows = sum(1 for _ in csv_reader)
        print(f"DEBUG: Starting async sync for {total_rows} creators")
        
        # Reset reader
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        upserted = 0
        skipped = 0
        batch_size = 200  # Larger batch size for async processing
        batch = []
        
        for row_num, row in enumerate(csv_reader, 1):
            try:
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
                
                # Parse conservative click estimate
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
                
                # Skip rows with missing required fields
                if not owner_email or not acct_id:
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
                    'conservative_click_estimate': conservative_click_estimate
                })
                
                # Process batch when it reaches batch_size
                if len(batch) >= batch_size:
                    print(f"DEBUG: Processing batch {row_num//batch_size} of {len(batch)} creators (row {row_num}/{total_rows})")
                    batch_result = process_batch_optimized(db, batch)
                    upserted += batch_result['upserted']
                    skipped += batch_result['skipped']
                    batch = []
                    
            except Exception as e:
                print(f"DEBUG: Error processing row {row_num}: {e}")
                skipped += 1
                continue
        
        # Process any remaining items in the final batch
        if batch:
            print(f"DEBUG: Processing final batch of {len(batch)} creators")
            batch_result = process_batch_optimized(db, batch)
            upserted += batch_result['upserted']
            skipped += batch_result['skipped']
        
        print(f"DEBUG: Async sync completed - {upserted} upserted, {skipped} skipped")
        return {
            "status": "completed",
            "upserted": upserted,
            "skipped": skipped,
            "total_processed": upserted + skipped,
            "total_rows": total_rows,
            "message": f"Successfully processed {upserted} creators, skipped {skipped} due to conflicts"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
