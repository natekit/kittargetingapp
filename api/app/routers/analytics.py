from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text, case, and_, or_
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from app.models import Creator, ClickUnique, PerfUpload, Insertion, Campaign, Advertiser, Conversion, ConvUpload
from app.db import get_db

router = APIRouter()


class PlanRequest(BaseModel):
    category: Optional[str] = None
    advertiser_id: Optional[int] = None
    insertion_id: Optional[int] = None
    cpc: Optional[float] = None
    budget: float
    target_cpa: float
    horizon_days: int


class CreatorStats(BaseModel):
    creator_id: int
    name: str
    acct_id: str
    clicks: int
    conversions: int
    cvr: float
    expected_cpa: Optional[float] = None


class PlanCreator(BaseModel):
    creator_id: int
    name: str
    acct_id: str
    expected_cvr: float
    expected_cpa: float
    clicks_per_day: float
    expected_clicks: float
    expected_spend: float
    expected_conversions: float
    value_ratio: float


class PlanResponse(BaseModel):
    picked_creators: List[PlanCreator]
    total_spend: float
    total_conversions: float
    blended_cpa: float
    budget_utilization: float


@router.get("/leaderboard")
async def get_leaderboard(
    category: Optional[str] = Query(None, description="Category filter"),
    limit: int = Query(50, description="Number of results to return"),
    cpc: Optional[float] = Query(None, description="CPC for expected CPA calculation"),
    db: Session = Depends(get_db)
) -> List[CreatorStats]:
    """
    Get creator leaderboard with clicks, conversions, CVR, and optionally expected CPA.
    """
    # Base query for clicks
    clicks_query = db.query(
        Creator.creator_id,
        Creator.name,
        Creator.acct_id,
        func.sum(ClickUnique.unique_clicks).label('clicks')
    ).join(
        ClickUnique, ClickUnique.creator_id == Creator.creator_id
    ).join(
        PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
    ).join(
        Insertion, Insertion.insertion_id == PerfUpload.insertion_id
    ).join(
        Campaign, Campaign.campaign_id == Insertion.campaign_id
    ).join(
        Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
    )
    
    # Add category filter if provided
    if category:
        clicks_query = clicks_query.filter(Advertiser.category == category)
    
    clicks_subquery = clicks_query.group_by(
        Creator.creator_id, Creator.name, Creator.acct_id
    ).subquery()
    
    # Query for conversions
    conversions_query = db.query(
        Creator.creator_id,
        func.sum(Conversion.conversions).label('conversions')
    ).join(
        Conversion, Conversion.creator_id == Creator.creator_id
    ).join(
        ConvUpload, ConvUpload.conv_upload_id == Conversion.conv_upload_id
    )
    
    # Add category filter if provided
    if category:
        conversions_query = conversions_query.join(
            Advertiser, Advertiser.advertiser_id == ConvUpload.advertiser_id
        ).filter(Advertiser.category == category)
    
    conversions_subquery = conversions_query.group_by(Creator.creator_id).subquery()
    
    # Main query joining clicks and conversions
    main_query = db.query(
        clicks_subquery.c.creator_id,
        clicks_subquery.c.name,
        clicks_subquery.c.acct_id,
        func.coalesce(clicks_subquery.c.clicks, 0).label('clicks'),
        func.coalesce(conversions_subquery.c.conversions, 0).label('conversions'),
        case(
            (clicks_subquery.c.clicks > 0, 
             func.coalesce(conversions_subquery.c.conversions, 0) / func.nullif(clicks_subquery.c.clicks, 0)),
            else_=0.0
        ).label('cvr')
    ).outerjoin(
        conversions_subquery, 
        conversions_subquery.c.creator_id == clicks_subquery.c.creator_id
    )
    
    # Add expected CPA if CPC is provided
    if cpc and cpc > 0:
        main_query = main_query.add_columns(
            case(
                (clicks_subquery.c.clicks > 0,
                 cpc / func.nullif(
                     func.coalesce(conversions_subquery.c.conversions, 0) / func.nullif(clicks_subquery.c.clicks, 0),
                     0
                 )),
                else_=None
            ).label('expected_cpa')
        )
        
        # Sort by expected CPA (ascending - lower is better)
        main_query = main_query.order_by('expected_cpa')
    else:
        # Sort by CVR descending
        main_query = main_query.order_by('cvr')
    
    # Apply limit
    results = main_query.limit(limit).all()
    
    # Convert to response format
    leaderboard = []
    for row in results:
        creator_stats = CreatorStats(
            creator_id=row.creator_id,
            name=row.name,
            acct_id=row.acct_id,
            clicks=int(row.clicks),
            conversions=int(row.conversions),
            cvr=float(row.cvr)
        )
        
        if cpc and cpc > 0 and hasattr(row, 'expected_cpa'):
            creator_stats.expected_cpa = float(row.expected_cpa) if row.expected_cpa else None
        
        leaderboard.append(creator_stats)
    
    return leaderboard


