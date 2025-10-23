from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text, case, and_, or_, desc
from typing import Dict, Any, List, Optional
import logging
import numpy as np
from pydantic import BaseModel
from datetime import date, timedelta
from app.models import Creator, ClickUnique, PerfUpload, Insertion, Campaign, Advertiser, Conversion, ConvUpload, DeclinedCreator, Placement
from app.smart_matching import SmartMatchingService
from app.db import get_db

router = APIRouter()


def calculate_vector_similarity(creator_vector, anchor_vectors):
    """
    Calculate cosine similarity between a creator's vector and multiple anchor vectors.
    Returns the maximum similarity score. Optimized with numpy vectorization.
    """
    if not creator_vector or not anchor_vectors:
        return 0.0
    
    try:
        # Convert creator vector to numpy array
        creator_vec = np.array(creator_vector, dtype=np.float32)
        
        # Convert all anchor vectors to numpy array at once (vectorization)
        anchor_matrix = np.array(anchor_vectors, dtype=np.float32)
        
        # Calculate cosine similarities for all anchor vectors at once
        # Normalize vectors
        creator_norm = np.linalg.norm(creator_vec)
        anchor_norms = np.linalg.norm(anchor_matrix, axis=1)
        
        # Avoid division by zero
        if creator_norm == 0 or np.any(anchor_norms == 0):
            return 0.0
        
        # Calculate dot products for all anchor vectors at once
        dot_products = np.dot(anchor_matrix, creator_vec)
        
        # Calculate cosine similarities
        similarities = dot_products / (creator_norm * anchor_norms)
        
        # Return maximum similarity
        max_similarity = np.max(similarities)
        return float(max_similarity)
        
    except Exception as e:
        print(f"DEBUG: Vector similarity calculation error: {e}")
        return 0.0


