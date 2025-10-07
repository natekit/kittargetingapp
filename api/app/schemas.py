from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from decimal import Decimal


class AdvertiserIn(BaseModel):
    name: str
    category: Optional[str] = None


class AdvertiserOut(BaseModel):
    advertiser_id: int
    name: str
    category: Optional[str] = None

    class Config:
        from_attributes = True


class CampaignIn(BaseModel):
    advertiser_id: int
    name: str
    start_date: date
    end_date: date
    notes: Optional[str] = None


class CampaignOut(BaseModel):
    campaign_id: int
    advertiser_id: int
    name: str
    start_date: date
    end_date: date
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class InsertionIn(BaseModel):
    campaign_id: int
    month_start: date
    month_end: date
    cpc: Decimal


class InsertionOut(BaseModel):
    insertion_id: int
    campaign_id: int
    month_start: date
    month_end: date
    cpc: Decimal

    class Config:
        from_attributes = True


class CreatorOut(BaseModel):
    creator_id: int
    name: str
    acct_id: str
    owner_email: str
    topic: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
