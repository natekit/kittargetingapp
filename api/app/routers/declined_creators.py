from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import csv
import io
from datetime import date
from fastapi.responses import StreamingResponse
from app.models import Creator, DeclinedCreator, Advertiser
from app.db import get_db

router = APIRouter()


@router.get("/declined-creators-csv")
async def download_declined_creators_csv(
    db: Session = Depends(get_db)
):
    """
    Download all declined creators as CSV file.
    """
    print(f"DEBUG: DECLINED CREATORS CSV - Starting download")
    
    try:
        # Get all declined creators with joined data
        # Using explicit column selection to ensure acct_id is included
        declined_creators = db.query(
            DeclinedCreator.declined_id,
            DeclinedCreator.creator_id,
            DeclinedCreator.advertiser_id,
            DeclinedCreator.declined_at,
            DeclinedCreator.reason,
            Creator.name.label("creator_name"),
            Creator.acct_id.label("creator_acct_id"),
            Advertiser.name.label("advertiser_name")
        ).join(
            Creator, Creator.creator_id == DeclinedCreator.creator_id
        ).join(
            Advertiser, Advertiser.advertiser_id == DeclinedCreator.advertiser_id
        ).all()
        
        print(f"DEBUG: Found {len(declined_creators)} declined creators")
        
        # Generate CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header - making sure Account ID is clearly labeled
        writer.writerow([
            'Declined ID', 'Creator ID', 'Account ID', 'Creator Name', 
            'Advertiser Name', 'Declined At', 'Reason'
        ])
        
        # Write declined creator data
        for idx, dc in enumerate(declined_creators):
            # Debug log first few to verify acct_id is present
            if idx < 3:
                print(f"DEBUG: Declined creator {idx+1} - Creator ID: {dc.creator_id}, Account ID: {dc.creator_acct_id}, Name: {dc.creator_name}")
            
            writer.writerow([
                dc.declined_id,
                dc.creator_id,
                dc.creator_acct_id,  # Explicitly use the labeled acct_id
                dc.creator_name,
                dc.advertiser_name,
                dc.declined_at.isoformat() if dc.declined_at else '',
                dc.reason or ''
            ])
        
        csv_content = output.getvalue()
        
        # Return CSV as downloadable file
        return StreamingResponse(
            io.BytesIO(csv_content.encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=declined_creators_{date.today().strftime('%Y%m%d')}.csv"}
        )
        
    except Exception as e:
        print(f"DEBUG: Declined creators CSV error: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating declined creators CSV: {str(e)}")