@router.post("/plan", response_model=PlanResponse)
async def create_plan(
    plan_request: PlanRequest,
    db: Session = Depends(get_db)
) -> PlanResponse:
    """
    Create a budget allocation plan for creators based on historical performance.
    """
    # Validate inputs
    if not plan_request.category and not plan_request.advertiser_id:
        raise HTTPException(status_code=400, detail="Either category or advertiser_id must be provided")
    
    if not plan_request.insertion_id and not plan_request.cpc:
        raise HTTPException(status_code=400, detail="Either insertion_id or cpc must be provided")
    
    # Get CPC from insertion if not provided
    cpc = plan_request.cpc
    if not cpc and plan_request.insertion_id:
        insertion = db.query(Insertion).filter(Insertion.insertion_id == plan_request.insertion_id).first()
        if not insertion:
            raise HTTPException(status_code=404, detail="Insertion not found")
        cpc = float(insertion.cpc)
    
    # Get creators in category
    creators_query = db.query(Creator)
    if plan_request.category:
        creators_query = creators_query.join(
            ClickUnique, ClickUnique.creator_id == Creator.creator_id
        ).join(
            PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
        ).join(
            Insertion, Insertion.insertion_id == PerfUpload.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).join(
            Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
        ).filter(Advertiser.category == plan_request.category)
    elif plan_request.advertiser_id:
        creators_query = creators_query.join(
            ClickUnique, ClickUnique.creator_id == Creator.creator_id
        ).join(
            PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
        ).join(
            Insertion, Insertion.insertion_id == PerfUpload.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).filter(Campaign.advertiser_id == plan_request.advertiser_id)
    
    creators = creators_query.distinct().all()
    
    if not creators:
        return PlanResponse(
            picked_creators=[],
            total_spend=0.0,
            total_conversions=0.0,
            blended_cpa=0.0,
            budget_utilization=0.0
        )
    
    # Calculate expected CVR for each creator
    creator_stats = []
    global_baseline_cvr = 0.005  # 0.5%
    
    for creator in creators:
        # Get historical clicks and conversions for this creator
        clicks_query = db.query(func.sum(ClickUnique.unique_clicks)).join(
            PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
        ).join(
            Insertion, Insertion.insertion_id == PerfUpload.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).filter(ClickUnique.creator_id == creator.creator_id)
        
        if plan_request.category:
            clicks_query = clicks_query.join(
                Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
            ).filter(Advertiser.category == plan_request.category)
        elif plan_request.advertiser_id:
            clicks_query = clicks_query.filter(Campaign.advertiser_id == plan_request.advertiser_id)
        
        total_clicks = clicks_query.scalar() or 0
        
        conversions_query = db.query(func.sum(Conversion.conversions)).join(
            ConvUpload, ConvUpload.conv_upload_id == Conversion.conv_upload_id
        ).filter(Conversion.creator_id == creator.creator_id)
        
        if plan_request.category:
            conversions_query = conversions_query.join(
                Advertiser, Advertiser.advertiser_id == ConvUpload.advertiser_id
            ).filter(Advertiser.category == plan_request.category)
        elif plan_request.advertiser_id:
            conversions_query = conversions_query.filter(ConvUpload.advertiser_id == plan_request.advertiser_id)
        
        total_conversions = conversions_query.scalar() or 0
        
        # Calculate CVR with fallbacks
        if total_clicks > 0:
            category_cvr = total_conversions / total_clicks
        else:
            # Fallback to overall creator CVR
            overall_clicks = db.query(func.sum(ClickUnique.unique_clicks)).filter(
                ClickUnique.creator_id == creator.creator_id
            ).scalar() or 0
            overall_conversions = db.query(func.sum(Conversion.conversions)).filter(
                Conversion.creator_id == creator.creator_id
            ).scalar() or 0
            
            if overall_clicks > 0:
                category_cvr = overall_conversions / overall_clicks
            else:
                category_cvr = global_baseline_cvr
        
        expected_cvr = max(category_cvr, global_baseline_cvr)
        expected_cpa = cpc / expected_cvr if expected_cvr > 0 else float('inf')
        
        # Filter by target CPA
        if expected_cpa <= plan_request.target_cpa:
            # Calculate historical days (simplified - using 30 days as default)
            historical_days = 30
            clicks_per_day = total_clicks / max(1, historical_days)
            expected_clicks = clicks_per_day * plan_request.horizon_days
            expected_spend = cpc * expected_clicks
            expected_conversions = expected_cvr * expected_clicks
            value_ratio = expected_cvr / cpc if cpc > 0 else 0
            
            creator_stats.append({
                'creator_id': creator.creator_id,
                'name': creator.name,
                'acct_id': creator.acct_id,
                'expected_cvr': expected_cvr,
                'expected_cpa': expected_cpa,
                'clicks_per_day': clicks_per_day,
                'expected_clicks': expected_clicks,
                'expected_spend': expected_spend,
                'expected_conversions': expected_conversions,
                'value_ratio': value_ratio
            })
    
    # Sort by value ratio (descending)
    creator_stats.sort(key=lambda x: x['value_ratio'], reverse=True)
    
    # Greedy allocation
    picked_creators = []
    total_spend = 0.0
    total_conversions = 0.0
    
    for creator_stat in creator_stats:
        if total_spend + creator_stat['expected_spend'] <= plan_request.budget:
            # Can fit full allocation
            picked_creators.append(PlanCreator(**creator_stat))
            total_spend += creator_stat['expected_spend']
            total_conversions += creator_stat['expected_conversions']
        else:
            # Pro-rate the last creator
            remaining_budget = plan_request.budget - total_spend
            if remaining_budget > 0:
                pro_ratio = remaining_budget / creator_stat['expected_spend']
                pro_rated_stat = creator_stat.copy()
                pro_rated_stat['expected_clicks'] *= pro_ratio
                pro_rated_stat['expected_spend'] = remaining_budget
                pro_rated_stat['expected_conversions'] *= pro_ratio
                
                picked_creators.append(PlanCreator(**pro_rated_stat))
                total_spend += remaining_budget
                total_conversions += pro_rated_stat['expected_conversions']
            break
    
    # Calculate blended CPA
    blended_cpa = total_spend / total_conversions if total_conversions > 0 else 0.0
    budget_utilization = total_spend / plan_request.budget if plan_request.budget > 0 else 0.0
    
    return PlanResponse(
        picked_creators=picked_creators,
        total_spend=total_spend,
        total_conversions=total_conversions,
        blended_cpa=blended_cpa,
        budget_utilization=budget_utilization
    )
