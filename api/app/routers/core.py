from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import Advertiser, Campaign, Insertion, Creator
from app.schemas import (
    AdvertiserIn, AdvertiserOut,
    CampaignIn, CampaignOut,
    InsertionIn, InsertionOut,
    CreatorOut
)
from app.db import get_db

router = APIRouter()


# Advertiser endpoints
@router.post("/advertisers", response_model=AdvertiserOut)
def create_advertiser(advertiser: AdvertiserIn, db: Session = Depends(get_db)):
    db_advertiser = Advertiser(**advertiser.dict())
    db.add(db_advertiser)
    db.commit()
    db.refresh(db_advertiser)
    return db_advertiser


@router.get("/advertisers", response_model=List[AdvertiserOut])
def get_advertisers(db: Session = Depends(get_db)):
    return db.query(Advertiser).all()


# Campaign endpoints
@router.post("/campaigns", response_model=CampaignOut)
def create_campaign(campaign: CampaignIn, db: Session = Depends(get_db)):
    # Verify advertiser exists
    advertiser = db.query(Advertiser).filter(Advertiser.advertiser_id == campaign.advertiser_id).first()
    if not advertiser:
        raise HTTPException(status_code=404, detail="Advertiser not found")
    
    db_campaign = Campaign(**campaign.dict())
    db.add(db_campaign)
    db.commit()
    db.refresh(db_campaign)
    return db_campaign


@router.get("/campaigns", response_model=List[CampaignOut])
def get_campaigns(advertiser_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Campaign)
    if advertiser_id is not None:
        query = query.filter(Campaign.advertiser_id == advertiser_id)
    return query.all()


# Insertion endpoints
@router.post("/insertions", response_model=InsertionOut)
def create_insertion(insertion: InsertionIn, db: Session = Depends(get_db)):
    # Verify campaign exists
    campaign = db.query(Campaign).filter(Campaign.campaign_id == insertion.campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    db_insertion = Insertion(**insertion.dict())
    db.add(db_insertion)
    db.commit()
    db.refresh(db_insertion)
    return db_insertion


@router.get("/insertions", response_model=List[InsertionOut])
def get_insertions(campaign_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Insertion)
    if campaign_id is not None:
        query = query.filter(Insertion.campaign_id == campaign_id)
    return query.all()


# Creator endpoints
@router.get("/creators", response_model=List[CreatorOut])
def get_creators(db: Session = Depends(get_db)):
    return db.query(Creator).all()
