from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
import csv
import io
from typing import Dict, Any, List, Tuple
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

        # Collect normalized rows first
        all_rows: List[Tuple[str, str, str, str]] = []
        for row in csv_reader:
            try:
                owner_email = (row.get('owner_email') or '').strip().lower()
                acct_id = (row.get('acct_id') or '').strip()
                name = (row.get('name') or '').strip()
                topic = (row.get('topic') or '').strip()
                if not owner_email or not acct_id:
                    skipped += 1
                    continue
                all_rows.append((owner_email, acct_id, name, topic))
            except Exception:
                skipped += 1
                continue

        # Process in batches to reduce DB round-trips and avoid timeouts
        BATCH_SIZE = 200
        for i in range(0, len(all_rows), BATCH_SIZE):
            batch = all_rows[i:i + BATCH_SIZE]
            try:
                emails = [r[0] for r in batch]
                acct_ids = [r[1] for r in batch]

                # Fetch existing creators matching by email (case-insensitive) or acct_id
                existing = (
                    db.query(Creator)
                    .filter(
                        (func.lower(Creator.owner_email).in_(emails)) |
                        (Creator.acct_id.in_(acct_ids))
                    )
                    .all()
                )

                # Build lookup maps
                by_email = {c.owner_email.lower(): c for c in existing}
                by_acct = {c.acct_id: c for c in existing}

                current_time = datetime.utcnow()

                for owner_email, acct_id, name, topic in batch:
                    try:
                        existing_creator = by_email.get(owner_email) or by_acct.get(acct_id)
                        if existing_creator:
                            if name:
                                existing_creator.name = name
                            if topic:
                                existing_creator.topic = topic
                            if existing_creator.acct_id != acct_id:
                                existing_creator.acct_id = acct_id
                            existing_creator.updated_at = current_time
                            upserted += 1
                        else:
                            new_creator = Creator(
                                name=name or '',
                                acct_id=acct_id,
                                owner_email=owner_email,
                                topic=topic or None,
                                created_at=current_time,
                                updated_at=current_time
                            )
                            db.add(new_creator)
                            upserted += 1
                    except Exception:
                        skipped += 1
                        continue

                db.commit()
            except Exception:
                db.rollback()
                # Conservatively mark this whole batch as skipped if a batch-level error occurs
                skipped += len(batch)
                continue

        return {"upserted": upserted, "skipped": skipped}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
