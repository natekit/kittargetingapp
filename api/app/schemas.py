from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
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


# Analytics schemas
class PlanRequest(BaseModel):
    category: Optional[str] = None
    advertiser_id: Optional[int] = None
    insertion_id: Optional[int] = None
    cpc: Optional[float] = None
    budget: float
    target_cpa: Optional[float] = None
    advertiser_avg_cvr: Optional[float] = None
    horizon_days: int = 30
    # Smart matching fields
    target_age_range: Optional[str] = None
    target_gender_skew: Optional[str] = None
    target_location: Optional[str] = None
    target_interests: Optional[str] = None
    use_smart_matching: bool = True
    # Creator filtering fields
    include_acct_ids: Optional[str] = None
    exclude_acct_ids: Optional[str] = None
    # Email export field
    email: Optional[str] = None


class PlanCreator(BaseModel):
    creator_id: int
    name: str
    acct_id: str
    expected_cvr: float
    expected_cpa: Optional[float] = None
    clicks_per_day: float
    expected_clicks: float
    expected_spend: float
    expected_conversions: float
    value_ratio: float
    recommended_placements: int
    median_clicks_per_placement: Optional[float] = None
    # Smart matching fields
    matching_rationale: Optional[str] = None
    tier: Optional[int] = None
    performance_score: Optional[float] = None
    demographic_score: Optional[float] = None
    topic_score: Optional[float] = None
    similarity_score: Optional[float] = None
    combined_score: Optional[float] = None


class PlanResponse(BaseModel):
    picked_creators: List[PlanCreator]
    total_spend: float
    total_conversions: float
    blended_cpa: float
    budget_utilization: float


class LeaderboardEntry(BaseModel):
    creator_id: int
    name: str
    total_clicks: int
    total_conversions: int
    cvr: float
    cpa: Optional[float]
    cpc: float


class FilterOptions(BaseModel):
    advertisers: List[str]
    categories: List[str]


class HistoricalDataResponse(BaseModel):
    historical_data: List[Dict[str, Any]]
    total_clicks: int
    total_conversions: int
    overall_cvr: float
    start_date: str
    end_date: str


class CampaignForecastRequest(BaseModel):
    advertiser_id: Optional[int] = None
    category: Optional[str] = None
    budget: float
    avg_cpc: float
    lookback_days: int = 30


class CampaignForecastResponse(BaseModel):
    historical_cvr: float
    historical_cpa: Optional[float]
    forecasted_clicks: float
    forecasted_conversions: float
    forecasted_cpa: Optional[float]
    confidence_score: float


# Auth schemas
class UserSignUp(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class UserSignIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    user_id: int
    email: str
    name: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
