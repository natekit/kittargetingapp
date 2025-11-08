from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json
from app.models import Plan, User
from app.schemas import PlanRequest, PlanResponse
from app.db import get_db
from app.routers.auth import get_current_user
from app.routers.analytics import generate_plan_csv
import csv
import io
from datetime import date

router = APIRouter()


class PlanCreateRequest(BaseModel):
    plan_request: Dict[str, Any]  # PlanRequest as dict
    plan_response: Dict[str, Any]  # PlanResponse as dict


class PlanConfirmResponse(BaseModel):
    success: bool
    message: str
    plan_id: int


@router.post("/plans", response_model=Dict[str, Any])
async def create_plan(
    plan_data: PlanCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save a plan to the database."""
    try:
        # Create plan record
        db_plan = Plan(
            user_id=current_user.user_id,
            plan_request=plan_data.plan_request,
            plan_data=plan_data.plan_response,
            status='draft',
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(db_plan)
        db.commit()
        db.refresh(db_plan)
        
        return {
            "plan_id": db_plan.plan_id,
            "status": db_plan.status,
            "created_at": db_plan.created_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        print(f"DEBUG: Error creating plan: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving plan: {str(e)}")


@router.put("/plans/{plan_id}/confirm", response_model=PlanConfirmResponse)
async def confirm_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm a plan and send email notification to team."""
    try:
        # Get plan
        plan = db.query(Plan).filter(
            Plan.plan_id == plan_id,
            Plan.user_id == current_user.user_id
        ).first()
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        if plan.status == 'confirmed':
            return PlanConfirmResponse(
                success=True,
                message="Plan already confirmed",
                plan_id=plan_id
            )
        
        # Update plan status
        plan.status = 'confirmed'
        plan.confirmed_at = datetime.now(timezone.utc)
        plan.updated_at = datetime.now(timezone.utc)
        db.commit()
        
        # Generate plan data for email
        # Convert dict to PlanResponse and PlanRequest objects
        from app.schemas import PlanCreator
        
        # Convert plan_data dict to PlanResponse
        plan_data_dict = plan.plan_data
        picked_creators = [
            PlanCreator(**creator_data) 
            for creator_data in plan_data_dict.get('picked_creators', [])
        ]
        plan_response = PlanResponse(
            picked_creators=picked_creators,
            total_spend=plan_data_dict.get('total_spend', 0),
            total_conversions=plan_data_dict.get('total_conversions', 0),
            blended_cpa=plan_data_dict.get('blended_cpa', 0),
            budget_utilization=plan_data_dict.get('budget_utilization', 0)
        )
        
        # Convert plan_request dict to PlanRequest
        plan_request = PlanRequest(**plan.plan_request)
        
        # Generate CSV
        csv_content = generate_plan_csv(plan_response, plan_request)
        
        # Send email to nate@kit.com
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders
            from datetime import date
            import os
            
            # Check if email sending is enabled
            email_enabled = os.getenv('EMAIL_SENDING_ENABLED', 'false').lower() == 'true'
            
            if not email_enabled:
                print(f"DEBUG: Email sending disabled - would send confirmation to nate@kit.com")
                print(f"DEBUG: To enable email sending, set EMAIL_SENDING_ENABLED=true")
            else:
                # Get SMTP credentials
                smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
                smtp_port = int(os.getenv('SMTP_PORT', '587'))
                smtp_username = os.getenv('SMTP_USERNAME')
                smtp_password = os.getenv('SMTP_PASSWORD')
                
                if not smtp_username or not smtp_password:
                    print(f"DEBUG: SMTP credentials not configured - would send to nate@kit.com")
                    print(f"DEBUG: Set SMTP_USERNAME and SMTP_PASSWORD environment variables")
                else:
                    # Create email
                    msg = MIMEMultipart()
                    msg['From'] = smtp_username
                    msg['To'] = 'nate@kit.com'
                    msg['Subject'] = f"New Campaign Confirmed - {current_user.email}"
                    
                    # Email body
                    body = f"""
A new campaign has been confirmed!

Advertiser Information:
- Email: {current_user.email}
- Name: {current_user.name or 'Not provided'}
- User ID: {current_user.user_id}

Campaign Details:
- Budget: ${plan_request.budget:.2f}
- Category: {plan_request.category or 'N/A'}
- CPC: ${plan_request.cpc or 'N/A'}
- Target CPA: ${plan_request.target_cpa or 'Not specified'}
- Horizon Days: {plan_request.horizon_days}

Plan Summary:
- Total Spend: ${plan_response.total_spend:.2f}
- Total Conversions: {plan_response.total_conversions:.2f}
- Blended CPA: ${plan_response.blended_cpa:.2f}
- Budget Utilization: {plan_response.budget_utilization:.2%}
- Number of Creators: {len(plan_response.picked_creators)}
- Plan ID: {plan_id}

Please find the detailed plan attached as a CSV file.

Best regards,
Kit Targeting System
                    """
                    
                    msg.attach(MIMEText(body, 'plain'))
                    
                    # Attach CSV
                    attachment = MIMEBase('application', 'octet-stream')
                    attachment.set_payload(csv_content.encode())
                    encoders.encode_base64(attachment)
                    attachment.add_header(
                        'Content-Disposition',
                        f'attachment; filename=campaign_plan_{plan_id}_{date.today().strftime("%Y%m%d")}.csv'
                    )
                    msg.attach(attachment)
                    
                    # Send email
                    print(f"DEBUG: Sending confirmation email to {recipient_email}")
                    server = smtplib.SMTP(smtp_server, smtp_port)
                    server.starttls()
                    server.login(smtp_username, smtp_password)
                    server.send_message(msg)
                    server.quit()
                    print(f"DEBUG: Confirmation email sent successfully to {recipient_email}")
                    print(f"DEBUG: Email subject: {msg['Subject']}")
                    print(f"DEBUG: CSV attachment size: {len(csv_content)} characters")
        except Exception as e:
            print(f"DEBUG: Error sending confirmation email: {e}")
            import traceback
            print(f"DEBUG: Email error traceback: {traceback.format_exc()}")
            # Don't fail the confirmation if email fails
            # The plan is still confirmed in the database
            # But log the error so we know email didn't send
        
        return PlanConfirmResponse(
            success=True,
            message="Campaign confirmed! Our team will set up your campaign shortly.",
            plan_id=plan_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"DEBUG: Error confirming plan: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error confirming plan: {str(e)}")


@router.get("/plans", response_model=List[Dict[str, Any]])
async def get_user_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all plans for the current user."""
    plans = db.query(Plan).filter(
        Plan.user_id == current_user.user_id
    ).order_by(Plan.created_at.desc()).all()
    
    return [
        {
            "plan_id": plan.plan_id,
            "status": plan.status,
            "created_at": plan.created_at.isoformat(),
            "confirmed_at": plan.confirmed_at.isoformat() if plan.confirmed_at else None,
            "budget": plan.plan_request.get("budget"),
            "total_spend": plan.plan_data.get("total_spend"),
            "total_conversions": plan.plan_data.get("total_conversions"),
            "blended_cpa": plan.plan_data.get("blended_cpa"),
            "creator_count": len(plan.plan_data.get("picked_creators", []))
        }
        for plan in plans
    ]


@router.get("/plans/{plan_id}", response_model=Dict[str, Any])
async def get_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific plan by ID."""
    plan = db.query(Plan).filter(
        Plan.plan_id == plan_id,
        Plan.user_id == current_user.user_id
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    return {
        "plan_id": plan.plan_id,
        "status": plan.status,
        "created_at": plan.created_at.isoformat(),
        "confirmed_at": plan.confirmed_at.isoformat() if plan.confirmed_at else None,
        "plan_request": plan.plan_request,
        "plan_data": plan.plan_data
    }