def _batch_calculate_performance_data(creators, advertiser_id, category, db):
    """
    Pre-calculate all performance data in batch queries to eliminate N+1 query problem.
    Returns a dictionary mapping creator_id to performance data.
    """
    if not creators:
        return {}
    
    creator_ids = [c.creator_id for c in creators]
    print(f"DEBUG: Batch calculating performance data for {len(creator_ids)} creators")
    
    # Batch query for clicks data
    clicks_data = db.query(
        Creator.creator_id,
        func.sum(ClickUnique.unique_clicks).label('total_clicks'),
        func.avg(ClickUnique.unique_clicks).label('avg_clicks_per_placement'),
        func.count(ClickUnique.click_id).label('placement_count')
    ).join(
        ClickUnique, ClickUnique.creator_id == Creator.creator_id
    ).join(
        PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
    ).join(
        Insertion, Insertion.insertion_id == PerfUpload.insertion_id
    ).join(
        Campaign, Campaign.campaign_id == Insertion.campaign_id
    ).filter(
        Creator.creator_id.in_(creator_ids)
    )
    
    # Add category/advertiser filters
    if category:
        clicks_data = clicks_data.join(
            Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
        ).filter(Advertiser.category == category)
    elif advertiser_id:
        clicks_data = clicks_data.filter(Campaign.advertiser_id == advertiser_id)
    
    clicks_results = clicks_data.group_by(Creator.creator_id).all()
    
    # Batch query for conversions data
    conversions_data = db.query(
        Creator.creator_id,
        func.sum(Conversion.conversions).label('total_conversions')
    ).join(
        Conversion, Conversion.creator_id == Creator.creator_id
    ).join(
        ConvUpload, ConvUpload.conv_upload_id == Conversion.conv_upload_id
    ).filter(
        Creator.creator_id.in_(creator_ids)
    )
    
    # Add category/advertiser filters for conversions
    if category:
        conversions_data = conversions_data.filter(ConvUpload.advertiser_id.in_(
            db.query(Advertiser.advertiser_id).filter(Advertiser.category == category)
        ))
    elif advertiser_id:
        conversions_data = conversions_data.filter(ConvUpload.advertiser_id == advertiser_id)
    
    conversions_results = conversions_data.group_by(Creator.creator_id).all()
    
    # Combine results into performance data dictionary
    performance_data = {}
    
    # Process clicks data
    for row in clicks_results:
        creator_id = row.creator_id
        performance_data[creator_id] = {
            'total_clicks': row.total_clicks or 0,
            'avg_clicks_per_placement': row.avg_clicks_per_placement or 0,
            'placement_count': row.placement_count or 0,
            'total_conversions': 0,
            'expected_cvr': 0.025,  # Default fallback
            'expected_cpa': None
        }
    
    # Process conversions data
    for row in conversions_results:
        creator_id = row.creator_id
        if creator_id in performance_data:
            performance_data[creator_id]['total_conversions'] = row.total_conversions or 0
    
    # Calculate CVR and CPA for each creator
    for creator_id, data in performance_data.items():
        if data['total_clicks'] > 0 and data['total_conversions'] > 0:
            data['expected_cvr'] = data['total_conversions'] / data['total_clicks']
            data['phase'] = 1  # Has performance data
        else:
            # Check for overall creator performance as fallback
            overall_clicks = db.query(func.sum(ClickUnique.unique_clicks)).filter(
                ClickUnique.creator_id == creator_id
            ).scalar() or 0
            overall_conversions = db.query(func.sum(Conversion.conversions)).filter(
                Conversion.creator_id == creator_id
            ).scalar() or 0
            
            if overall_clicks > 0 and overall_conversions > 0:
                data['expected_cvr'] = overall_conversions / overall_clicks
                data['phase'] = 2  # Has cross-performance data
            else:
                data['expected_cvr'] = 0.025  # Default fallback
                data['phase'] = 3  # No performance data
        
        # Add required fields for smart matching
        data['historical_cvr'] = data['expected_cvr']
        data['cross_clicks'] = 0
        data['cross_conversions'] = 0
        data['cross_cvr'] = 0.0
    
    print(f"DEBUG: Batch performance calculation complete - {len(performance_data)} creators processed")
    return performance_data


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
    expected_cpa: Optional[float] = None  # None for vector-similar creators with no historical data
    clicks_per_day: float
    expected_clicks: float
    expected_spend: float
    expected_conversions: float
    value_ratio: float
    recommended_placements: int
    median_clicks_per_placement: Optional[float] = None


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
    
    # Base query for average clicks per creator
    clicks_query = db.query(
        Creator.creator_id,
        Creator.name,
        Creator.acct_id,
        func.avg(ClickUnique.unique_clicks).label('avg_clicks')
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
    
    # Query for average conversions per creator
    conversions_query = db.query(
        Creator.creator_id,
        func.avg(Conversion.conversions).label('avg_conversions')
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
        func.coalesce(clicks_subquery.c.avg_clicks, 0).label('avg_clicks'),
        func.coalesce(conversions_subquery.c.avg_conversions, 0).label('avg_conversions'),
        case(
            (clicks_subquery.c.avg_clicks > 0, 
            func.coalesce(conversions_subquery.c.avg_conversions, 0) / func.nullif(clicks_subquery.c.avg_clicks, 0)),
            else_=0.0
        ).label('avg_cvr')
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
        # Sort by average CVR descending (highest average CVR first)
        main_query = main_query.order_by(desc('avg_cvr'))
    
    # Debug: Print the final SQL query
    print(f"DEBUG: LEADERBOARD - Final query SQL: {main_query}")
    
    # Apply limit
    results = main_query.limit(limit).all()
    print(f"DEBUG: LEADERBOARD - Found {len(results)} results")
    
    # Convert to response format
    leaderboard = []
    for i, row in enumerate(results):
        print(f"DEBUG: LEADERBOARD - Creator {i+1}: {row.name} (ID: {row.creator_id})")
        print(f"  - Average clicks: {row.avg_clicks:.2f}")
        print(f"  - Average conversions: {row.avg_conversions:.2f}")
        print(f"  - Average CVR: {row.avg_cvr:.4f}")
        if hasattr(row, 'expected_cpa') and row.expected_cpa:
            print(f"  - Expected CPA: {row.expected_cpa:.2f}")
        creator_stats = CreatorStats(
            creator_id=row.creator_id,
            name=row.name,
            acct_id=row.acct_id,
            clicks=int(row.avg_clicks),
            conversions=int(row.avg_conversions),
            cvr=float(row.avg_cvr)
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
    global_baseline_cvr = 0.025  # 2.5%
    
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
    
    # Enhanced greedy allocation with placement limits and budget maximization
    print("DEBUG: Starting enhanced greedy allocation with placement limits")
    picked_creators = []
    total_spend = 0.0
    total_conversions = 0.0
    remaining_budget = plan_request.budget
    creator_placement_counts = {}  # Track placements per creator
    
    # First pass: Add full allocations with placement limits
    for alloc_index, creator_stat in enumerate(creator_stats):
        creator_id = creator_stat['creator_id']
        current_placements = creator_placement_counts.get(creator_id, 0)
        
        print(f"DEBUG: Allocation {alloc_index + 1}/{len(creator_stats)} - {creator_stat['name']} (spend: {creator_stat['expected_spend']}, placements: {current_placements}/3, remaining budget: {remaining_budget})")
        
        # Check placement limit (max 3 per creator)
        if current_placements >= 3:
            print(f"DEBUG: Skipping {creator_stat['name']} - already at max placements (3)")
            continue
            
        if creator_stat['expected_spend'] <= remaining_budget:
            # Can fit full allocation
            print(f"DEBUG: Adding full allocation for {creator_stat['name']} (placement {current_placements + 1})")
            picked_creators.append(PlanCreator(**creator_stat))
            total_spend += creator_stat['expected_spend']
            total_conversions += creator_stat['expected_conversions']
            remaining_budget -= creator_stat['expected_spend']
            creator_placement_counts[creator_id] = current_placements + 1
        else:
            print(f"DEBUG: Skipping {creator_stat['name']} - too expensive (${creator_stat['expected_spend']:.2f} > ${remaining_budget:.2f})")
    
    # Second pass: Continue adding creators until budget is fully utilized
    print(f"DEBUG: First pass complete - ${total_spend:.2f} spent, ${remaining_budget:.2f} remaining")
    
    # Keep trying to fill budget with additional creators
    max_iterations = len(creator_stats) * 3  # Prevent infinite loops
    iteration = 0
    
    while remaining_budget > 0 and iteration < max_iterations:
        iteration += 1
        print(f"DEBUG: Budget filling iteration {iteration} - ${remaining_budget:.2f} remaining")
        
        added_creator = False
        
        # Try to find creators that can fit in remaining budget
        for creator_stat in creator_stats:
            creator_id = creator_stat['creator_id']
            current_placements = creator_placement_counts.get(creator_id, 0)
            
            # Check placement limit
            if current_placements >= 3:
                continue
                
            if creator_stat['expected_spend'] <= remaining_budget:
                print(f"DEBUG: Adding additional creator {creator_stat['name']} (placement {current_placements + 1}) with remaining budget")
                picked_creators.append(PlanCreator(**creator_stat))
                total_spend += creator_stat['expected_spend']
                total_conversions += creator_stat['expected_conversions']
                remaining_budget -= creator_stat['expected_spend']
                creator_placement_counts[creator_id] = current_placements + 1
                added_creator = True
                break
        
        # If no full creators fit, try pro-rating the best remaining creator
        if not added_creator and remaining_budget > 0:
            for creator_stat in creator_stats:
                creator_id = creator_stat['creator_id']
                current_placements = creator_placement_counts.get(creator_id, 0)
                
                # Check placement limit
                if current_placements >= 3:
                    continue
                    
                if creator_stat['expected_spend'] > remaining_budget:
                    pro_ratio = remaining_budget / creator_stat['expected_spend']
                    if pro_ratio > 0.1:  # Only pro-rate if we can get at least 10% of the allocation
                        print(f"DEBUG: Pro-rating {creator_stat['name']} (placement {current_placements + 1}) - ratio: {pro_ratio:.2f}")
                        pro_rated_stat = creator_stat.copy()
                        pro_rated_stat['expected_clicks'] *= pro_ratio
                        pro_rated_stat['expected_spend'] = remaining_budget
                        pro_rated_stat['expected_conversions'] *= pro_ratio
                        
                        print(f"DEBUG: Pro-rated spend: {pro_rated_stat['expected_spend']}, conversions: {pro_rated_stat['expected_conversions']}")
                        picked_creators.append(PlanCreator(**pro_rated_stat))
                        total_spend += remaining_budget
                        total_conversions += pro_rated_stat['expected_conversions']
                        creator_placement_counts[creator_id] = current_placements + 1
                        remaining_budget = 0
                        added_creator = True
                        break
        
        # If no creators were added, break to prevent infinite loop
        if not added_creator:
            print(f"DEBUG: No more creators can be added with remaining budget ${remaining_budget:.2f}")
            break
    
    print(f"DEBUG: Final budget utilization - ${total_spend:.2f} spent, ${remaining_budget:.2f} remaining, {len(picked_creators)} total placements")
    
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
        
        # Pre-calculate performance data in batch to eliminate N+1 queries
        print("DEBUG: Pre-calculating performance data in batch")
        batch_performance_data = _batch_calculate_performance_data(
            smart_service._get_base_creators_query(plan_request.advertiser_id, plan_request.category).all(),
            plan_request.advertiser_id,
            plan_request.category,
            db
        )
        
        matched_creators = smart_service.find_smart_creators(
            advertiser_id=plan_request.advertiser_id,
            category=plan_request.category,
            target_demographics=target_demographics,
            budget=plan_request.budget,
            cpc=cpc,
            target_cpa=plan_request.target_cpa,
            horizon_days=plan_request.horizon_days,
            advertiser_avg_cvr=plan_request.advertiser_avg_cvr or 0.025,
            include_acct_ids=plan_request.include_acct_ids,
            exclude_acct_ids=plan_request.exclude_acct_ids,
            batch_performance_data=batch_performance_data  # Pass pre-calculated data
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
        
        # Enhanced allocation with placement limits and budget maximization
        creator_placement_counts = {}  # Track placements per creator
        remaining_budget = plan_request.budget
        
        # Phase 1: Target category/campaign creators with CPA ≤ target CPA
        print(f"DEBUG: Phase 1 - Target category/campaign creators with CPA ≤ target CPA")
        phase1_creators = []
        for creator_data in matched_creators:
            creator = creator_data['creator']
            performance_data = creator_data['performance_data']
            
            # Use batch performance data if available, otherwise fall back to individual data
            if creator.creator_id in batch_performance_data:
                batch_data = batch_performance_data[creator.creator_id]
                expected_cpa = cpc / batch_data['expected_cvr'] if batch_data['expected_cvr'] > 0 else float('inf')
                print(f"DEBUG: Phase 1 - Using batch data for {creator.name} (CVR: {batch_data['expected_cvr']:.4f}, CPA: {expected_cpa:.2f})")
            else:
                expected_cpa = performance_data.get('expected_cpa', float('inf')) if performance_data else float('inf')
                print(f"DEBUG: Phase 1 - Using individual data for {creator.name} (CPA: {expected_cpa:.2f})")
            
            # Phase 1: Only creators with CPA ≤ target CPA in TARGET category/campaign
            if plan_request.target_cpa is not None and expected_cpa <= plan_request.target_cpa:
                phase1_creators.append(creator_data)
                print(f"DEBUG: Phase 1 - {creator.name} (CPA: {expected_cpa:.2f}) - TARGET category")
            else:
                print(f"DEBUG: Phase 1 - Skipping {creator.name} - CPA {expected_cpa:.2f} exceeds target CPA {plan_request.target_cpa:.2f} in TARGET category")
        
        # Sort Phase 1 by CPA (lowest first)
        phase1_creators.sort(key=lambda x: x['performance_data']['expected_cpa'])
        
        # Allocate Phase 1 creators
        for creator_data in phase1_creators:
            if remaining_budget <= 0:
                break
                
            creator = creator_data['creator']
            performance_data = creator_data['performance_data']
            creator_id = creator.creator_id
            current_placements = creator_placement_counts.get(creator_id, 0)
            
            if current_placements >= 3:
                continue
            
            expected_clicks = performance_data.get('expected_clicks', 100)
            expected_spend = cpc * expected_clicks
            expected_conversions = performance_data.get('expected_conversions', expected_clicks * (plan_request.advertiser_avg_cvr or 0.025))
            
            if expected_spend <= remaining_budget:
                # Add new creator (Phase 1 - first placement only)
                picked_creators.append(PlanCreator(
                    creator_id=creator.creator_id,
                    name=creator.name,
                    acct_id=creator.acct_id,
                    expected_cvr=performance_data.get('expected_cvr', plan_request.advertiser_avg_cvr or 0.025),
                    expected_cpa=performance_data['expected_cpa'],
                    clicks_per_day=expected_clicks / plan_request.horizon_days,
                    expected_clicks=expected_clicks,
                    expected_spend=expected_spend,
                    expected_conversions=expected_conversions,
                    value_ratio=creator_data['combined_score'],
                    recommended_placements=1,
                    median_clicks_per_placement=performance_data.get('median_clicks_per_placement')
                ))
                total_spend += expected_spend
                total_conversions += expected_conversions
                remaining_budget -= expected_spend
                creator_placement_counts[creator_id] = 1
                print(f"DEBUG: Phase 1 - Added {creator.name} (CPA: {performance_data['expected_cpa']:.2f}, spend: ${expected_spend:.2f})")
            else:
                print(f"DEBUG: Phase 1 - Skipping {creator.name} - too expensive (${expected_spend:.2f} > ${remaining_budget:.2f})")
        
        # Phase 2: Other categories/campaigns creators with CPA ≤ target CPA (but exclude creators who failed in target category)
        print(f"DEBUG: Phase 2 - Other categories/campaigns creators with CPA ≤ target CPA")
        phase2_creators = []
        target_category_failures = set()  # Track creators who failed in target category
        
        # First, identify creators who failed in target category using batch data
        for creator_data in matched_creators:
            creator = creator_data['creator']
            performance_data = creator_data['performance_data']
            
            # Use batch performance data if available
            if creator.creator_id in batch_performance_data:
                batch_data = batch_performance_data[creator.creator_id]
                expected_cpa = cpc / batch_data['expected_cvr'] if batch_data['expected_cvr'] > 0 else float('inf')
            else:
                expected_cpa = performance_data.get('expected_cpa', float('inf')) if performance_data else float('inf')
            
            if plan_request.target_cpa is not None and expected_cpa > plan_request.target_cpa:
                target_category_failures.add(creator.creator_id)
                print(f"DEBUG: Phase 2 - {creator.name} failed in target category (CPA: {expected_cpa:.2f}) - will exclude from Phase 2")
        
        # Now find Phase 2 candidates (other categories, but not target category failures)
            for creator_data in matched_creators:
                creator = creator_data['creator']
                performance_data = creator_data['performance_data']
                
        # Sort Phase 2 by CPA (lowest first)
        phase2_creators.sort(key=lambda x: x['performance_data']['expected_cpa'])
        
        # Allocate Phase 2 creators
        for creator_data in phase2_creators:
            if remaining_budget <= 0:
                break
                
                creator = creator_data['creator']
                performance_data = creator_data['performance_data']
                creator_id = creator.creator_id
                current_placements = creator_placement_counts.get(creator_id, 0)
                
                if current_placements >= 3:
                    continue
                
                    expected_clicks = performance_data.get('expected_clicks', 100)
                expected_spend = cpc * expected_clicks
            expected_conversions = performance_data.get('expected_conversions', expected_clicks * (plan_request.advertiser_avg_cvr or 0.025))
                
            if expected_spend <= remaining_budget:
                # Add new creator (Phase 2 - first placement only)
                    picked_creators.append(PlanCreator(
                        creator_id=creator.creator_id,
                        name=creator.name,
                        acct_id=creator.acct_id,
                    expected_cvr=performance_data.get('expected_cvr', plan_request.advertiser_avg_cvr or 0.025),
                    expected_cpa=performance_data['expected_cpa'],
                        clicks_per_day=expected_clicks / plan_request.horizon_days,
                        expected_clicks=expected_clicks,
                        expected_spend=expected_spend,
                        expected_conversions=expected_conversions,
                        value_ratio=creator_data['combined_score'],
                    recommended_placements=1,
                    median_clicks_per_placement=performance_data.get('median_clicks_per_placement')
                    ))
                    total_spend += expected_spend
                    total_conversions += expected_conversions
                    remaining_budget -= expected_spend
                    creator_placement_counts[creator_id] = 1
            print(f"DEBUG: Phase 2 - Added {creator.name} (CPA: {performance_data['expected_cpa']:.2f}, spend: ${expected_spend:.2f})")
        
        # Phase 3: Add more placements to existing creators (up to 3 total per creator)
        print(f"DEBUG: Phase 3 - Adding more placements to existing creators with ${remaining_budget:.2f} remaining")
        if remaining_budget > 0:
            # Try to add more placements to existing creators
            for creator_data in phase1_creators + phase2_creators:
                if remaining_budget <= 0:
                    break
            
                    creator = creator_data['creator']
                    performance_data = creator_data['performance_data']
                    creator_id = creator.creator_id
                    current_placements = creator_placement_counts.get(creator_id, 0)
                    
                    if current_placements >= 3:
                        continue
                    
                        expected_clicks = performance_data.get('expected_clicks', 100)
                expected_spend = cpc * expected_clicks
                expected_conversions = performance_data.get('expected_conversions', expected_clicks * (plan_request.advertiser_avg_cvr or 0.025))
                
                if expected_spend <= remaining_budget:
                    # Update existing creator - add another placement
                    existing_creator = None
                    for i, pc in enumerate(picked_creators):
                        if pc.creator_id == creator_id:
                            existing_creator = i
                            break
                    
                    if existing_creator is not None:
                        pc = picked_creators[existing_creator]
                        new_placements = pc.recommended_placements + 1
                        
                        # Update the existing creator with multiplied values
                        picked_creators[existing_creator] = PlanCreator(
                            creator_id=pc.creator_id,
                            name=pc.name,
                            acct_id=pc.acct_id,
                            expected_cvr=pc.expected_cvr,
                            expected_cpa=pc.expected_cpa,
                            clicks_per_day=pc.clicks_per_day,
                            expected_clicks=expected_clicks * new_placements,
                            expected_spend=expected_spend * new_placements,
                            expected_conversions=expected_conversions * new_placements,
                            value_ratio=pc.value_ratio,
                            recommended_placements=new_placements,
                            median_clicks_per_placement=pc.median_clicks_per_placement
                        )
                        
                        total_spend += expected_spend
                        total_conversions += expected_conversions
                        remaining_budget -= expected_spend
                        creator_placement_counts[creator_id] = new_placements
                        print(f"DEBUG: Phase 3 - Updated {creator.name} to {new_placements} placements (spend: ${expected_spend:.2f} per placement)")
        
        print(f"DEBUG: Three-phase CPA enforcement complete - ${total_spend:.2f} spent, ${remaining_budget:.2f} remaining, {len(picked_creators)} total placements")
        
        # Phase 4 & 5: Vector Fallback Logic
        if remaining_budget > 0:
            print(f"DEBUG: Phase 4 - Vector fallback with ${remaining_budget:.2f} remaining budget")
            
            # Get anchor vectors from top 3 most successful creators (optimization)
            anchor_vectors = []
            # Sort picked creators by value_ratio (best performers first) and take top 3
            top_creators = sorted(picked_creators, key=lambda x: x.value_ratio, reverse=True)[:3]
            print(f"DEBUG: Using top {len(top_creators)} creators as anchor vectors for similarity matching")
            
            for pc in top_creators:
                # Get vector data for this creator
                creator = db.query(Creator).filter(Creator.creator_id == pc.creator_id).first()
                
                if creator and hasattr(creator, 'vector') and creator.vector:
                    try:
                        # Access the actual vector array from CreatorVector object
                        if hasattr(creator.vector, 'vector'):
                            vector_data = creator.vector.vector
                        elif isinstance(creator.vector, str):
                            import ast
                            vector_data = ast.literal_eval(creator.vector)
                        else:
                            vector_data = creator.vector
                        
                        anchor_vectors.append(vector_data)
                        print(f"DEBUG: Added anchor vector for creator {creator.creator_id}")
                    except Exception as e:
                        print(f"DEBUG: Error parsing vector for creator {creator.creator_id}: {e}")
                        continue
            
            if anchor_vectors:
                print(f"DEBUG: Found {len(anchor_vectors)} anchor vectors for similarity matching")
                
                # Find creators with no historical data but with vectors
                vector_creators = db.query(Creator).filter(
                    Creator.vector != None,
                    ~Creator.creator_id.in_([pc.creator_id for pc in picked_creators])
                ).all()
                
                print(f"DEBUG: Found {len(vector_creators)} creators with vectors but no historical data")
                
                # Calculate similarity scores for vector creators (optimized)
                vector_similarities = []
                print(f"DEBUG: Processing {len(vector_creators)} vector creators for similarity matching")
                
                for creator in vector_creators:
                    try:
                        # Access the actual vector array from CreatorVector object
                        if hasattr(creator.vector, 'vector'):
                            creator_vector = creator.vector.vector
                        elif isinstance(creator.vector, str):
                            import ast
                            creator_vector = ast.literal_eval(creator.vector)
                        else:
                            creator_vector = creator.vector
                        
                        # Calculate similarity using optimized function
                        similarity = calculate_vector_similarity(creator_vector, anchor_vectors)
                        
                        if similarity >= 0.7:  # Minimum similarity threshold
                            vector_similarities.append({
                                'creator': creator,
                                'similarity': similarity,
                                'expected_clicks': creator.conservative_click_estimate or 100,
                                'expected_conversions': 0,  # No conversion expectations for vector-similar creators
                                'expected_spend': cpc * (creator.conservative_click_estimate or 100)
                            })
                    except Exception as e:
                        print(f"DEBUG: Error processing vector for creator {creator.creator_id}: {e}")
                        continue
                
                # Sort by similarity (highest first)
                vector_similarities.sort(key=lambda x: x['similarity'], reverse=True)
                print(f"DEBUG: Found {len(vector_similarities)} vector-similar creators above 0.7 threshold")
                
                # Early exit if no vector-similar creators found
                if not vector_similarities:
                    print(f"DEBUG: No vector-similar creators found, skipping vector fallback")
                else:
                    # Phase 4: Add vector-similar creators
                    for vector_data in vector_similarities:
                        if remaining_budget <= 0:
                            break
                        
                        creator = vector_data['creator']
                        expected_spend = vector_data['expected_spend']
                        expected_clicks = vector_data['expected_clicks']
                        expected_conversions = vector_data['expected_conversions']
                        similarity = vector_data['similarity']
                        
                        if expected_spend <= remaining_budget:
                            # Add new vector-similar creator
                            picked_creators.append(PlanCreator(
                                creator_id=creator.creator_id,
                                name=creator.name,
                                acct_id=creator.acct_id,
                                expected_cvr=plan_request.advertiser_avg_cvr or 0.025,
                                expected_cpa=None,  # No historical CPA data for vector-similar creators
                                clicks_per_day=expected_clicks / plan_request.horizon_days,
                                expected_clicks=expected_clicks,
                                expected_spend=expected_spend,
                                expected_conversions=0,  # No conversion expectations for vector-similar creators
                                value_ratio=similarity,  # Use similarity as value ratio
                                recommended_placements=1,
                                median_clicks_per_placement=None
                            ))
                            total_spend += expected_spend
                            total_conversions += expected_conversions
                            remaining_budget -= expected_spend
                            creator_placement_counts[creator.creator_id] = 1
                            print(f"DEBUG: Phase 4 - Added vector-similar creator {creator.name} (similarity: {similarity:.3f}, spend: ${expected_spend:.2f}) - NO HISTORICAL DATA")
                    
                    # Phase 5: Add more placements to vector-matched creators
                    if remaining_budget > 0:
                        print(f"DEBUG: Phase 5 - Adding more placements to vector-matched creators with ${remaining_budget:.2f} remaining")
                    
                    # Try to add more placements to vector-matched creators
                    max_iterations = len(vector_similarities) * 3
                    iteration = 0
                    
                    while remaining_budget > 0 and iteration < max_iterations:
                        iteration += 1
                        added_creator = False
                        
                        for vector_data in vector_similarities:
                            if remaining_budget <= 0:
                                break
                            
                            creator = vector_data['creator']
                            creator_id = creator.creator_id
                            current_placements = creator_placement_counts.get(creator_id, 0)
                            
                            if current_placements >= 3:
                                continue
                            
                            expected_spend = vector_data['expected_spend']
                            expected_clicks = vector_data['expected_clicks']
                            expected_conversions = vector_data['expected_conversions']
                            
                            if expected_spend <= remaining_budget:
                                # Update existing creator - add another placement
                                existing_creator = None
                                for i, pc in enumerate(picked_creators):
                                    if pc.creator_id == creator_id:
                                        existing_creator = i
                                        break
                                
                                if existing_creator is not None:
                                    pc = picked_creators[existing_creator]
                                    new_placements = pc.recommended_placements + 1
                                    
                                    # Update the existing creator with multiplied values
                                    picked_creators[existing_creator] = PlanCreator(
                                        creator_id=pc.creator_id,
                                        name=pc.name,
                                        acct_id=pc.acct_id,
                                        expected_cvr=pc.expected_cvr,
                                        expected_cpa=pc.expected_cpa,
                                        clicks_per_day=pc.clicks_per_day,
                                        expected_clicks=expected_clicks * new_placements,
                                        expected_spend=expected_spend * new_placements,
                                        expected_conversions=expected_conversions * new_placements,
                                        value_ratio=pc.value_ratio,
                                        recommended_placements=new_placements,
                                        median_clicks_per_placement=pc.median_clicks_per_placement
                                    )
                                    
                                    total_spend += expected_spend
                                    total_conversions += expected_conversions
                                    remaining_budget -= expected_spend
                                    creator_placement_counts[creator_id] = new_placements
                                    print(f"DEBUG: Phase 5 - Updated {creator.name} to {new_placements} placements (spend: ${expected_spend:.2f} per placement)")
                                added_creator = True
                                break
                        
                        if not added_creator:
                            break
                
                print(f"DEBUG: Vector fallback complete - ${total_spend:.2f} spent, ${remaining_budget:.2f} remaining")
            else:
                print(f"DEBUG: No anchor vectors found for similarity matching")
        
        # Recalculate totals from final picked_creators to ensure accuracy
        final_total_spend = sum(pc.expected_spend for pc in picked_creators)
        final_total_conversions = sum(pc.expected_conversions for pc in picked_creators)
        
        print(f"DEBUG: Recalculated totals - spend: ${final_total_spend:.2f}, conversions: {final_total_conversions:.2f}")
        
        # Calculate final metrics
        blended_cpa = final_total_spend / final_total_conversions if final_total_conversions > 0 else 0.0
        budget_utilization = final_total_spend / plan_request.budget if plan_request.budget > 0 else 0.0
        
        # Show phase breakdown
        phase1_count = len([p for p in picked_creators if p.recommended_placements == 1])
        phase2_3_count = len([p for p in picked_creators if p.recommended_placements > 1])
        vector_creators = len([p for p in picked_creators if p.value_ratio > 0.7 and p.value_ratio < 1.0])  # Vector similarity scores
        
        print(f"DEBUG: Five-phase results - Phase 1: {phase1_count} creators, Phase 2&3: {phase2_3_count} additional placements, Vector: {vector_creators} creators")
        print(f"DEBUG: Final results - {len(picked_creators)} creators, ${final_total_spend:.2f} spend, {final_total_conversions:.2f} conversions, ${blended_cpa:.2f} CPA, {budget_utilization:.2%} utilization")
        
        return PlanResponse(
            picked_creators=picked_creators,
            total_spend=final_total_spend,
            total_conversions=final_total_conversions,
            blended_cpa=blended_cpa,
            budget_utilization=budget_utilization
        )
        
    except Exception as e:
        print(f"DEBUG: Smart matching error: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Smart matching failed: {str(e)}")
    
def _get_other_campaigns_clicks(creator: Creator, advertiser_id: Optional[int], category: Optional[str], db: Session) -> int:
    """Get click estimates from other campaigns for this creator."""
    from sqlalchemy import func, and_
    from app.models import ClickUnique, PerfUpload, Insertion, Campaign, Advertiser
    
    print(f"DEBUG: Getting other campaigns clicks for creator {creator.creator_id}")
    
    # Build query for clicks from OTHER campaigns
    other_campaigns_query = db.query(func.sum(ClickUnique.unique_clicks)).join(
        PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
    ).join(
        Insertion, Insertion.insertion_id == PerfUpload.insertion_id
    ).join(
        Campaign, Campaign.campaign_id == Insertion.campaign_id
    ).filter(ClickUnique.creator_id == creator.creator_id)
    
    # Exclude the current advertiser/category
    if advertiser_id:
        other_campaigns_query = other_campaigns_query.filter(Campaign.advertiser_id != advertiser_id)
    elif category:
        other_campaigns_query = other_campaigns_query.join(
            Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
        ).filter(Advertiser.category != category)
    
    total_other_clicks = other_campaigns_query.scalar() or 0
    print(f"DEBUG: Creator {creator.creator_id} - Total other campaigns clicks: {total_other_clicks}")
    
    if total_other_clicks > 0:
        # Get individual placement clicks from other campaigns to calculate median
        placement_clicks_query = db.query(ClickUnique.unique_clicks).join(
            PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
        ).join(
            Insertion, Insertion.insertion_id == PerfUpload.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).filter(ClickUnique.creator_id == creator.creator_id)
        
        # Exclude current advertiser/category
        if advertiser_id:
            placement_clicks_query = placement_clicks_query.filter(Campaign.advertiser_id != advertiser_id)
        elif category:
            placement_clicks_query = placement_clicks_query.join(
                Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
            ).filter(Advertiser.category != category)
        
        placement_clicks = [row[0] for row in placement_clicks_query.all() if row[0] is not None]
        
        if placement_clicks:
            # Calculate median clicks per placement from other campaigns
            placement_clicks.sort()
            median_clicks = placement_clicks[len(placement_clicks) // 2]
            print(f"DEBUG: Creator {creator.creator_id} - Median clicks from other campaigns: {median_clicks}")
            return median_clicks
    
    return 0


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
            
            # Debug: Get individual click records to see what's being summed
            individual_clicks = clicks_query.all()
            print(f"DEBUG: HISTORICAL - Creator {creator.creator_id} - Individual click records: {[(c.unique_clicks, c.execution_date) for c in individual_clicks]}")
            
            # Calculate total clicks directly from the individual records
            total_clicks = sum(record.unique_clicks for record in individual_clicks)
            print(f"DEBUG: HISTORICAL - Creator {creator.creator_id} - total clicks: {total_clicks}")
            
            # Get conversion data
            if insertion_id:
                print(f"DEBUG: HISTORICAL - Getting conversions for creator {creator.creator_id} for insertion {insertion_id}")
                conversions_query = db.query(Conversion).filter(
                    Conversion.creator_id == creator.creator_id,
                    Conversion.insertion_id == insertion_id
                )
            else:
                print(f"DEBUG: HISTORICAL - Getting conversions for creator {creator.creator_id} for all insertions of advertiser {advertiser_id}")
                # Get conversions for all insertions of this advertiser
                conversions_query = db.query(Conversion).join(ConvUpload).filter(
                    Conversion.creator_id == creator.creator_id,
                    ConvUpload.advertiser_id == advertiser_id
                )
            
            print(f"DEBUG: HISTORICAL - Conversions query SQL: {conversions_query}")
            
            # Debug: Get individual conversion records to see what's being summed
            individual_conversions = db.query(Conversion.conversions, Conversion.period).filter(
                Conversion.creator_id == creator.creator_id,
                Conversion.insertion_id == insertion_id
            ).all()
            print(f"DEBUG: HISTORICAL - Creator {creator.creator_id} - Individual conversion records: {individual_conversions}")
            
            # Debug: Check what conversion records exist for this creator and insertion
            all_conversions = db.query(Conversion.conversion_id, Conversion.creator_id, Conversion.insertion_id, Conversion.conversions, Conversion.period).filter(
                Conversion.creator_id == creator.creator_id,
                Conversion.insertion_id == insertion_id
            ).all()
            print(f"DEBUG: HISTORICAL - Creator {creator.creator_id} - All conversion records in DB: {all_conversions}")
            
            total_conversions = db.query(func.sum(Conversion.conversions)).filter(
                Conversion.creator_id == creator.creator_id,
                Conversion.insertion_id == insertion_id
            ).scalar() or 0
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


@router.get("/debug/clicks")
async def debug_clicks(
    campaign_id: Optional[int] = Query(None, description="Campaign ID to debug"),
    insertion_id: Optional[int] = Query(None, description="Insertion ID to debug"),
    advertiser_id: Optional[int] = Query(None, description="Advertiser ID to debug"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Debug endpoint to check click counts and data sources.
    """
    print(f"DEBUG: CLICKS - Starting debug with campaign_id={campaign_id}, insertion_id={insertion_id}, advertiser_id={advertiser_id}")
    
    # Get all click records with detailed info
    clicks_query = db.query(
        ClickUnique.click_id,
        ClickUnique.creator_id,
        ClickUnique.unique_clicks,
        ClickUnique.execution_date,
        ClickUnique.status,
        PerfUpload.perf_upload_id,
        PerfUpload.insertion_id,
        Insertion.campaign_id,
        Campaign.advertiser_id,
        Creator.name,
        Creator.acct_id
    ).join(
        PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
    ).join(
        Insertion, Insertion.insertion_id == PerfUpload.insertion_id
    ).join(
        Campaign, Campaign.campaign_id == Insertion.campaign_id
    ).join(
        Creator, Creator.creator_id == ClickUnique.creator_id
    )
    
    # Apply filters
    if campaign_id:
        clicks_query = clicks_query.filter(Insertion.campaign_id == campaign_id)
    if insertion_id:
        clicks_query = clicks_query.filter(PerfUpload.insertion_id == insertion_id)
    if advertiser_id:
        clicks_query = clicks_query.filter(Campaign.advertiser_id == advertiser_id)
    
    print(f"DEBUG: CLICKS - Query SQL: {clicks_query}")
    
    # Get all click records
    click_records = clicks_query.all()
    print(f"DEBUG: CLICKS - Found {len(click_records)} click records")
    
    # Calculate totals
    total_clicks = sum(record.unique_clicks for record in click_records)
    
    # Group by creator
    creator_clicks = {}
    for record in click_records:
        creator_id = record.creator_id
        if creator_id not in creator_clicks:
            creator_clicks[creator_id] = {
                'name': record.name,
                'acct_id': record.acct_id,
                'total_clicks': 0,
                'records': []
            }
        creator_clicks[creator_id]['total_clicks'] += record.unique_clicks
        creator_clicks[creator_id]['records'].append({
            'click_id': record.click_id,
            'unique_clicks': record.unique_clicks,
            'execution_date': record.execution_date.isoformat() if record.execution_date else None,
            'status': record.status,
            'insertion_id': record.insertion_id,
            'campaign_id': record.campaign_id
        })
    
    return {
        "total_click_records": len(click_records),
        "total_clicks": total_clicks,
        "creator_breakdown": creator_clicks,
        "filters_applied": {
            "campaign_id": campaign_id,
            "insertion_id": insertion_id,
            "advertiser_id": advertiser_id
        }
    }


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
