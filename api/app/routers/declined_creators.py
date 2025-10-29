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
        declined_creators = db.query(
            DeclinedCreator,
            Creator.name,
            Creator.acct_id,
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
        
        # Write header
        writer.writerow([
            'Declined ID', 'Creator ID', 'Creator Name', 'Account ID', 
            'Advertiser Name', 'Declined At', 'Reason'
        ])
        
        # Write declined creator data
        for dc in declined_creators:
            writer.writerow([
                dc.DeclinedCreator.declined_id,
                dc.DeclinedCreator.creator_id,
                dc.name,
                dc.acct_id,
                dc.advertiser_name,
                dc.DeclinedCreator.declined_at.isoformat() if dc.DeclinedCreator.declined_at else '',
                dc.DeclinedCreator.reason or ''
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

