from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text, case, and_, or_, desc
from typing import Dict, Any, List, Optional
import logging
from pydantic import BaseModel
from datetime import date, timedelta
from app.models import Creator, ClickUnique, PerfUpload, Insertion, Campaign, Advertiser, Conversion, ConvUpload, DeclinedCreator, Placement
from app.smart_matching import SmartMatchingService
from app.db import get_db

router = APIRouter()


class PlanRequest(BaseModel):
    category: Optional[str] = None
    advertiser_id: Optional[int] = None
    insertion_id: Optional[int] = None
    cpc: Optional[float] = None
    budget: float
    target_cpa: Optional[float] = None
    advertiser_avg_cvr: Optional[float] = None
    horizon_days: int
    # New smart matching fields
    target_age_range: Optional[str] = None
    target_gender_skew: Optional[str] = None
    target_location: Optional[str] = None
    target_interests: Optional[str] = None
    use_smart_matching: bool = True
    # Creator filtering fields
    include_acct_ids: Optional[str] = None  # Comma-separated list of Acct IDs to include
    exclude_acct_ids: Optional[str] = None  # Comma-separated list of Acct IDs to exclude


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


@router.get("/declined-creators/{advertiser_id}")
async def get_declined_creators(
    advertiser_id: int,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Get all creators who have declined to work with a specific advertiser.
    """
    declined_creators = db.query(
        DeclinedCreator,
        Creator.name,
        Creator.acct_id,
        Advertiser.name.label("advertiser_name")
    ).join(
        Creator, Creator.creator_id == DeclinedCreator.creator_id
    ).join(
        Advertiser, Advertiser.advertiser_id == DeclinedCreator.advertiser_id
    ).filter(
        DeclinedCreator.advertiser_id == advertiser_id
    ).all()
    
    return [
        {
            "declined_id": dc.DeclinedCreator.declined_id,
            "creator_id": dc.DeclinedCreator.creator_id,
            "creator_name": dc.name,
            "acct_id": dc.acct_id,
            "advertiser_name": dc.advertiser_name,
            "declined_at": dc.DeclinedCreator.declined_at,
            "reason": dc.DeclinedCreator.reason
        }
        for dc in declined_creators
    ]


@router.get("/filter-options")
async def get_filter_options(db: Session = Depends(get_db)) -> Dict[str, List[str]]:
    """
    Get available filter options for leaderboard dropdowns.
    """
    # Get advertiser categories
    advertiser_categories = db.query(Advertiser.category).filter(
        Advertiser.category.isnot(None)
    ).distinct().all()
    
    # Get creator topics
    creator_topics = db.query(Creator.topic).filter(
        Creator.topic.isnot(None)
    ).distinct().all()
    
    topics_list = [topic[0] for topic in creator_topics if topic[0]]
    print(f"DEBUG: Available creator topics: {topics_list}")
    
    return {
        "advertiser_categories": [cat[0] for cat in advertiser_categories if cat[0]],
        "creator_topics": topics_list
    }


@router.get("/leaderboard")
async def get_leaderboard(
    advertiser_category: Optional[str] = Query(None, description="Advertiser category filter"),
    creator_topic: Optional[str] = Query(None, description="Creator topic filter"),
    limit: int = Query(50, description="Number of results to return"),
    cpc: Optional[float] = Query(None, description="CPC for expected CPA calculation"),
    db: Session = Depends(get_db)
) -> List[CreatorStats]:
    """
    Get creator leaderboard with clicks, conversions, CVR, and optionally expected CPA.
    """
    print(f"DEBUG: LEADERBOARD - Starting calculation with filters: advertiser_category={advertiser_category}, creator_topic={creator_topic}")
    
    # Base query for total clicks
    clicks_query = db.query(
        Creator.creator_id,
        Creator.name,
        Creator.acct_id,
        func.sum(ClickUnique.unique_clicks).label('total_clicks')
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
    
    # Add advertiser category filter if provided
    if advertiser_category:
        print(f"DEBUG: LEADERBOARD - Adding advertiser category filter: {advertiser_category}")
        clicks_query = clicks_query.filter(Advertiser.category == advertiser_category)
    
    # Add creator topic filter if provided
    if creator_topic:
        print(f"DEBUG: LEADERBOARD - Adding creator topic filter: {creator_topic}")
        clicks_query = clicks_query.filter(Creator.topic == creator_topic)
    
    # Debug: Print the SQL query for clicks
    print(f"DEBUG: LEADERBOARD - Clicks query SQL: {clicks_query}")
    
    clicks_subquery = clicks_query.group_by(
        Creator.creator_id, Creator.name, Creator.acct_id
    ).subquery()
    
    print(f"DEBUG: LEADERBOARD - Clicks subquery created")
    
    # Query for conversions
    conversions_query = db.query(
        Creator.creator_id,
        func.sum(Conversion.conversions).label('conversions')
    ).join(
        Conversion, Conversion.creator_id == Creator.creator_id
    ).join(
        ConvUpload, ConvUpload.conv_upload_id == Conversion.conv_upload_id
    )
    
    # Add advertiser category filter if provided
    if advertiser_category:
        print(f"DEBUG: LEADERBOARD - Adding advertiser category filter to conversions: {advertiser_category}")
        conversions_query = conversions_query.join(
            Advertiser, Advertiser.advertiser_id == ConvUpload.advertiser_id
        ).filter(Advertiser.category == advertiser_category)
    
    # Add creator topic filter if provided
    if creator_topic:
        print(f"DEBUG: LEADERBOARD - Adding creator topic filter to conversions: {creator_topic}")
        conversions_query = conversions_query.filter(Creator.topic == creator_topic)
    
    # Debug: Print the SQL query for conversions
    print(f"DEBUG: LEADERBOARD - Conversions query SQL: {conversions_query}")
    
    conversions_subquery = conversions_query.group_by(Creator.creator_id).subquery()
    
    print(f"DEBUG: LEADERBOARD - Conversions subquery created")
    
    # Main query joining clicks and conversions
    main_query = db.query(
        clicks_subquery.c.creator_id,
        clicks_subquery.c.name,
        clicks_subquery.c.acct_id,
        func.coalesce(clicks_subquery.c.total_clicks, 0).label('clicks'),
        func.coalesce(conversions_subquery.c.conversions, 0).label('conversions'),
        case(
            (clicks_subquery.c.total_clicks > 0, 
             func.coalesce(conversions_subquery.c.conversions, 0) / func.nullif(clicks_subquery.c.total_clicks, 0)),
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
                (clicks_subquery.c.total_clicks > 0,
                 cpc / func.nullif(
                     func.coalesce(conversions_subquery.c.conversions, 0) / func.nullif(clicks_subquery.c.total_clicks, 0),
                     0
                 )),
                else_=None
            ).label('expected_cpa')
        )
        
        # Sort by expected CPA (ascending - lower is better)
        main_query = main_query.order_by('expected_cpa')
    else:
        # Sort by CVR descending (highest CVR first)
        main_query = main_query.order_by(desc('cvr'))
    
    # Debug: Print the final SQL query
    print(f"DEBUG: LEADERBOARD - Final query SQL: {main_query}")
    
    # Apply limit
    results = main_query.limit(limit).all()
    print(f"DEBUG: LEADERBOARD - Found {len(results)} results")
    
    # Convert to response format
    leaderboard = []
    for i, row in enumerate(results):
        print(f"DEBUG: LEADERBOARD - Creator {i+1}: {row.name} (ID: {row.creator_id})")
        print(f"  - Total clicks: {row.clicks}")
        print(f"  - Conversions: {row.conversions}")
        print(f"  - CVR: {row.cvr:.4f}")
        if hasattr(row, 'expected_cpa') and row.expected_cpa:
            print(f"  - Expected CPA: {row.expected_cpa:.2f}")
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
    print(f"DEBUG: Planner request received: {plan_request}")
    
    # Validate inputs
    if not plan_request.category and not plan_request.advertiser_id:
        print("DEBUG: Validation failed - no category or advertiser_id provided")
        raise HTTPException(status_code=400, detail="Either category or advertiser_id must be provided")
    
    if not plan_request.insertion_id and not plan_request.cpc:
        print("DEBUG: Validation failed - no insertion_id or cpc provided")
        raise HTTPException(status_code=400, detail="Either insertion_id or cpc must be provided")
    
    if plan_request.budget <= 0:
        print(f"DEBUG: Validation failed - invalid budget: {plan_request.budget}")
        raise HTTPException(status_code=400, detail="Budget must be greater than 0")
    
    if plan_request.target_cpa is not None and plan_request.target_cpa <= 0:
        print(f"DEBUG: Validation failed - invalid target_cpa: {plan_request.target_cpa}")
        raise HTTPException(status_code=400, detail="Target CPA must be greater than 0")
    
    if plan_request.horizon_days <= 0:
        print(f"DEBUG: Validation failed - invalid horizon_days: {plan_request.horizon_days}")
        raise HTTPException(status_code=400, detail="Horizon days must be greater than 0")
    
    if plan_request.advertiser_avg_cvr is not None and (plan_request.advertiser_avg_cvr <= 0 or plan_request.advertiser_avg_cvr >= 1):
        print(f"DEBUG: Validation failed - invalid advertiser_avg_cvr: {plan_request.advertiser_avg_cvr}")
        raise HTTPException(status_code=400, detail="Advertiser average CVR must be between 0 and 1")
    
    print("DEBUG: Input validation passed")
    
    # Get CPC from insertion if not provided
    cpc = plan_request.cpc
    if not cpc and plan_request.insertion_id:
        print(f"DEBUG: Looking up CPC for insertion_id: {plan_request.insertion_id}")
        insertion = db.query(Insertion).filter(Insertion.insertion_id == plan_request.insertion_id).first()
        if not insertion:
            print(f"DEBUG: Insertion not found for insertion_id: {plan_request.insertion_id}")
            raise HTTPException(status_code=404, detail="Insertion not found")
        cpc = float(insertion.cpc)
        print(f"DEBUG: Found CPC from insertion: {cpc}")
    else:
        print(f"DEBUG: Using provided CPC: {cpc}")
    
    # Get creators in category
    print("DEBUG: Starting creator query")
    creators_query = db.query(Creator)
    if plan_request.category:
        print(f"DEBUG: Filtering by category: {plan_request.category}")
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
        logging.info(f"Planning for category: {plan_request.category}")
    elif plan_request.advertiser_id:
        print(f"DEBUG: Filtering by advertiser_id: {plan_request.advertiser_id}")
        creators_query = creators_query.join(
            ClickUnique, ClickUnique.creator_id == Creator.creator_id
        ).join(
            PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
        ).join(
            Insertion, Insertion.insertion_id == PerfUpload.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).filter(Campaign.advertiser_id == plan_request.advertiser_id)
        logging.info(f"Planning for advertiser_id: {plan_request.advertiser_id}")
    
    print("DEBUG: Executing creator query")
    creators = creators_query.distinct().all()
    print(f"DEBUG: Found {len(creators)} creators for planning")
    logging.info(f"Found {len(creators)} creators for planning")
    
    # Apply creator filtering based on Acct IDs
    if plan_request.include_acct_ids or plan_request.exclude_acct_ids:
        print("DEBUG: Applying creator filtering")
        
        # Parse include Acct IDs (additive - ensure these creators are included)
        include_acct_ids = set()
        if plan_request.include_acct_ids:
            include_acct_ids = {acct_id.strip() for acct_id in plan_request.include_acct_ids.split(',') if acct_id.strip()}
            print(f"DEBUG: Include Acct IDs (additive): {include_acct_ids}")
        
        # Parse exclude Acct IDs (restrictive - exclude these creators)
        exclude_acct_ids = set()
        if plan_request.exclude_acct_ids:
            exclude_acct_ids = {acct_id.strip() for acct_id in plan_request.exclude_acct_ids.split(',') if acct_id.strip()}
            print(f"DEBUG: Exclude Acct IDs: {exclude_acct_ids}")
        
        # First, filter out excluded creators
        filtered_creators = []
        for creator in creators:
            creator_acct_id = creator.acct_id.strip()
            
            # If exclude list is specified, exclude creators in that list
            if exclude_acct_ids and creator_acct_id in exclude_acct_ids:
                print(f"DEBUG: Excluding creator {creator.name} (Acct ID: {creator_acct_id}) - in exclude list")
                continue
            
            filtered_creators.append(creator)
            print(f"DEBUG: Including creator {creator.name} (Acct ID: {creator_acct_id})")
        
        # If include list is specified, ensure those creators are added even if not in filtered list
        if include_acct_ids:
            print("DEBUG: Adding required creators from include list")
            for creator in creators:
                creator_acct_id = creator.acct_id.strip()
                if creator_acct_id in include_acct_ids:
                    # Check if already in filtered list
                    if not any(c.creator_id == creator.creator_id for c in filtered_creators):
                        filtered_creators.append(creator)
                        print(f"DEBUG: Added required creator {creator.name} (Acct ID: {creator_acct_id})")
        
        creators = filtered_creators
        print(f"DEBUG: After filtering: {len(creators)} creators remaining")
        logging.info(f"After creator filtering: {len(creators)} creators remaining")
    
    # Filter out declined creators for this advertiser
    if plan_request.advertiser_id:
        print(f"DEBUG: Filtering declined creators for advertiser_id: {plan_request.advertiser_id}")
        declined_creator_ids = db.query(DeclinedCreator.creator_id).filter(
            DeclinedCreator.advertiser_id == plan_request.advertiser_id
        ).all()
        declined_ids = [dc[0] for dc in declined_creator_ids]
        print(f"DEBUG: Found {len(declined_ids)} declined creators: {declined_ids}")
        creators = [c for c in creators if c.creator_id not in declined_ids]
        print(f"DEBUG: After filtering declined creators: {len(creators)} creators remaining")
        logging.info(f"After filtering declined creators: {len(creators)} creators remaining")
    
    if not creators:
        print("DEBUG: No creators found - returning empty plan")
        return PlanResponse(
            picked_creators=[],
            total_spend=0.0,
            total_conversions=0.0,
            blended_cpa=0.0,
            budget_utilization=0.0
        )
    
    # Calculate expected CVR for each creator
    print("DEBUG: Starting creator stats calculation")
    creator_stats = []
    global_baseline_cvr = 0.005  # 0.5%
    
    # Use advertiser average CVR if provided, otherwise use global baseline
    advertiser_cvr = plan_request.advertiser_avg_cvr if plan_request.advertiser_avg_cvr is not None else global_baseline_cvr
    print(f"DEBUG: Using advertiser_cvr: {advertiser_cvr}")
    
    for creator_index, creator in enumerate(creators):
        print(f"DEBUG: Processing creator {creator_index + 1}/{len(creators)}: {creator.name} (ID: {creator.creator_id})")
        # STEP 1: Get click estimates (historical or conservative)
        print(f"DEBUG: PLANNING - Creator {creator_index + 1} ({creator.name}) - Getting click estimates")
        clicks_query = db.query(func.sum(ClickUnique.unique_clicks)).join(
            PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
        ).join(
            Insertion, Insertion.insertion_id == PerfUpload.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).filter(ClickUnique.creator_id == creator.creator_id)
        
        if plan_request.category:
            print(f"DEBUG: PLANNING - Adding category filter: {plan_request.category}")
            clicks_query = clicks_query.join(
                Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
            ).filter(Advertiser.category == plan_request.category)
        elif plan_request.advertiser_id:
            print(f"DEBUG: PLANNING - Adding advertiser filter: {plan_request.advertiser_id}")
            clicks_query = clicks_query.filter(Campaign.advertiser_id == plan_request.advertiser_id)
        
        print(f"DEBUG: PLANNING - Clicks query SQL: {clicks_query}")
        total_clicks = clicks_query.scalar() or 0
        print(f"DEBUG: PLANNING - Creator {creator_index + 1} - Total clicks: {total_clicks}")
        
        # If no historical clicks, use conservative estimate
        if total_clicks == 0:
            print(f"DEBUG: Creator {creator_index + 1} - No historical clicks, checking conservative estimate")
            if creator.conservative_click_estimate:
                total_clicks = creator.conservative_click_estimate
                print(f"DEBUG: Creator {creator_index + 1} - Using conservative estimate: {total_clicks}")
            else:
                print(f"DEBUG: Creator {creator_index + 1} - No clicks and no estimate - excluding creator")
                # No clicks and no estimate - exclude this creator
                continue
        
        # STEP 2: Get CVR estimates (historical or fallback)
        print(f"DEBUG: PLANNING - Creator {creator_index + 1} - Getting conversion estimates")
        conversions_query = db.query(func.sum(Conversion.conversions)).join(
            ConvUpload, ConvUpload.conv_upload_id == Conversion.conv_upload_id
        ).filter(Conversion.creator_id == creator.creator_id)
        
        if plan_request.category:
            print(f"DEBUG: PLANNING - Adding category filter to conversions: {plan_request.category}")
            conversions_query = conversions_query.join(
                Advertiser, Advertiser.advertiser_id == ConvUpload.advertiser_id
            ).filter(Advertiser.category == plan_request.category)
        elif plan_request.advertiser_id:
            print(f"DEBUG: PLANNING - Adding advertiser filter to conversions: {plan_request.advertiser_id}")
            conversions_query = conversions_query.filter(ConvUpload.advertiser_id == plan_request.advertiser_id)
        
        print(f"DEBUG: PLANNING - Conversions query SQL: {conversions_query}")
        total_conversions = conversions_query.scalar() or 0
        print(f"DEBUG: PLANNING - Creator {creator_index + 1} - Total conversions: {total_conversions}")
        
        # Calculate CVR with proper fallbacks
        if total_clicks > 0 and total_conversions > 0:
            # Use historical CVR
            expected_cvr = total_conversions / total_clicks
            print(f"DEBUG: Creator {creator_index + 1} - Using historical CVR: {expected_cvr}")
        else:
            print(f"DEBUG: Creator {creator_index + 1} - No historical CVR, checking overall creator CVR")
            # Fallback to overall creator CVR
            overall_clicks = db.query(func.sum(ClickUnique.unique_clicks)).filter(
                ClickUnique.creator_id == creator.creator_id
            ).scalar() or 0
            overall_conversions = db.query(func.sum(Conversion.conversions)).filter(
                Conversion.creator_id == creator.creator_id
            ).scalar() or 0
            
            print(f"DEBUG: Creator {creator_index + 1} - Overall clicks: {overall_clicks}, conversions: {overall_conversions}")
            
            if overall_clicks > 0 and overall_conversions > 0:
                expected_cvr = overall_conversions / overall_clicks
                print(f"DEBUG: Creator {creator_index + 1} - Using overall CVR: {expected_cvr}")
            else:
                # Use advertiser CVR or global baseline
                expected_cvr = advertiser_cvr
                print(f"DEBUG: Creator {creator_index + 1} - Using fallback CVR: {expected_cvr}")
        expected_cpa = cpc / expected_cvr if expected_cvr > 0 else float('inf')
        print(f"DEBUG: Creator {creator_index + 1} - Expected CPA: {expected_cpa}")
        
        # Filter by target CPA (if provided)
        if plan_request.target_cpa is None or expected_cpa <= plan_request.target_cpa:
            print(f"DEBUG: Creator {creator_index + 1} - Passes CPA filter (target: {plan_request.target_cpa}, expected: {expected_cpa})")
            # Calculate actual historical days from data
            historical_days_query = db.query(
                func.max(ClickUnique.execution_date) - func.min(ClickUnique.execution_date)
            ).filter(ClickUnique.creator_id == creator.creator_id)
            
            if plan_request.category:
                historical_days_query = historical_days_query.join(
                    PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
                ).join(
                    Insertion, Insertion.insertion_id == PerfUpload.insertion_id
                ).join(
                    Campaign, Campaign.campaign_id == Insertion.campaign_id
                ).join(
                    Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
                ).filter(Advertiser.category == plan_request.category)
            elif plan_request.advertiser_id:
                historical_days_query = historical_days_query.join(
                    PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
                ).join(
                    Insertion, Insertion.insertion_id == PerfUpload.insertion_id
                ).join(
                    Campaign, Campaign.campaign_id == Insertion.campaign_id
                ).filter(Campaign.advertiser_id == plan_request.advertiser_id)
            
            historical_days = historical_days_query.scalar()
            if historical_days:
                historical_days = max(1, historical_days)
            else:
                historical_days = 30  # Fallback to 30 days if no data
            
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
        else:
            print(f"DEBUG: Creator {creator_index + 1} - FAILED CPA filter (target: {plan_request.target_cpa}, expected: {expected_cpa}) - EXCLUDING")
            continue
    
    # Sort by value ratio (descending) or CVR if no CPA target
    print(f"DEBUG: Sorting {len(creator_stats)} creator stats")
    if plan_request.target_cpa is None:
        # When no CPA target, prioritize by CVR
        creator_stats.sort(key=lambda x: x['expected_cvr'], reverse=True)
        print("DEBUG: Sorted by CVR (descending)")
    else:
        # When CPA target exists, prioritize by value ratio
        creator_stats.sort(key=lambda x: x['value_ratio'], reverse=True)
        print("DEBUG: Sorted by value ratio (descending)")
    
    # Greedy allocation
    print("DEBUG: Starting greedy allocation")
    picked_creators = []
    total_spend = 0.0
    total_conversions = 0.0
    
    for alloc_index, creator_stat in enumerate(creator_stats):
        print(f"DEBUG: Allocation {alloc_index + 1}/{len(creator_stats)} - {creator_stat['name']} (spend: {creator_stat['expected_spend']}, current total: {total_spend}, budget: {plan_request.budget})")
        if total_spend + creator_stat['expected_spend'] <= plan_request.budget:
            # Can fit full allocation
            print(f"DEBUG: Adding full allocation for {creator_stat['name']}")
            picked_creators.append(PlanCreator(**creator_stat))
            total_spend += creator_stat['expected_spend']
            total_conversions += creator_stat['expected_conversions']
        else:
            # Pro-rate the last creator
            remaining_budget = plan_request.budget - total_spend
            print(f"DEBUG: Pro-rating {creator_stat['name']} - remaining budget: {remaining_budget}")
            if remaining_budget > 0:
                pro_ratio = remaining_budget / creator_stat['expected_spend']
                pro_rated_stat = creator_stat.copy()
                pro_rated_stat['expected_clicks'] *= pro_ratio
                pro_rated_stat['expected_spend'] = remaining_budget
                pro_rated_stat['expected_conversions'] *= pro_ratio
                
                print(f"DEBUG: Pro-rated spend: {pro_rated_stat['expected_spend']}, conversions: {pro_rated_stat['expected_conversions']}")
                picked_creators.append(PlanCreator(**pro_rated_stat))
                total_spend += remaining_budget
                total_conversions += pro_rated_stat['expected_conversions']
            break
    
    # Calculate blended CPA
    blended_cpa = total_spend / total_conversions if total_conversions > 0 else 0.0
    budget_utilization = total_spend / plan_request.budget if plan_request.budget > 0 else 0.0
    
    print(f"DEBUG: Final results - {len(picked_creators)} creators, ${total_spend:.2f} spend, {total_conversions:.2f} conversions, ${blended_cpa:.2f} CPA, {budget_utilization:.2%} utilization")
    
    return PlanResponse(
        picked_creators=picked_creators,
        total_spend=total_spend,
        total_conversions=total_conversions,
        blended_cpa=blended_cpa,
        budget_utilization=budget_utilization
    )


@router.post("/plan-smart", response_model=PlanResponse)
async def create_smart_plan(
    plan_request: PlanRequest,
    db: Session = Depends(get_db)
) -> PlanResponse:
    """
    Create a smart budget allocation plan using multi-tier creator selection.
    """
    print(f"DEBUG: Smart planner request received: {plan_request}")
    
    # Validate inputs (same as original)
    if not plan_request.category and not plan_request.advertiser_id:
        print("DEBUG: Validation failed - no category or advertiser_id provided")
        raise HTTPException(status_code=400, detail="Either category or advertiser_id must be provided")
    
    if not plan_request.insertion_id and not plan_request.cpc:
        print("DEBUG: Validation failed - no insertion_id or cpc provided")
        raise HTTPException(status_code=400, detail="Either insertion_id or cpc must be provided")
    
    if plan_request.budget <= 0:
        print(f"DEBUG: Validation failed - invalid budget: {plan_request.budget}")
        raise HTTPException(status_code=400, detail="Budget must be greater than 0")
    
    if plan_request.target_cpa is not None and plan_request.target_cpa <= 0:
        print(f"DEBUG: Validation failed - invalid target_cpa: {plan_request.target_cpa}")
        raise HTTPException(status_code=400, detail="Target CPA must be greater than 0")
    
    if plan_request.horizon_days <= 0:
        print(f"DEBUG: Validation failed - invalid horizon_days: {plan_request.horizon_days}")
        raise HTTPException(status_code=400, detail="Horizon days must be greater than 0")
    
    if plan_request.advertiser_avg_cvr is not None and (plan_request.advertiser_avg_cvr <= 0 or plan_request.advertiser_avg_cvr >= 1):
        print(f"DEBUG: Validation failed - invalid advertiser_avg_cvr: {plan_request.advertiser_avg_cvr}")
        raise HTTPException(status_code=400, detail="Advertiser average CVR must be between 0 and 1")
    
    print("DEBUG: Input validation passed")
    
    # Get CPC from insertion if not provided
    cpc = plan_request.cpc
    if not cpc and plan_request.insertion_id:
        print(f"DEBUG: Looking up CPC for insertion_id: {plan_request.insertion_id}")
        insertion = db.query(Insertion).filter(Insertion.insertion_id == plan_request.insertion_id).first()
        if not insertion:
            print(f"DEBUG: Insertion not found for insertion_id: {plan_request.insertion_id}")
            raise HTTPException(status_code=404, detail="Insertion not found")
        cpc = float(insertion.cpc)
        print(f"DEBUG: Found CPC from insertion: {cpc}")
    else:
        print(f"DEBUG: Using provided CPC: {cpc}")
    
    # Prepare target demographics
    target_demographics = None
    if plan_request.target_age_range or plan_request.target_gender_skew or plan_request.target_location or plan_request.target_interests:
        target_demographics = {
            'target_age_range': plan_request.target_age_range,
            'target_gender_skew': plan_request.target_gender_skew,
            'target_location': plan_request.target_location,
            'target_interests': plan_request.target_interests
        }
        print(f"DEBUG: Using target demographics: {target_demographics}")
    
    # Use smart matching service
    smart_service = SmartMatchingService(db)
    
    try:
        print("DEBUG: Starting smart matching algorithm")
        matched_creators = smart_service.find_smart_creators(
            advertiser_id=plan_request.advertiser_id,
            category=plan_request.category,
            target_demographics=target_demographics,
            budget=plan_request.budget,
            cpc=cpc,
            target_cpa=plan_request.target_cpa,
            horizon_days=plan_request.horizon_days,
            advertiser_avg_cvr=plan_request.advertiser_avg_cvr or 0.06,
            include_acct_ids=plan_request.include_acct_ids,
            exclude_acct_ids=plan_request.exclude_acct_ids
        )
        
        print(f"DEBUG: Smart matching found {len(matched_creators)} creators")
        
        if not matched_creators:
            print("DEBUG: No creators found - returning empty plan")
            return PlanResponse(
                picked_creators=[],
                total_spend=0.0,
                total_conversions=0.0,
                blended_cpa=0.0,
                budget_utilization=0.0
            )
        
        # Convert to PlanCreator format and allocate budget
        picked_creators = []
        total_spend = 0.0
        total_conversions = 0.0
        
        for creator_data in matched_creators:
            creator = creator_data['creator']
            performance_data = creator_data['performance_data']
            
            # Calculate expected metrics
            expected_clicks = performance_data.get('expected_clicks', 100)
            expected_spend = cpc * expected_clicks
            expected_conversions = performance_data.get('expected_conversions', 10)
            
            # Check if we can fit this creator in budget
            if total_spend + expected_spend <= plan_request.budget:
                # Full allocation
                picked_creators.append(PlanCreator(
                    creator_id=creator.creator_id,
                    name=creator.name,
                    acct_id=creator.acct_id,
                    expected_cvr=performance_data.get('expected_cvr', 0.06),
                    expected_cpa=performance_data.get('expected_cpa', 10.0),
                    clicks_per_day=expected_clicks / plan_request.horizon_days,
                    expected_clicks=expected_clicks,
                    expected_spend=expected_spend,
                    expected_conversions=expected_conversions,
                    value_ratio=creator_data['combined_score'],
                    recommended_placements=performance_data.get('recommended_placements', 1),
                    median_clicks_per_placement=performance_data.get('median_clicks_per_placement')
                ))
                total_spend += expected_spend
                total_conversions += expected_conversions
                print(f"DEBUG: Added creator {creator.name} - spend: ${expected_spend:.2f}, rationale: {creator_data['matching_rationale']}")
            else:
                # Pro-rate the last creator
                remaining_budget = plan_request.budget - total_spend
                if remaining_budget > 0:
                    pro_ratio = remaining_budget / expected_spend
                    pro_rated_clicks = expected_clicks * pro_ratio
                    pro_rated_conversions = expected_conversions * pro_ratio
                    
                    picked_creators.append(PlanCreator(
                        creator_id=creator.creator_id,
                        name=creator.name,
                        acct_id=creator.acct_id,
                        expected_cvr=performance_data.get('expected_cvr', 0.06),
                        expected_cpa=performance_data.get('expected_cpa', 10.0),
                        clicks_per_day=pro_rated_clicks / plan_request.horizon_days,
                        expected_clicks=pro_rated_clicks,
                        expected_spend=remaining_budget,
                        expected_conversions=pro_rated_conversions,
                        value_ratio=creator_data['combined_score'],
                        recommended_placements=performance_data.get('recommended_placements', 1),
                        median_clicks_per_placement=performance_data.get('median_clicks_per_placement')
                    ))
                    total_spend += remaining_budget
                    total_conversions += pro_rated_conversions
                    print(f"DEBUG: Pro-rated creator {creator.name} - spend: ${remaining_budget:.2f}, rationale: {creator_data['matching_rationale']}")
                break
        
        # Calculate final metrics
        blended_cpa = total_spend / total_conversions if total_conversions > 0 else 0.0
        budget_utilization = total_spend / plan_request.budget if plan_request.budget > 0 else 0.0
        
        print(f"DEBUG: Smart plan results - {len(picked_creators)} creators, ${total_spend:.2f} spend, {total_conversions:.2f} conversions, ${blended_cpa:.2f} CPA, {budget_utilization:.2%} utilization")
        
        return PlanResponse(
            picked_creators=picked_creators,
            total_spend=total_spend,
            total_conversions=total_conversions,
            blended_cpa=blended_cpa,
            budget_utilization=budget_utilization
        )
        
    except Exception as e:
        print(f"DEBUG: Smart matching error: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Smart matching failed: {str(e)}")


@router.get("/historical-data")
async def get_historical_data(
    advertiser_id: Optional[int] = Query(None, description="Advertiser ID"),
    insertion_id: Optional[int] = Query(None, description="Insertion ID"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get historical performance data for creators.
    """
    print(f"DEBUG: HISTORICAL - Starting with advertiser_id={advertiser_id}, insertion_id={insertion_id}")
    
    if not advertiser_id and not insertion_id:
        raise HTTPException(status_code=400, detail="Either advertiser_id or insertion_id must be provided")
    
    try:
        # Get creators for the advertiser/insertion
        if insertion_id:
            # Get creators for specific insertion - try multiple approaches
            print(f"DEBUG: Getting creators for insertion_id: {insertion_id}")
            
            # First try through placements
            creators_from_placements = db.query(Creator).join(Placement).filter(Placement.insertion_id == insertion_id).distinct().all()
            print(f"DEBUG: Found {len(creators_from_placements)} creators through placements")
            
            # Also try through conversions (direct relationship)
            creators_from_conversions = db.query(Creator).join(Conversion).filter(Conversion.insertion_id == insertion_id).distinct().all()
            print(f"DEBUG: Found {len(creators_from_conversions)} creators through conversions")
            
            # Also try through clicks (through perf_uploads)
            creators_from_clicks = db.query(Creator).join(ClickUnique).join(PerfUpload).filter(PerfUpload.insertion_id == insertion_id).distinct().all()
            print(f"DEBUG: Found {len(creators_from_clicks)} creators through clicks")
            
            # Combine all unique creators
            all_creator_ids = set()
            all_creators = []
            
            for creator in creators_from_placements + creators_from_conversions + creators_from_clicks:
                if creator.creator_id not in all_creator_ids:
                    all_creator_ids.add(creator.creator_id)
                    all_creators.append(creator)
            
            creators = all_creators
            print(f"DEBUG: Total unique creators found: {len(creators)}")
        else:
            # Get creators for advertiser
            print(f"DEBUG: Getting creators for advertiser_id: {advertiser_id}")
            creators_query = db.query(Creator).join(Placement).join(Insertion).join(Campaign).filter(Campaign.advertiser_id == advertiser_id)
            creators = creators_query.distinct().all()
            print(f"DEBUG: Found {len(creators)} creators")
        
        historical_data = []
        
        for creator in creators:
            print(f"DEBUG: Processing creator {creator.creator_id}: {creator.name}")
            
            # Get click data
            if insertion_id:
                print(f"DEBUG: HISTORICAL - Getting clicks for creator {creator.creator_id} for insertion {insertion_id}")
                clicks_query = db.query(ClickUnique).join(PerfUpload).filter(
                    ClickUnique.creator_id == creator.creator_id,
                    PerfUpload.insertion_id == insertion_id
                )
            else:
                print(f"DEBUG: HISTORICAL - Getting clicks for creator {creator.creator_id} for all insertions of advertiser {advertiser_id}")
                # Get clicks for all insertions of this advertiser
                clicks_query = db.query(ClickUnique).join(PerfUpload).join(Insertion).join(Campaign).filter(
                    ClickUnique.creator_id == creator.creator_id,
                    Campaign.advertiser_id == advertiser_id
                )
            
            print(f"DEBUG: HISTORICAL - Clicks query SQL: {clicks_query}")
            total_clicks = db.query(func.sum(ClickUnique.unique_clicks)).select_from(clicks_query.subquery()).scalar() or 0
            print(f"DEBUG: HISTORICAL - Creator {creator.creator_id} - total clicks: {total_clicks}")
            
            # Get conversion data
            if insertion_id:
                print(f"DEBUG: HISTORICAL - Getting conversions for creator {creator.creator_id} for insertion {insertion_id}")
                conversions_query = db.query(Conversion).join(ConvUpload).filter(
                    Conversion.creator_id == creator.creator_id,
                    ConvUpload.insertion_id == insertion_id
                )
            else:
                print(f"DEBUG: HISTORICAL - Getting conversions for creator {creator.creator_id} for all insertions of advertiser {advertiser_id}")
                # Get conversions for all insertions of this advertiser
                conversions_query = db.query(Conversion).join(ConvUpload).filter(
                    Conversion.creator_id == creator.creator_id,
                    ConvUpload.advertiser_id == advertiser_id
                )
            
            print(f"DEBUG: HISTORICAL - Conversions query SQL: {conversions_query}")
            total_conversions = db.query(func.sum(Conversion.conversions)).select_from(conversions_query.subquery()).scalar() or 0
            print(f"DEBUG: HISTORICAL - Creator {creator.creator_id} - total conversions: {total_conversions}")
            
            # Calculate CVR
            cvr = total_conversions / total_clicks if total_clicks > 0 else 0
            
            # Get recent performance data
            recent_clicks = clicks_query.order_by(ClickUnique.execution_date.desc()).limit(10).all()
            recent_conversions = conversions_query.order_by(Conversion.period.desc()).limit(10).all()
            
            creator_data = {
                'creator_id': creator.creator_id,
                'name': creator.name,
                'acct_id': creator.acct_id,
                'topic': creator.topic,
                'age_range': creator.age_range,
                'gender_skew': creator.gender_skew,
                'location': creator.location,
                'interests': creator.interests,
                'conservative_click_estimate': creator.conservative_click_estimate,
                'total_clicks': int(total_clicks),
                'total_conversions': int(total_conversions),
                'cvr': float(cvr),
                'recent_clicks': [
                    {
                        'execution_date': click.execution_date.isoformat() if click.execution_date else None,
                        'clicks': click.raw_clicks or 0,
                        'unique_clicks': click.unique_clicks,
                        'flagged': click.flagged
                    } for click in recent_clicks
                ],
                'recent_conversions': [
                    {
                        'period': str(conversion.period),
                        'conversions': conversion.conversions
                    } for conversion in recent_conversions
                ]
            }
            
            historical_data.append(creator_data)
        
        # Calculate summary statistics
        total_creators = len(historical_data)
        creators_with_clicks = len([c for c in historical_data if c['total_clicks'] > 0])
        creators_with_conversions = len([c for c in historical_data if c['total_conversions'] > 0])
        total_clicks = sum(c['total_clicks'] for c in historical_data)
        total_conversions = sum(c['total_conversions'] for c in historical_data)
        overall_cvr = total_conversions / total_clicks if total_clicks > 0 else 0
        
        summary = {
            'total_creators': total_creators,
            'creators_with_clicks': creators_with_clicks,
            'creators_with_conversions': creators_with_conversions,
            'total_clicks': total_clicks,
            'total_conversions': total_conversions,
            'overall_cvr': overall_cvr
        }
        
        print(f"DEBUG: Summary - {summary}")
        
        return {
            'summary': summary,
            'creators': historical_data
        }
        
    except Exception as e:
        print(f"DEBUG: Historical data error: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error getting historical data: {str(e)}")


@router.get("/campaign-forecast")
async def get_campaign_forecast(
    campaign_id: int = Query(..., description="Campaign ID to forecast"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get campaign forecasting data for upcoming placements.
    """
    print(f"DEBUG: Campaign forecast request - campaign_id: {campaign_id}")
    
    try:
        # Get the campaign
        campaign = db.query(Campaign).filter(Campaign.campaign_id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get all insertions for this campaign
        insertions = db.query(Insertion).filter(Insertion.campaign_id == campaign_id).all()
        print(f"DEBUG: Found {len(insertions)} insertions for campaign {campaign_id}")
        
        # Debug: Print all insertion details
        for insertion in insertions:
            print(f"DEBUG: Insertion {insertion.insertion_id} - Start: {insertion.month_start}, End: {insertion.month_end}, CPC: {insertion.cpc}")
        
        # Separate current/past vs future insertions
        today = date.today()
        print(f"DEBUG: Today's date: {today}")
        
        current_past_insertions = [i for i in insertions if i.month_end < today]
        future_insertions = [i for i in insertions if i.month_start > today]
        
        print(f"DEBUG: Current/past insertions: {len(current_past_insertions)}, Future insertions: {len(future_insertions)}")
        
        # Debug: Show which insertions are current/past vs future
        for insertion in current_past_insertions:
            print(f"DEBUG: Current/Past - Insertion {insertion.insertion_id} ends {insertion.month_end}")
        for insertion in future_insertions:
            print(f"DEBUG: Future - Insertion {insertion.insertion_id} starts {insertion.month_start}")
        
        # If no future insertions, check if there are current month insertions
        if not future_insertions:
            current_month_start = today.replace(day=1)
            current_month_insertions = [i for i in insertions if i.month_start <= today and i.month_end >= current_month_start]
            print(f"DEBUG: No future insertions, checking current month: {len(current_month_insertions)} found")
            
            if not current_month_insertions:
                return {
                    'campaign_id': campaign_id,
                    'campaign_name': campaign.name,
                    'forecast_data': [],
                    'total_forecasted_spend': 0.0,
                    'total_forecasted_clicks': 0,
                    'message': 'No future or current month insertions found for this campaign'
                }
            else:
                # Use current month insertions for forecasting
                future_insertions = current_month_insertions
                print(f"DEBUG: Using current month insertions for forecasting: {len(future_insertions)}")
        
        # Get creators for future insertions through multiple paths
        future_insertion_ids = [i.insertion_id for i in future_insertions]
        print(f"DEBUG: Looking for creators for insertions: {future_insertion_ids}")
        
        # Try to get creators through placements first
        placements = db.query(Placement).filter(Placement.insertion_id.in_(future_insertion_ids)).all()
        print(f"DEBUG: Found {len(placements)} placements for future insertions")
        
        # If no placements, try to get creators through performance data
        if not placements:
            print("DEBUG: No placements found, looking for creators through performance data")
            
            # Get creators through clicks (ClickUnique → PerfUpload → Insertion)
            creators_from_clicks = db.query(Creator).join(ClickUnique).join(PerfUpload).filter(
                PerfUpload.insertion_id.in_(future_insertion_ids)
            ).distinct().all()
            print(f"DEBUG: Found {len(creators_from_clicks)} creators through performance data")
            
            # Get creators through conversions
            creators_from_conversions = db.query(Creator).join(Conversion).filter(
                Conversion.insertion_id.in_(future_insertion_ids)
            ).distinct().all()
            print(f"DEBUG: Found {len(creators_from_conversions)} creators through conversions")
            
            # Combine all unique creators
            all_creator_ids = set()
            all_creators = []
            
            for creator in creators_from_clicks + creators_from_conversions:
                if creator.creator_id not in all_creator_ids:
                    all_creator_ids.add(creator.creator_id)
                    all_creators.append(creator)
            
            print(f"DEBUG: Total unique creators found: {len(all_creators)}")
            
            # Create virtual placements for forecasting
            placements = []
            for creator in all_creators:
                # Find the insertion for this creator
                insertion = next((i for i in future_insertions if i.insertion_id in future_insertion_ids), None)
                if insertion:
                    # Create a virtual placement object
                    virtual_placement = type('VirtualPlacement', (), {
                        'placement_id': f"virtual_{creator.creator_id}_{insertion.insertion_id}",
                        'creator': creator,
                        'insertion': insertion
                    })()
                    placements.append(virtual_placement)
            
            print(f"DEBUG: Created {len(placements)} virtual placements for forecasting")
        
        forecast_data = []
        total_forecasted_spend = 0.0
        total_forecasted_clicks = 0
        
        for placement in placements:
            creator = placement.creator
            insertion = placement.insertion
            
            print(f"DEBUG: Processing placement for creator {creator.creator_id} ({creator.name}) in insertion {insertion.insertion_id}")
            
            # Calculate forecasted clicks using the 3-tier logic
            forecasted_clicks = 0
            
            # Tier 1: Check if creator has run this campaign this month
            current_month_start = today.replace(day=1)
            current_month_clicks = db.query(func.sum(ClickUnique.unique_clicks)).join(
                PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
            ).join(
                Insertion, Insertion.insertion_id == PerfUpload.insertion_id
            ).filter(
                ClickUnique.creator_id == creator.creator_id,
                Insertion.campaign_id == campaign_id,
                ClickUnique.execution_date >= current_month_start
            ).scalar() or 0
            
            if current_month_clicks > 0:
                forecasted_clicks = current_month_clicks
                print(f"DEBUG: Tier 1 - Using current month clicks: {forecasted_clicks}")
            else:
                # Tier 2: Check if creator has run other campaigns
                other_campaigns_clicks = db.query(func.sum(ClickUnique.unique_clicks)).join(
                    PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
                ).join(
                    Insertion, Insertion.insertion_id == PerfUpload.insertion_id
                ).join(
                    Campaign, Campaign.campaign_id == Insertion.campaign_id
                ).filter(
                    ClickUnique.creator_id == creator.creator_id,
                    Campaign.campaign_id != campaign_id
                ).scalar() or 0
                
                if other_campaigns_clicks > 0:
                    forecasted_clicks = other_campaigns_clicks
                    print(f"DEBUG: Tier 2 - Using other campaigns clicks: {forecasted_clicks}")
                else:
                    # Tier 3: Use conservative estimate
                    forecasted_clicks = creator.conservative_click_estimate or 0
                    print(f"DEBUG: Tier 3 - Using conservative estimate: {forecasted_clicks}")
            
            # Calculate forecasted spend
            forecasted_spend = float(insertion.cpc) * forecasted_clicks
            
            # Get execution dates for this creator and insertion from performance data
            # This tells us when the insertion will actually run
            execution_dates = db.query(ClickUnique.execution_date).join(
                PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
            ).filter(
                ClickUnique.creator_id == creator.creator_id,
                PerfUpload.insertion_id == insertion.insertion_id,
                ClickUnique.execution_date > today  # Only future execution dates
            ).distinct().all()
            
            print(f"DEBUG: Found {len(execution_dates)} future execution dates for creator {creator.creator_id} in insertion {insertion.insertion_id}")
            
            if execution_dates:
                # Create forecast entries for each execution date
                for execution_date_tuple in execution_dates:
                    execution_date = execution_date_tuple[0]
                    
                    forecast_entry = {
                        'placement_id': f"{placement.placement_id}_{execution_date.strftime('%Y-%m-%d')}",
                        'creator_id': creator.creator_id,
                        'creator_name': creator.name,
                        'creator_acct_id': creator.acct_id,
                        'insertion_id': insertion.insertion_id,
                        'insertion_month_start': insertion.month_start.isoformat(),
                        'insertion_month_end': insertion.month_end.isoformat(),
                        'execution_date': execution_date.isoformat(),
                        'cpc': float(insertion.cpc),
                        'forecasted_clicks': forecasted_clicks,
                        'forecasted_spend': forecasted_spend,
                        'forecast_method': 'current_month' if current_month_clicks > 0 else 'other_campaigns' if other_campaigns_clicks > 0 else 'conservative_estimate'
                    }
                    
                    forecast_data.append(forecast_entry)
                    total_forecasted_spend += forecasted_spend
                    total_forecasted_clicks += forecasted_clicks
            else:
                # If no execution dates found, use insertion period as fallback
                print(f"DEBUG: No execution dates found for creator {creator.creator_id}, using insertion period")
                
                # Create a single entry using insertion period
                forecast_entry = {
                    'placement_id': f"{placement.placement_id}_fallback",
                    'creator_id': creator.creator_id,
                    'creator_name': creator.name,
                    'creator_acct_id': creator.acct_id,
                    'insertion_id': insertion.insertion_id,
                    'insertion_month_start': insertion.month_start.isoformat(),
                    'insertion_month_end': insertion.month_end.isoformat(),
                    'execution_date': insertion.month_start.isoformat(),  # Use insertion start as fallback
                    'cpc': float(insertion.cpc),
                    'forecasted_clicks': forecasted_clicks,
                    'forecasted_spend': forecasted_spend,
                    'forecast_method': 'current_month' if current_month_clicks > 0 else 'other_campaigns' if other_campaigns_clicks > 0 else 'conservative_estimate'
                }
                
                forecast_data.append(forecast_entry)
                total_forecasted_spend += forecasted_spend
                total_forecasted_clicks += forecasted_clicks
        
        print(f"DEBUG: Forecast complete - {len(forecast_data)} placements, ${total_forecasted_spend:.2f} spend, {total_forecasted_clicks} clicks")
        
        return {
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'forecast_data': forecast_data,
            'total_forecasted_spend': total_forecasted_spend,
            'total_forecasted_clicks': total_forecasted_clicks,
            'future_insertions_count': len(future_insertions),
            'placements_count': len(placements)
        }
        
    except Exception as e:
        print(f"DEBUG: Campaign forecast error: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error getting campaign forecast: {str(e)}")
