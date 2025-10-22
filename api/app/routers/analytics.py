from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, asc
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import math

from app.db import get_db
from app.models import Creator, ClickUnique, Conversion, Placement, DeclinedCreator, CreatorVector
from app.schemas import (
    PlanRequest, PlanResponse, PlanCreator, 
    LeaderboardEntry, FilterOptions, HistoricalDataResponse,
    CampaignForecastRequest, CampaignForecastResponse
)
from app.smart_matching import SmartMatchingService

router = APIRouter()

@router.get("/declined-creators/{advertiser_id}")
async def get_declined_creators(
    advertiser_id: int,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get declined creators for a specific advertiser"""
    declined_creators = db.query(DeclinedCreator).filter(
        DeclinedCreator.advertiser_id == advertiser_id
    ).all()
    
    return [
        {
            "creator_id": dc.creator_id,
            "creator_name": dc.creator_name,
            "declined_at": dc.declined_at,
            "reason": dc.reason
        }
        for dc in declined_creators
    ]

@router.get("/filter-options")
async def get_filter_options(db: Session = Depends(get_db)) -> Dict[str, List[str]]:
    """Get filter options for the frontend"""
    # Get unique advertisers
    advertisers = db.query(Creator.advertiser).filter(
        Creator.advertiser.isnot(None)
    ).distinct().all()
    
    # Get unique categories
    categories = db.query(Creator.category).filter(
        Creator.category.isnot(None)
    ).distinct().all()
    
    return {
        "advertisers": [a[0] for a in advertisers if a[0]],
        "categories": [c[0] for c in categories if c[0]]
    }

@router.get("/leaderboard")
async def get_leaderboard(
    advertiser_id: Optional[int] = None,
    category: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
) -> List[LeaderboardEntry]:
    """Get creator leaderboard with performance metrics"""
    
    # Base query for creators
    query = db.query(Creator)
    
    # Apply filters
    if advertiser_id:
        query = query.filter(Creator.advertiser_id == advertiser_id)
    if category:
        query = query.filter(Creator.category == category)
    
    creators = query.all()
    
    leaderboard = []
    
    for creator in creators:
        # Get click and conversion data
        clicks_query = db.query(func.sum(ClickUnique.clicks)).filter(ClickUnique.creator_id == creator.creator_id)
        conversions_query = db.query(func.sum(Conversion.conversions)).filter(Conversion.creator_id == creator.creator_id)
        
        if advertiser_id:
            clicks_query = clicks_query.filter(ClickUnique.advertiser_id == advertiser_id)
            conversions_query = conversions_query.filter(Conversion.advertiser_id == advertiser_id)
        if category:
            clicks_query = clicks_query.filter(ClickUnique.category == category)
            conversions_query = conversions_query.filter(Conversion.category == category)
        
        total_clicks = clicks_query.scalar() or 0
        total_conversions = conversions_query.scalar() or 0
        
        # Calculate metrics
        cvr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        cpa = (creator.cpc * total_clicks / total_conversions) if total_conversions > 0 else None
        
        leaderboard.append(LeaderboardEntry(
            creator_id=creator.creator_id,
            name=creator.name,
            total_clicks=total_clicks,
            total_conversions=total_conversions,
            cvr=cvr,
            cpa=cpa,
            cpc=creator.cpc
        ))
    
    # Sort by conversions descending
    leaderboard.sort(key=lambda x: x.total_conversions, reverse=True)
    
    return leaderboard[:limit]

@router.post("/plan", response_model=PlanResponse)
async def create_plan(
    plan_request: PlanRequest,
    db: Session = Depends(get_db)
) -> PlanResponse:
    """Create a basic plan based on simple criteria"""
    
    # Get creators with basic filtering
    query = db.query(Creator)
    
    if plan_request.advertiser_id:
        query = query.filter(Creator.advertiser_id == plan_request.advertiser_id)
    if plan_request.category:
        query = query.filter(Creator.category == plan_request.category)
    
    creators = query.limit(plan_request.max_creators).all()
    
    if not creators:
        return PlanResponse(
            plan_id="basic_plan",
            total_budget=0,
            estimated_clicks=0,
            estimated_conversions=0,
            estimated_cpa=None,
            creators=[]
        )
    
    # Simple allocation logic
    budget_per_creator = plan_request.budget / len(creators)
    plan_creators = []
    
    for creator in creators:
        expected_clicks = budget_per_creator / creator.cpc
        expected_conversions = expected_clicks * (creator.cvr / 100) if creator.cvr else 0
        
        plan_creators.append(PlanCreator(
            creator_id=creator.creator_id,
            name=creator.name,
            expected_clicks=expected_clicks,
            expected_conversions=expected_conversions,
            expected_spend=budget_per_creator,
            cpc=creator.cpc,
            cvr=creator.cvr
        ))
    
    total_clicks = sum(pc.expected_clicks for pc in plan_creators)
    total_conversions = sum(pc.expected_conversions for pc in plan_creators)
    total_cpa = (plan_request.budget / total_conversions) if total_conversions > 0 else None
    
    return PlanResponse(
        plan_id="basic_plan",
        total_budget=plan_request.budget,
        estimated_clicks=total_clicks,
        estimated_conversions=total_conversions,
        estimated_cpa=total_cpa,
        creators=plan_creators
    )

@router.post("/plan-smart", response_model=PlanResponse)
async def create_smart_plan(
    plan_request: PlanRequest,
    db: Session = Depends(get_db)
) -> PlanResponse:
    """Create a smart plan using advanced matching algorithms"""
    
    try:
        # Use smart matching service
        smart_service = SmartMatchingService(db)
        matched_creators = smart_service.find_smart_creators(
            advertiser_id=plan_request.advertiser_id,
            category=plan_request.category,
            max_creators=plan_request.max_creators
        )
        
        if not matched_creators:
            return PlanResponse(
                plan_id="smart_plan",
                total_budget=0,
                estimated_clicks=0,
                estimated_conversions=0,
                estimated_cpa=None,
                creators=[]
            )
        
        # Calculate CPC (use average from matched creators)
        total_cpc = sum(c['creator'].cpc for c in matched_creators if c['creator'].cpc)
        avg_cpc = total_cpc / len([c for c in matched_creators if c['creator'].cpc]) if matched_creators else 1.0
        
        # Use enhanced allocation logic with vector-CPA matching
        plan_creators = _allocate_creators_with_vector_cpa_logic(
            matched_creators, plan_request, avg_cpc, db
        )
        
        if not plan_creators:
            return PlanResponse(
                plan_id="smart_plan",
                total_budget=0,
                estimated_clicks=0,
                estimated_conversions=0,
                estimated_cpa=None,
                creators=[]
            )
        
        # Calculate totals
        total_clicks = sum(pc.expected_clicks for pc in plan_creators)
        total_conversions = sum(pc.expected_conversions for pc in plan_creators)
        total_spend = sum(pc.expected_spend for pc in plan_creators)
        total_cpa = (total_spend / total_conversions) if total_conversions > 0 else None
        
        return PlanResponse(
            plan_id="smart_plan",
            total_budget=total_spend,
            estimated_clicks=total_clicks,
            estimated_conversions=total_conversions,
            estimated_cpa=total_cpa,
            creators=plan_creators
        )
        
    except Exception as e:
        print(f"Error in smart plan creation: {e}")
        return PlanResponse(
            plan_id="smart_plan",
            total_budget=0,
            estimated_clicks=0,
            estimated_conversions=0,
            estimated_cpa=None,
            creators=[]
        )

def _allocate_creators_with_vector_cpa_logic(
    matched_creators: List[Dict[str, Any]], 
    plan_request: PlanRequest, 
    cpc: float, 
    db: Session
) -> List[PlanCreator]:
    """Enhanced allocation logic with proper budget utilization and CPA targeting"""
    
    print("DEBUG: Starting enhanced budget-CPA allocation logic")
    
    # Separate creators by phase and CPA status
    phase1_creators = []  # Same category/brand with CPA
    phase2_creators = []  # Cross category/brand with CPA
    phase3_creators = []  # No CPA data
    
    for creator_data in matched_creators:
        performance_data = creator_data['performance_data']
        phase = performance_data.get('phase', 3)
        
        if phase == 1 and performance_data.get('expected_cpa') is not None:
            # Phase 1: Same category/brand with CPA
            if plan_request.target_cpa is None or performance_data['expected_cpa'] <= plan_request.target_cpa:
                phase1_creators.append(creator_data)
        elif phase == 2 and performance_data.get('expected_cpa') is not None:
            # Phase 2: Cross category/brand with CPA
            if plan_request.target_cpa is None or performance_data['expected_cpa'] <= plan_request.target_cpa:
                phase2_creators.append(creator_data)
        else:
            # Phase 3: No CPA data
            phase3_creators.append(creator_data)
    
    print(f"DEBUG: Phase 1 (same CPA): {len(phase1_creators)}, Phase 2 (cross CPA): {len(phase2_creators)}, Phase 3 (no CPA): {len(phase3_creators)}")
    
    # Sort CPA creators by CPA (lowest first)
    phase1_creators.sort(key=lambda x: x['performance_data']['expected_cpa'])
    phase2_creators.sort(key=lambda x: x['performance_data']['expected_cpa'])
    
    # Get vector data for similarity matching
    creator_vectors = {}
    if phase3_creators:
        creator_ids = [c['creator'].creator_id for c in phase3_creators]
        vectors = db.query(CreatorVector).filter(CreatorVector.creator_id.in_(creator_ids)).all()
        creator_vectors = {v.creator_id: v.vector for v in vectors}
        print(f"DEBUG: Loaded vectors for {len(creator_vectors)} creators")
    
    # Allocation logic
    picked_creators = []
    creator_placement_counts = {}
    remaining_budget = plan_request.budget
    
    # Phase 1: Same category/brand CPA creators
    print("DEBUG: Phase 1 - Allocating same category/brand CPA creators")
    for creator_data in phase1_creators:
        if remaining_budget <= 0:
            break
            
        creator = creator_data['creator']
        performance_data = creator_data['performance_data']
        creator_id = creator.creator_id
        current_placements = creator_placement_counts.get(creator_id, 0)
        
        if current_placements >= 3:
            continue
            
        # Calculate allocation
        expected_clicks = performance_data.get('expected_clicks', 100)
        expected_spend = cpc * expected_clicks
        
        if expected_spend <= remaining_budget:
            picked_creators.append(_create_plan_creator(creator, creator_data, cpc, plan_request))
            creator_placement_counts[creator_id] = current_placements + 1
            remaining_budget -= expected_spend
            print(f"DEBUG: Phase 1 - Added {creator.name} (CPA: {performance_data['expected_cpa']:.2f}, placement {current_placements + 1})")
    
    # Phase 2: Cross category/brand CPA creators
    print("DEBUG: Phase 2 - Allocating cross category/brand CPA creators")
    for creator_data in phase2_creators:
        if remaining_budget <= 0:
            break
            
        creator = creator_data['creator']
        performance_data = creator_data['performance_data']
        creator_id = creator.creator_id
        current_placements = creator_placement_counts.get(creator_id, 0)
        
        if current_placements >= 3:
            continue
            
        # Calculate allocation
        expected_clicks = performance_data.get('expected_clicks', 100)
        expected_spend = cpc * expected_clicks
        
        if expected_spend <= remaining_budget:
            picked_creators.append(_create_plan_creator(creator, creator_data, cpc, plan_request))
            creator_placement_counts[creator_id] = current_placements + 1
            remaining_budget -= expected_spend
            print(f"DEBUG: Phase 2 - Added {creator.name} (CPA: {performance_data['expected_cpa']:.2f}, placement {current_placements + 1})")
    
    # Phase 3: Vector-similar creators (no CPA data)
    print("DEBUG: Phase 3 - Allocating vector-similar creators")
    if remaining_budget > 0 and phase3_creators:
        # Sort by vector similarity to CPA creators
        reference_creators = phase1_creators + phase2_creators
        vector_similar_creators = _sort_by_vector_similarity(
            phase3_creators, reference_creators, creator_vectors
        )
        
        for creator_data in vector_similar_creators:
            if remaining_budget <= 0:
                break
                
            creator = creator_data['creator']
            creator_id = creator.creator_id
            current_placements = creator_placement_counts.get(creator_id, 0)
            
            if current_placements >= 3:
                continue
                
            # Calculate allocation
            expected_clicks = creator.conservative_click_estimate or 100
            expected_spend = cpc * expected_clicks
            
            if expected_spend <= remaining_budget:
                picked_creators.append(_create_plan_creator(creator, creator_data, cpc, plan_request))
                creator_placement_counts[creator_id] = current_placements + 1
                remaining_budget -= expected_spend
                print(f"DEBUG: Phase 3 - Added {creator.name} (placement {current_placements + 1})")
    
    # Budget optimization: Add more placements to existing creators
    print("DEBUG: Budget optimization - Adding more placements to existing creators")
    if remaining_budget > 0:
        # Try to add more placements to existing creators (up to 3 total per creator)
        for creator_data in picked_creators:
            if remaining_budget <= 0:
                break
                
            creator = creator_data['creator']
            creator_id = creator.creator_id
            current_placements = creator_placement_counts.get(creator_id, 0)
            
            if current_placements >= 3:
                continue
                
            # Calculate allocation for additional placement
            expected_clicks = creator.conservative_click_estimate or 100
            expected_spend = cpc * expected_clicks
            
            if expected_spend <= remaining_budget:
                picked_creators.append(_create_plan_creator(creator, creator_data, cpc, plan_request))
                creator_placement_counts[creator_id] = current_placements + 1
                remaining_budget -= expected_spend
                print(f"DEBUG: Budget opt - Added {creator.name} (placement {current_placements + 1})")
    
    print(f"DEBUG: Enhanced allocation complete - {len(picked_creators)} creators, ${plan_request.budget - remaining_budget:.2f} spent")
    return picked_creators

def _sort_by_vector_similarity(
    phase3_creators: List[Dict[str, Any]], 
    reference_creators: List[Dict[str, Any]], 
    creator_vectors: Dict[int, List[float]]
) -> List[Dict[str, Any]]:
    """Sort Phase 3 creators by vector similarity to reference creators"""
    
    if not reference_creators or not creator_vectors:
        return phase3_creators
    
    # Get reference vectors
    reference_vectors = []
    for ref_creator in reference_creators:
        creator_id = ref_creator['creator'].creator_id
        if creator_id in creator_vectors:
            reference_vectors.append(creator_vectors[creator_id])
    
    if not reference_vectors:
        return phase3_creators
    
    # Calculate similarity scores
    similarity_scores = []
    for creator_data in phase3_creators:
        creator_id = creator_data['creator'].creator_id
        if creator_id in creator_vectors:
            creator_vector = creator_vectors[creator_id]
            max_similarity = 0
            
            for ref_vector in reference_vectors:
                similarity = _cosine_similarity(creator_vector, ref_vector)
                max_similarity = max(max_similarity, similarity)
            
            similarity_scores.append((creator_data, max_similarity))
        else:
            similarity_scores.append((creator_data, 0))
    
    # Sort by similarity (highest first)
    similarity_scores.sort(key=lambda x: x[1], reverse=True)
    
    return [creator_data for creator_data, _ in similarity_scores]

def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    import numpy as np
    
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    try:
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    except:
        return 0.0

def _create_plan_creator(
    creator: Creator, 
    creator_data: Dict[str, Any], 
    cpc: float, 
    plan_request: PlanRequest
) -> PlanCreator:
    """Create a PlanCreator object from creator data"""
    
    performance_data = creator_data.get('performance_data', {})
    
    # Use performance data if available, otherwise use creator defaults
    expected_clicks = performance_data.get('expected_clicks', creator.conservative_click_estimate or 100)
    expected_cvr = performance_data.get('expected_cvr', creator.cvr or 2.5)
    expected_conversions = expected_clicks * (expected_cvr / 100)
    expected_spend = cpc * expected_clicks
    
    return PlanCreator(
        creator_id=creator.creator_id,
        name=creator.name,
        expected_clicks=expected_clicks,
        expected_conversions=expected_conversions,
        expected_spend=expected_spend,
        cpc=cpc,
        cvr=expected_cvr
    )

@router.get("/historical-data")
async def get_historical_data(
    advertiser_id: Optional[int] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
) -> HistoricalDataResponse:
    """Get historical performance data"""
    
    # Parse dates
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except:
            start_dt = datetime.now() - timedelta(days=30)
    else:
        start_dt = datetime.now() - timedelta(days=30)
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except:
            end_dt = datetime.now()
    else:
        end_dt = datetime.now()
    
    # Get clicks data
    clicks_query = db.query(ClickUnique).filter(
        ClickUnique.date >= start_dt,
        ClickUnique.date <= end_dt
    )
    
    if advertiser_id:
        clicks_query = clicks_query.filter(ClickUnique.advertiser_id == advertiser_id)
    if category:
        clicks_query = clicks_query.filter(ClickUnique.category == category)
    
    clicks_data = clicks_query.all()
    
    # Get conversions data
    conversions_query = db.query(Conversion).filter(
        Conversion.date >= start_dt,
        Conversion.date <= end_dt
    )
    
    if advertiser_id:
        conversions_query = conversions_query.filter(Conversion.advertiser_id == advertiser_id)
    if category:
        conversions_query = conversions_query.filter(Conversion.category == category)
    
    conversions_data = conversions_query.all()
    
    # Aggregate data by date
    daily_data = {}
    
    for click in clicks_data:
        date_str = click.date.strftime('%Y-%m-%d')
        if date_str not in daily_data:
            daily_data[date_str] = {'clicks': 0, 'conversions': 0}
        daily_data[date_str]['clicks'] += click.clicks
    
    for conversion in conversions_data:
        date_str = conversion.date.strftime('%Y-%m-%d')
        if date_str not in daily_data:
            daily_data[date_str] = {'clicks': 0, 'conversions': 0}
        daily_data[date_str]['conversions'] += conversion.conversions
    
    # Convert to list format
    historical_data = []
    for date_str in sorted(daily_data.keys()):
        data = daily_data[date_str]
        historical_data.append({
            'date': date_str,
            'clicks': data['clicks'],
            'conversions': data['conversions'],
            'cvr': (data['conversions'] / data['clicks'] * 100) if data['clicks'] > 0 else 0
        })
    
    # Calculate totals
    total_clicks = sum(data['clicks'] for data in daily_data.values())
    total_conversions = sum(data['conversions'] for data in daily_data.values())
    overall_cvr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
    
    return HistoricalDataResponse(
        historical_data=historical_data,
        total_clicks=total_clicks,
        total_conversions=total_conversions,
        overall_cvr=overall_cvr,
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat()
    )

@router.get("/debug/clicks")
async def debug_clicks(
    advertiser_id: Optional[int] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Debug endpoint to check click data"""
    
    # Get total clicks
    clicks_query = db.query(func.sum(ClickUnique.clicks))
    if advertiser_id:
        clicks_query = clicks_query.filter(ClickUnique.advertiser_id == advertiser_id)
    if category:
        clicks_query = clicks_query.filter(ClickUnique.category == category)
    
    total_clicks = clicks_query.scalar() or 0
    
    # Get unique advertisers and categories
    advertisers = db.query(ClickUnique.advertiser_id).distinct().all()
    categories = db.query(ClickUnique.category).distinct().all()
    
    # Get sample click records
    sample_clicks = db.query(ClickUnique).limit(10).all()
    
    return {
        "total_clicks": total_clicks,
        "unique_advertisers": [a[0] for a in advertisers if a[0]],
        "unique_categories": [c[0] for c in categories if c[0]],
        "sample_records": [
            {
                "creator_id": c.creator_id,
                "advertiser_id": c.advertiser_id,
                "category": c.category,
                "clicks": c.clicks,
                "date": c.date.isoformat() if c.date else None
            }
            for c in sample_clicks
        ]
    }

@router.get("/campaign-forecast")
async def get_campaign_forecast(
    request: CampaignForecastRequest,
    db: Session = Depends(get_db)
) -> CampaignForecastResponse:
    """Get campaign forecast based on historical data"""
    
    # Get historical performance data
    start_date = datetime.now() - timedelta(days=request.lookback_days)
    
    # Get clicks and conversions for the specified period
    clicks_query = db.query(func.sum(ClickUnique.clicks)).filter(
        ClickUnique.date >= start_date
    )
    conversions_query = db.query(func.sum(Conversion.conversions)).filter(
        Conversion.date >= start_date
    )
    
    if request.advertiser_id:
        clicks_query = clicks_query.filter(ClickUnique.advertiser_id == request.advertiser_id)
        conversions_query = conversions_query.filter(Conversion.advertiser_id == request.advertiser_id)
    if request.category:
        clicks_query = clicks_query.filter(ClickUnique.category == request.category)
        conversions_query = conversions_query.filter(Conversion.category == request.category)
    
    total_clicks = clicks_query.scalar() or 0
    total_conversions = conversions_query.scalar() or 0
    
    # Calculate metrics
    historical_cvr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 2.5
    historical_cpa = (request.budget / total_conversions) if total_conversions > 0 else None
    
    # Forecast based on budget
    forecasted_clicks = request.budget / request.avg_cpc if request.avg_cpc > 0 else 0
    forecasted_conversions = forecasted_clicks * (historical_cvr / 100)
    forecasted_cpa = (request.budget / forecasted_conversions) if forecasted_conversions > 0 else None
    
    return CampaignForecastResponse(
        historical_cvr=historical_cvr,
        historical_cpa=historical_cpa,
        forecasted_clicks=forecasted_clicks,
        forecasted_conversions=forecasted_conversions,
        forecasted_cpa=forecasted_cpa,
        confidence_score=0.8  # Placeholder
    )
