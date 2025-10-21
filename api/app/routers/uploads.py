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
from app.models import Creator, PerfUpload, ClickUnique, Insertion, ConvUpload, Conversion, Advertiser, Campaign, DeclinedCreator, CreatorVector
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
    Upload performance or decline CSV data for a specific insertion.
    
    Performance CSV expected columns: Creator, Clicks, Unique, Flagged, Execution Date, Status
    Decline CSV expected columns: Creator, Send Offer
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
        
        # Detect CSV type based on column presence
        csv_columns = csv_reader.fieldnames or []
        print(f"DEBUG: CSV columns found: {csv_columns}")
        
        # Check for performance columns (case-insensitive)
        clicks_col = any(col.lower() == 'clicks' for col in csv_columns)
        unique_col = any(col.lower() == 'unique' for col in csv_columns)
        execution_date_col = any(col.lower() == 'execution date' for col in csv_columns)
        is_performance_csv = clicks_col and unique_col and execution_date_col
        
        # Check for decline columns (case-insensitive)
        offer_email_col = any(col.lower() == 'offer email' for col in csv_columns)
        is_decline_csv = offer_email_col
        
        print(f"DEBUG: CSV type detection - Performance: {is_performance_csv}, Decline: {is_decline_csv}")
        
        if not is_performance_csv and not is_decline_csv:
            raise HTTPException(status_code=400, detail=f"CSV must contain either performance columns (Clicks, Unique, Execution Date) or decline columns (Offer email). Found columns: {csv_columns}")
        
        print(f"DEBUG: Final CSV type - Performance: {is_performance_csv}, Decline: {is_decline_csv}")
        print(f"DEBUG: Starting performance upload for insertion {insertion_id} with duplicate detection enabled")
        
        inserted_rows = 0
        replaced_rows = 0
        unmatched_count = 0
        unmatched_examples = []
        declined_count = 0
        
        # Create perf_upload record
        perf_upload = PerfUpload(
            insertion_id=insertion_id,
            uploaded_at=datetime.utcnow(),
            filename=file.filename
        )
        db.add(perf_upload)
        db.flush()  # Get the ID without committing
        
        # Delete existing performance data for this insertion to replace with new data (only for performance CSV)
        replaced_rows = 0
        if is_performance_csv:
            existing_click_uniques = db.query(ClickUnique).filter(
                ClickUnique.perf_upload_id.in_(
                    db.query(PerfUpload.perf_upload_id).filter(PerfUpload.insertion_id == insertion_id)
                )
            ).all()
            
            replaced_rows = len(existing_click_uniques)
            for click_unique in existing_click_uniques:
                db.delete(click_unique)
            
            print(f"DEBUG: Deleted {replaced_rows} existing performance records for insertion {insertion_id}")
        
        for row in csv_reader:
            try:
                # Extract data from CSV row - get Creator column case-insensitively
                creator_field = next((row.get(col, '') for col in csv_columns if col.lower() == 'creator'), '').strip()
                
                # Skip rows with missing creator field
                if not creator_field:
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
                
                # Process based on CSV type
                if is_performance_csv:
                    # Performance CSV processing - get columns case-insensitively
                    clicks_str = next((row.get(col, '') for col in csv_columns if col.lower() == 'clicks'), '').strip()
                    unique_str = next((row.get(col, '') for col in csv_columns if col.lower() == 'unique'), '').strip()
                    flagged_str = next((row.get(col, '') for col in csv_columns if col.lower() == 'flagged'), '').strip()
                    execution_date_str = next((row.get(col, '') for col in csv_columns if col.lower() == 'execution date'), '').strip()
                    status = next((row.get(col, '') for col in csv_columns if col.lower() == 'status'), '').strip()
                    
                    # Skip rows with "unscheduled" status - these should not be stored or used in forecasts
                    if status and status.lower() == "unscheduled":
                        print(f"DEBUG: Skipping unscheduled row for creator {creator.name}")
                        continue
                    
                    # Skip rows with missing required performance fields
                    if not unique_str or not execution_date_str:
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
                    
                    # Check for existing click data for same creator/insertion/date and delete it
                    existing_clicks = db.query(ClickUnique).join(PerfUpload).filter(
                        ClickUnique.creator_id == creator.creator_id,
                        PerfUpload.insertion_id == insertion_id,
                        ClickUnique.execution_date == execution_date
                    ).all()
                    
                    if existing_clicks:
                        print(f"DEBUG: Found {len(existing_clicks)} existing click records for creator {creator.creator_id} on {execution_date} - deleting duplicates")
                        for existing_click in existing_clicks:
                            db.delete(existing_click)
                        replaced_rows += len(existing_clicks)
                    
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
                    
                    # Check if status is "declined" and record it (existing logic preserved)
                    if status and status.lower() == "declined":
                        # Get advertiser_id from the insertion's campaign
                        advertiser_id = insertion.campaign.advertiser_id
                        
                        # Check if this creator-advertiser combination is already declined
                        existing_decline = db.query(DeclinedCreator).filter(
                            DeclinedCreator.creator_id == creator.creator_id,
                            DeclinedCreator.advertiser_id == advertiser_id
                        ).first()
                        
                        if not existing_decline:
                            # Record the declined creator-advertiser combination
                            declined_creator = DeclinedCreator(
                                creator_id=creator.creator_id,
                                advertiser_id=advertiser_id,
                                reason=f"Declined from performance upload on {execution_date}"
                            )
                            db.add(declined_creator)
                            declined_count += 1
                
                elif is_decline_csv:
                    # Decline CSV processing - get column case-insensitively
                    offer_email = next((row.get(col, '') for col in csv_columns if col.lower() == 'offer email'), '').strip()
                    
                    # Skip rows with missing Offer email field
                    if not offer_email:
                        continue
                    
                    # Check if Offer email is "declined"
                    if offer_email.lower() == "declined":
                        # Get advertiser_id from the insertion's campaign
                        advertiser_id = insertion.campaign.advertiser_id
                        
                        # Check if this creator-advertiser combination is already declined
                        existing_decline = db.query(DeclinedCreator).filter(
                            DeclinedCreator.creator_id == creator.creator_id,
                            DeclinedCreator.advertiser_id == advertiser_id
                        ).first()
                        
                        if not existing_decline:
                            # Record the declined creator-advertiser combination
                            declined_creator = DeclinedCreator(
                                creator_id=creator.creator_id,
                                advertiser_id=advertiser_id,
                                reason=f"Declined from decline upload on {datetime.utcnow().date()}"
                            )
                            db.add(declined_creator)
                            declined_count += 1
                
            except Exception as e:
                # Skip rows that cause errors
                continue
        
        # Commit all changes
        db.commit()
        
        # Limit unmatched examples to first 10
        unmatched_examples = unmatched_examples[:10]
        
        print(f"DEBUG: Upload completed - Inserted: {inserted_rows}, Replaced: {replaced_rows}, Unmatched: {unmatched_count}, Declined: {declined_count}")
        
        return {
            "perf_upload_id": perf_upload.perf_upload_id,
            "csv_type": "performance" if is_performance_csv else "decline",
            "inserted_rows": inserted_rows,
            "replaced_rows": replaced_rows,
            "unmatched_count": unmatched_count,
            "unmatched_examples": unmatched_examples,
            "declined_count": declined_count
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
        
        # Process each row in the CSV
        for row_index, row in enumerate(csv_rows):
            print(f"DEBUG: Processing row {row_index + 1}")
            try:
                # Handle both original and standardized headers
                acct_id = row.get('Acct ID', row.get('Acct Id', row.get('acct_id', ''))).strip()
                conversions_str = row.get('Conversions', row.get('conversions', '')).strip()
                print(f"DEBUG: Row {row_index + 1} - acct_id: '{acct_id}', conversions: '{conversions_str}'")
                
                # Skip rows with missing required fields
                if not acct_id or not conversions_str:
                    print(f"DEBUG: Row {row_index + 1} - Skipping due to missing fields")
                    continue
                
                # Skip header rows
                if acct_id in ['Acct ID', 'Acct Id', 'acct_id'] or conversions_str in ['Conversions', 'conversions']:
                    print(f"DEBUG: Row {row_index + 1} - Skipping header row")
                    continue
                
                # Find creator by acct_id
                print(f"DEBUG: Row {row_index + 1} - Looking for creator with acct_id: '{acct_id}'")
                creator = db.query(Creator).filter(Creator.acct_id == acct_id).first()
                if not creator:
                    print(f"DEBUG: Row {row_index + 1} - No creator found for acct_id: '{acct_id}'")
                    continue
                print(f"DEBUG: Row {row_index + 1} - Found creator: {creator.creator_id}")
                
                # Parse conversions count
                try:
                    conversions = int(conversions_str)
                    print(f"DEBUG: Row {row_index + 1} - Parsed conversions: {conversions}")
                except ValueError as e:
                    print(f"DEBUG: Row {row_index + 1} - Error parsing conversions: {e}")
                    continue
                
                # Delete existing conversions for this creator/insertion
                print(f"DEBUG: Row {row_index + 1} - Looking for existing conversions for creator {creator.creator_id}, insertion {insertion_id}")
                existing_conversions = db.query(Conversion).filter(
                    Conversion.creator_id == creator.creator_id,
                    Conversion.insertion_id == insertion_id
                ).all()
                print(f"DEBUG: Row {row_index + 1} - Found {len(existing_conversions)} existing conversions")
                
                for conv in existing_conversions:
                    print(f"DEBUG: Row {row_index + 1} - Deleting conversion {conv.conversion_id} with period {conv.period}")
                    db.delete(conv)
                replaced_rows += len(existing_conversions)
                print(f"DEBUG: Row {row_index + 1} - Deleted {len(existing_conversions)} conversions")
                
                # Commit the deletions before inserting new ones
                db.commit()
                print(f"DEBUG: Row {row_index + 1} - Committed deletions")
                
                # Create daterange for the period
                period_range = f"[{start_date},{end_date}]"
                print(f"DEBUG: Row {row_index + 1} - Created period_range: {period_range}")
                
                # Insert new conversion record
                print(f"DEBUG: Row {row_index + 1} - Creating new conversion record")
                conversion = Conversion(
                    conv_upload_id=conv_upload.conv_upload_id,
                    insertion_id=insertion_id,
                    creator_id=creator.creator_id,
                    period=period_range,
                    conversions=conversions
                )
                db.add(conversion)
                print(f"DEBUG: Row {row_index + 1} - Added conversion to session")
                
                # Flush to catch any immediate errors
                try:
                    db.flush()
                    print(f"DEBUG: Row {row_index + 1} - Flush successful")
                except Exception as flush_error:
                    print(f"DEBUG: Row {row_index + 1} - Flush failed: {flush_error}")
                    print(f"DEBUG: Row {row_index + 1} - Conversion data: creator_id={creator.creator_id}, insertion_id={insertion_id}, period={period_range}, conversions={conversions}")
                    raise
                
                inserted_rows += 1
                print(f"DEBUG: Row {row_index + 1} - Successfully processed, inserted_rows now: {inserted_rows}")
                
                # Debug: Verify the conversion was actually saved
                # Note: We can't directly compare DATERANGE with string, so we'll check by creator and insertion
                saved_conversion = db.query(Conversion).filter(
                    Conversion.creator_id == creator.creator_id,
                    Conversion.insertion_id == insertion_id
                ).first()
                print(f"DEBUG: Row {row_index + 1} - Verification: Conversion saved with ID {saved_conversion.conversion_id if saved_conversion else 'NOT FOUND'}")
                if saved_conversion:
                    print(f"DEBUG: Row {row_index + 1} - Verification: Period {saved_conversion.period}, Conversions {saved_conversion.conversions}")
                
                # Debug: Check if the conversion actually exists in the database after commit
                db.commit()  # Ensure the conversion is committed
                committed_conversion = db.query(Conversion).filter(
                    Conversion.creator_id == creator.creator_id,
                    Conversion.insertion_id == insertion_id
                ).first()
                print(f"DEBUG: Row {row_index + 1} - Post-commit verification: Conversion ID {committed_conversion.conversion_id if committed_conversion else 'NOT FOUND'}")
                
            except Exception as e:
                print(f"DEBUG: Row {row_index + 1} - ERROR: {e}")
                print(f"DEBUG: Row {row_index + 1} - Exception type: {type(e)}")
                import traceback
                print(f"DEBUG: Row {row_index + 1} - Traceback: {traceback.format_exc()}")
                # Skip rows that cause errors
                continue
        
        # All changes are already committed per row
        
        # Debug: Final verification of what was actually saved
        final_conversions = db.query(Conversion).filter(
            Conversion.conv_upload_id == conv_upload.conv_upload_id
        ).all()
        print(f"DEBUG: FINAL - Total conversions saved for this upload: {len(final_conversions)}")
        for conv in final_conversions:
            print(f"DEBUG: FINAL - Conversion ID {conv.conversion_id}: Creator {conv.creator_id}, Period {conv.period}, Conversions {conv.conversions}")
        
        return {
            "conv_upload_id": conv_upload.conv_upload_id,
            "replaced_rows": replaced_rows,
            "inserted_rows": inserted_rows
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")


@router.post("/cleanup/performance-data")
async def cleanup_performance_data(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Clean up all performance and conversion data for testing.
    WARNING: This will delete ALL click and conversion data!
    """
    try:
        print("DEBUG: CLEANUP - Starting performance data cleanup")
        
        # Delete all click data
        click_count = db.query(ClickUnique).count()
        db.query(ClickUnique).delete()
        print(f"DEBUG: CLEANUP - Deleted {click_count} click records")
        
        # Delete all performance uploads
        perf_upload_count = db.query(PerfUpload).count()
        db.query(PerfUpload).delete()
        print(f"DEBUG: CLEANUP - Deleted {perf_upload_count} performance upload records")
        
        # Delete all conversion data
        conversion_count = db.query(Conversion).count()
        db.query(Conversion).delete()
        print(f"DEBUG: CLEANUP - Deleted {conversion_count} conversion records")
        
        # Delete all conversion uploads
        conv_upload_count = db.query(ConvUpload).count()
        db.query(ConvUpload).delete()
        print(f"DEBUG: CLEANUP - Deleted {conv_upload_count} conversion upload records")
        
        # Delete all decline data
        declined_count = db.query(DeclinedCreator).count()
        db.query(DeclinedCreator).delete()
        print(f"DEBUG: CLEANUP - Deleted {declined_count} declined creator records")
        
        # Commit the cleanup
        db.commit()
        
        print("DEBUG: CLEANUP - Performance data cleanup completed successfully")
        
        return {
            "status": "success",
            "message": "Performance data cleanup completed",
            "deleted_records": {
                "clicks": click_count,
                "perf_uploads": perf_upload_count,
                "conversions": conversion_count,
                "conv_uploads": conv_upload_count,
                "declined_creators": declined_count
            }
        }
        
    except Exception as e:
        db.rollback()
        print(f"DEBUG: CLEANUP - Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@router.post("/vectors")
async def upload_vectors(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Upload creator vectors from CSV file.
    Expected CSV format: account_id, vector_component_1, vector_component_2, ..., vector_component_n
    """
    try:
        print(f"DEBUG: Vector upload started - {file.filename}")
        
        # Read and parse CSV
        content = await file.read()
        csv_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        uploaded_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        
        # Batch processing for speed - collect all data first
        batch_data = []
        creator_lookup = {}
        
        # Pre-fetch all creators for faster lookup
        print("DEBUG: Pre-fetching creators for batch processing...")
        all_creators = db.query(Creator).all()
        creator_lookup = {creator.acct_id: creator for creator in all_creators}
        print(f"DEBUG: Loaded {len(creator_lookup)} creators for lookup")
        
        # Process all rows first
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 because header is row 1
            try:
                # Get account_id
                account_id = row.get('account_id')
                if not account_id:
                    errors.append(f"Row {row_num}: Missing account_id")
                    skipped_count += 1
                    continue
                
                # Find creator by account_id (using pre-fetched lookup)
                creator = creator_lookup.get(account_id)
                if not creator:
                    errors.append(f"Row {row_num}: Creator with account_id '{account_id}' not found")
                    skipped_count += 1
                    continue
                
                # Extract vector components (all columns except account_id)
                vector_components = []
                for key, value in row.items():
                    if key != 'account_id' and value.strip():
                        try:
                            vector_components.append(float(value))
                        except ValueError:
                            errors.append(f"Row {row_num}: Invalid vector component '{value}' for column '{key}'")
                            break
                else:
                    # All vector components parsed successfully
                    if not vector_components:
                        errors.append(f"Row {row_num}: No vector components found")
                        skipped_count += 1
                        continue
                    
                    vector_dimension = len(vector_components)
                    batch_data.append({
                        'creator_id': creator.creator_id,
                        'vector': vector_components,
                        'vector_dimension': vector_dimension,
                        'creator_name': creator.name
                    })
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                skipped_count += 1
                print(f"DEBUG: Error processing row {row_num}: {e}")
        
        # Batch database operations
        print(f"DEBUG: Processing {len(batch_data)} vectors in batch...")
        
        # Get existing vectors for batch update
        creator_ids = [item['creator_id'] for item in batch_data]
        existing_vectors = {v.creator_id: v for v in db.query(CreatorVector).filter(CreatorVector.creator_id.in_(creator_ids)).all()}
        
        # Process batch
        for item in batch_data:
            creator_id = item['creator_id']
            if creator_id in existing_vectors:
                # Update existing vector
                existing_vectors[creator_id].vector = item['vector']
                existing_vectors[creator_id].vector_dimension = item['vector_dimension']
                existing_vectors[creator_id].updated_at = datetime.now(pytz.UTC)
                updated_count += 1
            else:
                # Create new vector
                new_vector = CreatorVector(
                    creator_id=creator_id,
                    vector=item['vector'],
                    vector_dimension=item['vector_dimension']
                )
                db.add(new_vector)
                uploaded_count += 1
        
        # Single commit for all changes
        print(f"DEBUG: Committing {len(batch_data)} vector operations...")
        db.commit()
        
        print(f"DEBUG: Vector upload completed - {uploaded_count} created, {updated_count} updated, {skipped_count} skipped")
        
        return {
            "status": "success",
            "message": f"Vector upload completed",
            "uploaded": uploaded_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "total_processed": uploaded_count + updated_count + skipped_count,
            "errors": errors[:10] if errors else [],  # Limit errors to first 10
            "total_errors": len(errors)
        }
        
    except Exception as e:
        db.rollback()
        print(f"DEBUG: Vector upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Vector upload failed: {str(e)}")


@router.post("/create-vectors-table")
async def create_vectors_table(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Create the creator_vectors table directly.
    Use this if migrations aren't working.
    """
    try:
        print("DEBUG: Creating creator_vectors table...")
        
        # Check if table already exists
        from sqlalchemy import text
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'creator_vectors'
            );
        """)).scalar()
        
        if result:
            return {
                "status": "success",
                "message": "creator_vectors table already exists",
                "table_exists": True
            }
        
        # Create the table
        db.execute(text("""
            CREATE TABLE creator_vectors (
                creator_id INTEGER NOT NULL,
                vector NUMERIC[] NOT NULL,
                vector_dimension INTEGER NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                PRIMARY KEY (creator_id),
                FOREIGN KEY (creator_id) REFERENCES creators (creator_id),
                CHECK (vector_dimension > 0)
            );
        """))
        
        db.commit()
        
        print("DEBUG: creator_vectors table created successfully")
        
        return {
            "status": "success",
            "message": "creator_vectors table created successfully",
            "table_exists": True
        }
        
    except Exception as e:
        db.rollback()
        print(f"DEBUG: Error creating table: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create table: {str(e)}")
