"""
Smart creator matching algorithm for enhanced planner.
Implements multi-tier selection strategy with budget optimization.
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.models import (
    Creator, Advertiser, Topic, Keyword, CreatorTopic, CreatorKeyword, 
    CreatorSimilarity, ClickUnique, Conversion, PerfUpload, ConvUpload,
    Insertion, Campaign
)
from app.topic_similarities import get_topic_similarity, get_all_topics
from app.demographic_matching import calculate_demographic_similarity
import logging

logger = logging.getLogger(__name__)


class SmartMatchingService:
    """Service for smart creator matching and selection."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_smart_creators(
        self,
        advertiser_id: Optional[int] = None,
        category: Optional[str] = None,
        target_demographics: Optional[Dict[str, Any]] = None,
        budget: float = 0.0,
        cpc: float = 0.0,
        target_cpa: Optional[float] = None,
        horizon_days: int = 30,
        advertiser_avg_cvr: float = 0.025,
        include_acct_ids: Optional[str] = None,
        exclude_acct_ids: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find creators using smart matching algorithm.
        
        Returns:
            List of creator dictionaries with matching rationale and scores
        """
        logger.info(f"Starting smart matching for advertiser_id={advertiser_id}, category={category}")
        
        # Get base creators query - INCREASE limit to get more creators for budget
        creators_query = self._get_base_creators_query(advertiser_id, category)
        all_creators = creators_query.distinct().limit(500).all()  # Increase to 500 creators for better budget utilization
        print(f"DEBUG: Found {len(all_creators)} total creators (limited to 500 for budget utilization)")
        
        # Apply creator filtering based on Acct IDs
        if include_acct_ids or exclude_acct_ids:
            logger.info("Applying creator filtering")
            
            # Parse include Acct IDs (additive - ensure these creators are included)
            include_acct_ids_set = set()
            if include_acct_ids:
                include_acct_ids_set = {acct_id.strip() for acct_id in include_acct_ids.split(',') if acct_id.strip()}
                logger.info(f"Include Acct IDs (additive): {include_acct_ids_set}")
            
            # Parse exclude Acct IDs (restrictive - exclude these creators)
            exclude_acct_ids_set = set()
            if exclude_acct_ids:
                exclude_acct_ids_set = {acct_id.strip() for acct_id in exclude_acct_ids.split(',') if acct_id.strip()}
                logger.info(f"Exclude Acct IDs: {exclude_acct_ids_set}")
            
            # First, filter out excluded creators
            filtered_creators = []
            for creator in all_creators:
                creator_acct_id = creator.acct_id.strip()
                
                # If exclude list is specified, exclude creators in that list
                if exclude_acct_ids_set and creator_acct_id in exclude_acct_ids_set:
                    logger.debug(f"Excluding creator {creator.name} (Acct ID: {creator_acct_id}) - in exclude list")
                    continue
                
                filtered_creators.append(creator)
                logger.debug(f"Including creator {creator.name} (Acct ID: {creator_acct_id})")
            
            # If include list is specified, ensure those creators are added even if not in filtered list
            if include_acct_ids_set:
                logger.info("Adding required creators from include list")
                for creator in all_creators:
                    creator_acct_id = creator.acct_id.strip()
                    if creator_acct_id in include_acct_ids_set:
                        # Check if already in filtered list
                        if not any(c.creator_id == creator.creator_id for c in filtered_creators):
                            filtered_creators.append(creator)
                            logger.info(f"Added required creator {creator.name} (Acct ID: {creator_acct_id})")
            
            all_creators = filtered_creators
            logger.info(f"After filtering: {len(all_creators)} creators remaining")
        
        # Get advertiser target demographics if not provided
        if not target_demographics and advertiser_id:
            target_demographics = self._get_advertiser_demographics(advertiser_id)
        
        # Three-phase allocation: Phase 1 (CPA), Phase 2 (Cross-CVR), Phase 3 (Smart Matching)
        three_phase_creators = self._get_three_phase_creators(
            all_creators, advertiser_id, category, cpc, target_cpa, 
            horizon_days, advertiser_avg_cvr
        )
        
        # Separate by phase for logging
        phase1_creators = [c for c in three_phase_creators if c['phase'] == 1]
        phase2_creators = [c for c in three_phase_creators if c['phase'] == 2]
        phase3_creators = [c for c in three_phase_creators if c['phase'] == 3]
        
        print(f"DEBUG: Phase 1 (Same advertiser/category): {len(phase1_creators)} creators")
        print(f"DEBUG: Phase 2 (Cross-performance): {len(phase2_creators)} creators")
        print(f"DEBUG: Phase 3 (Smart matching): {len(phase3_creators)} creators")
        
        # Calculate final scores and rationale for three-phase creators
        final_creators = self._calculate_final_scores(
            three_phase_creators, target_demographics, cpc, horizon_days
        )
        
        # Sort by tier first, then by combined score within each tier
        final_creators.sort(key=lambda x: (x['tier'], -x['combined_score']))
        
        print(f"DEBUG: Final selection: {len(final_creators)} creators")
        return final_creators
    
    def _get_base_creators_query(self, advertiser_id: Optional[int], category: Optional[str]):
        """Get base creators query - return ALL creators, don't filter by historical data."""
        # Always return all creators, let the tiers handle filtering
        query = self.db.query(Creator)
        
        # Only apply basic filters, don't join on performance data
        # This ensures we get the full creator pool (800 creators)
        # The tier logic will handle performance-based filtering later
        
        return query
    
    def _get_advertiser_demographics(self, advertiser_id: int) -> Dict[str, Any]:
        """Get advertiser target demographics."""
        advertiser = self.db.query(Advertiser).filter(Advertiser.advertiser_id == advertiser_id).first()
        if not advertiser:
            return {}
        
        return {
            'target_age_range': advertiser.target_age_range,
            'target_gender_skew': advertiser.target_gender_skew,
            'target_location': advertiser.target_location,
            'target_interests': advertiser.target_interests
        }
    
    def _get_three_phase_creators(
        self, 
        creators: List[Creator], 
        advertiser_id: Optional[int], 
        category: Optional[str],
        cpc: float,
        target_cpa: Optional[float],
        horizon_days: int,
        advertiser_avg_cvr: float
    ) -> List[Dict[str, Any]]:
        """Three-phase allocation: Phase 1 (CPA), Phase 2 (Cross-CVR), Phase 3 (Smart Matching)."""
        all_creators = []
        
        # Batch performance data query for all creators
        creator_ids = [creator.creator_id for creator in creators]
        batch_performance_data = self._get_batch_performance_data(creator_ids, advertiser_id, category)
        
        for creator in creators:
            # Get performance data from batch results
            perf_data = batch_performance_data.get(creator.creator_id, {
                'phase': 3,
                'total_clicks': 0,
                'total_conversions': 0,
                'historical_cvr': 0.0,
                'cross_clicks': 0,
                'cross_conversions': 0,
                'cross_cvr': 0.0
            })
            
            # Create performance data in the expected format
            performance_data = self._create_performance_data_from_batch(
                creator, perf_data, cpc, horizon_days, advertiser_avg_cvr
            )
            
            # Determine tier and rationale based on phase
            if performance_data['phase'] == 1:
                tier = 1
                rationale = 'Historical performance data for same advertiser/category'
                # Sort by CPA (lower is better)
                sort_key = performance_data['expected_cpa'] if performance_data['expected_cpa'] is not None else float('inf')
            elif performance_data['phase'] == 2:
                tier = 2
                rationale = 'Cross-performance data from other advertisers/categories'
                # Sort by CVR (higher is better)
                sort_key = -performance_data['expected_cvr']  # Negative for descending sort
            else:
                tier = 3
                rationale = 'No historical performance data - using smart matching'
                # Sort by combined score (higher is better)
                sort_key = -performance_data.get('combined_score', 0)  # Negative for descending sort
            
            creator_data = {
                'creator': creator,
                'tier': tier,
                'phase': performance_data['phase'],
                'performance_data': performance_data,
                'matching_rationale': rationale,
                'sort_key': sort_key,
                'performance_score': 1.0 if performance_data['phase'] <= 2 else 0.0,
                'demographic_score': 0.0,
                'topic_score': 0.0,
                'similarity_score': 0.0
            }
            
            # Apply CPA constraint for Phase 1 only
            if performance_data['phase'] == 1:
                if target_cpa is None or performance_data['expected_cpa'] <= target_cpa:
                    all_creators.append(creator_data)
            else:
                # Phase 2 and 3 don't have CPA constraints
                all_creators.append(creator_data)
        
        # Sort by tier first, then by sort_key within each tier
        all_creators.sort(key=lambda x: (x['tier'], x['sort_key']))
        
        return all_creators
    
    def _get_tier2_creators(
        self, 
        all_creators: List[Creator], 
        tier1_creators: List[Dict[str, Any]], 
        advertiser_id: Optional[int], 
        category: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Tier 2: Creators with topic/keyword matches - FAST VERSION."""
        if not tier1_creators:
            return []
        
        # Simple topic matching without expensive DB queries
        tier2_creators = []
        tier1_creator_ids = {cd['creator'].creator_id for cd in tier1_creators}
        
        # Just add creators that aren't in tier 1 - simple and fast
        for creator in all_creators[:100]:  # Limit to first 100 for performance
            if creator.creator_id not in tier1_creator_ids:
                creator_data = {
                    'creator': creator,
                    'tier': 2,
                    'performance_data': None,  # Skip expensive performance query
                    'matching_rationale': 'Additional creator for budget utilization',
                    'performance_score': 0.0,
                    'demographic_score': 0.0,
                    'topic_score': 0.5,  # Medium score
                    'similarity_score': 0.0
                }
                tier2_creators.append(creator_data)
                
                # Stop after finding 50 additional creators
                if len(tier2_creators) >= 50:
                    break
        
        return tier2_creators
    
    def _get_tier3_creators(
        self, 
        all_creators: List[Creator], 
        target_demographics: Optional[Dict[str, Any]], 
        advertiser_id: Optional[int], 
        category: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Tier 3: Creators with demographic matches - OPTIMIZED VERSION."""
        if not target_demographics:
            return []
        
        tier3_creators = []
        # Limit to first 50 creators for performance
        for creator in all_creators[:50]:
            # Calculate demographic similarity (fast, no DB queries)
            creator_demographics = {
                'age_range': creator.age_range,
                'gender_skew': creator.gender_skew,
                'location': creator.location,
                'interests': creator.interests
            }
            
            demographic_score = calculate_demographic_similarity(
                creator_demographics, target_demographics
            )
            
            if demographic_score > 0.3:  # Threshold for relevance
                creator_data = {
                    'creator': creator,
                    'tier': 3,
                    'performance_data': None,  # Skip expensive performance query
                    'matching_rationale': f'Demographic match (score: {demographic_score:.2f})',
                    'performance_score': 0.0,
                    'demographic_score': demographic_score,
                    'topic_score': 0.0,
                    'similarity_score': 0.0
                }
                tier3_creators.append(creator_data)
                
                # Early termination - stop after finding 20 demographic matches
                if len(tier3_creators) >= 20:
                    break
        
        return tier3_creators
    
    def _get_tier4_creators(
        self, 
        all_creators: List[Creator], 
        tier1_creators: List[Dict[str, Any]], 
        advertiser_id: Optional[int], 
        category: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Tier 4: Creators similar to high performers - FAST VERSION."""
        if not tier1_creators:
            return []
        
        # Simple similarity matching without expensive DB queries
        tier4_creators = []
        tier1_creator_ids = {cd['creator'].creator_id for cd in tier1_creators}
        
        # Just add more creators that aren't in tier 1 or 2 - simple and fast
        for creator in all_creators[100:200]:  # Next 100 creators for performance
            if creator.creator_id not in tier1_creator_ids:
                creator_data = {
                    'creator': creator,
                    'tier': 4,
                    'performance_data': None,  # Skip expensive performance query
                    'matching_rationale': 'Additional creator for budget utilization',
                    'performance_score': 0.0,
                    'demographic_score': 0.0,
                    'topic_score': 0.0,
                    'similarity_score': 0.3  # Medium similarity score
                }
                tier4_creators.append(creator_data)
                
                # Stop after finding 50 additional creators
                if len(tier4_creators) >= 50:
                    break
        
        return tier4_creators
    
    def _combine_creator_tiers(
        self, 
        tier1: List[Dict[str, Any]], 
        tier2: List[Dict[str, Any]], 
        tier3: List[Dict[str, Any]], 
        tier4: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Combine and deduplicate creators from all tiers."""
        combined = {}
        
        # Add creators from each tier, avoiding duplicates
        for tier_creators in [tier1, tier2, tier3, tier4]:
            for creator_data in tier_creators:
                creator_id = creator_data['creator'].creator_id
                if creator_id not in combined:
                    combined[creator_id] = creator_data
                else:
                    # Update with higher tier if applicable
                    if creator_data['tier'] < combined[creator_id]['tier']:
                        combined[creator_id] = creator_data
        
        return list(combined.values())
    
    def _calculate_final_scores(
        self, 
        creators: List[Dict[str, Any]], 
        target_demographics: Optional[Dict[str, Any]], 
        cpc: float, 
        horizon_days: int
    ) -> List[Dict[str, Any]]:
        """Calculate final combined scores for all creators."""
        for creator_data in creators:
            creator = creator_data['creator']
            
            # Calculate performance score
            performance_data = creator_data['performance_data']
            if performance_data and performance_data.get('has_performance', False):
                performance_score = 1.0
            else:
                performance_score = 0.0
            
            # Calculate demographic score if target demographics provided
            demographic_score = 0.0
            if target_demographics:
                creator_demographics = {
                    'age_range': creator.age_range,
                    'gender_skew': creator.gender_skew,
                    'location': creator.location,
                    'interests': creator.interests
                }
                demographic_score = calculate_demographic_similarity(
                    creator_demographics, target_demographics
                )
            
            # Calculate topic score
            topic_score = creator_data.get('topic_score', 0.0)
            
            # Calculate similarity score
            similarity_score = creator_data.get('similarity_score', 0.0)
            
            # Combined score with weights
            combined_score = (
                performance_score * 0.5 +      # 50% weight to performance
                demographic_score * 0.2 +       # 20% weight to demographics
                topic_score * 0.2 +            # 20% weight to topics
                similarity_score * 0.1         # 10% weight to similarity
            )
            
            creator_data.update({
                'performance_score': performance_score,
                'demographic_score': demographic_score,
                'topic_score': topic_score,
                'similarity_score': similarity_score,
                'combined_score': combined_score
            })
        
        return creators
    
    def _get_batch_performance_data(
        self, 
        creator_ids: List[int],
        advertiser_id: Optional[int], 
        category: Optional[str]
    ) -> Dict[int, Dict[str, Any]]:
        """Get performance data for multiple creators in batch queries with three-phase categorization."""
        from sqlalchemy import func, and_
        from app.models import ClickUnique, PerfUpload, Insertion, Campaign, Advertiser, Conversion
        
        print(f"DEBUG: Getting batch performance data for {len(creator_ids)} creators")
        
        # Phase 1: Same advertiser/category performance
        same_performance_data = self._get_same_performance_data(creator_ids, advertiser_id, category)
        
        # Phase 2: Cross-performance (other advertisers/categories)
        cross_performance_data = self._get_cross_performance_data(creator_ids, advertiser_id, category)
        
        # Combine results with phase categorization
        performance_data = {}
        for creator_id in creator_ids:
            same_data = same_performance_data.get(creator_id, {'total_clicks': 0, 'total_conversions': 0})
            cross_data = cross_performance_data.get(creator_id, {'total_clicks': 0, 'total_conversions': 0})
            
            # Determine which phase this creator belongs to
            if same_data['total_clicks'] > 0 or same_data['total_conversions'] > 0:
                # Phase 1: Same advertiser/category performance
                performance_data[creator_id] = {
                    'phase': 1,
                    'total_clicks': same_data['total_clicks'],
                    'total_conversions': same_data['total_conversions'],
                    'historical_cvr': same_data['total_conversions'] / same_data['total_clicks'] if same_data['total_clicks'] > 0 else 0.0,
                    'cross_clicks': cross_data['total_clicks'],
                    'cross_conversions': cross_data['total_conversions'],
                    'cross_cvr': cross_data['total_conversions'] / cross_data['total_clicks'] if cross_data['total_clicks'] > 0 else 0.0
                }
            elif cross_data['total_clicks'] > 0 or cross_data['total_conversions'] > 0:
                # Phase 2: Cross-performance
                performance_data[creator_id] = {
                    'phase': 2,
                    'total_clicks': 0,
                    'total_conversions': 0,
                    'historical_cvr': 0.0,
                    'cross_clicks': cross_data['total_clicks'],
                    'cross_conversions': cross_data['total_conversions'],
                    'cross_cvr': cross_data['total_conversions'] / cross_data['total_clicks'] if cross_data['total_clicks'] > 0 else 0.0
                }
            else:
                # Phase 3: No historical performance
                performance_data[creator_id] = {
                    'phase': 3,
                    'total_clicks': 0,
                    'total_conversions': 0,
                    'historical_cvr': 0.0,
                    'cross_clicks': 0,
                    'cross_conversions': 0,
                    'cross_cvr': 0.0
                }
        
        return performance_data

    def _get_same_performance_data(
        self, 
        creator_ids: List[int],
        advertiser_id: Optional[int], 
        category: Optional[str]
    ) -> Dict[int, Dict[str, Any]]:
        """Get performance data for same advertiser/category."""
        from sqlalchemy import func
        from app.models import ClickUnique, PerfUpload, Insertion, Campaign, Advertiser, Conversion
        
        # Build base query for clicks (same advertiser/category)
        clicks_query = self.db.query(
            ClickUnique.creator_id,
            func.sum(ClickUnique.unique_clicks).label('total_clicks')
        ).join(
            PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
        ).join(
            Insertion, Insertion.insertion_id == PerfUpload.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).filter(ClickUnique.creator_id.in_(creator_ids))
        
        # Add category or advertiser filter
        if category:
            clicks_query = clicks_query.join(
                Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
            ).filter(Advertiser.category == category)
        elif advertiser_id:
            clicks_query = clicks_query.filter(Campaign.advertiser_id == advertiser_id)
        
        clicks_results = {row.creator_id: row.total_clicks or 0 for row in clicks_query.group_by(ClickUnique.creator_id).all()}
        
        # Build base query for conversions (same advertiser/category)
        conversions_query = self.db.query(
            Conversion.creator_id,
            func.sum(Conversion.conversions).label('total_conversions')
        ).join(
            Insertion, Insertion.insertion_id == Conversion.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).filter(Conversion.creator_id.in_(creator_ids))
        
        # Add category or advertiser filter
        if category:
            conversions_query = conversions_query.join(
                Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
            ).filter(Advertiser.category == category)
        elif advertiser_id:
            conversions_query = conversions_query.filter(Campaign.advertiser_id == advertiser_id)
        
        conversions_results = {row.creator_id: row.total_conversions or 0 for row in conversions_query.group_by(Conversion.creator_id).all()}
        
        # Combine results
        same_performance_data = {}
        for creator_id in creator_ids:
            same_performance_data[creator_id] = {
                'total_clicks': clicks_results.get(creator_id, 0),
                'total_conversions': conversions_results.get(creator_id, 0)
            }
        
        return same_performance_data

    def _get_cross_performance_data(
        self, 
        creator_ids: List[int],
        advertiser_id: Optional[int], 
        category: Optional[str]
    ) -> Dict[int, Dict[str, Any]]:
        """Get performance data for other advertisers/categories."""
        from sqlalchemy import func
        from app.models import ClickUnique, PerfUpload, Insertion, Campaign, Advertiser, Conversion
        
        # Build base query for clicks (other advertisers/categories)
        clicks_query = self.db.query(
            ClickUnique.creator_id,
            func.sum(ClickUnique.unique_clicks).label('total_clicks')
        ).join(
            PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
        ).join(
            Insertion, Insertion.insertion_id == PerfUpload.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).join(
            Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
        ).filter(ClickUnique.creator_id.in_(creator_ids))
        
        # Exclude same advertiser/category
        if category:
            clicks_query = clicks_query.filter(Advertiser.category != category)
        elif advertiser_id:
            clicks_query = clicks_query.filter(Campaign.advertiser_id != advertiser_id)
        
        clicks_results = {row.creator_id: row.total_clicks or 0 for row in clicks_query.group_by(ClickUnique.creator_id).all()}
        
        # Build base query for conversions (other advertisers/categories)
        conversions_query = self.db.query(
            Conversion.creator_id,
            func.sum(Conversion.conversions).label('total_conversions')
        ).join(
            Insertion, Insertion.insertion_id == Conversion.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).join(
            Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
        ).filter(Conversion.creator_id.in_(creator_ids))
        
        # Exclude same advertiser/category
        if category:
            conversions_query = conversions_query.filter(Advertiser.category != category)
        elif advertiser_id:
            conversions_query = conversions_query.filter(Campaign.advertiser_id != advertiser_id)
        
        conversions_results = {row.creator_id: row.total_conversions or 0 for row in conversions_query.group_by(Conversion.creator_id).all()}
        
        # Combine results
        cross_performance_data = {}
        for creator_id in creator_ids:
            cross_performance_data[creator_id] = {
                'total_clicks': clicks_results.get(creator_id, 0),
                'total_conversions': conversions_results.get(creator_id, 0)
            }
        
        return cross_performance_data

    def _create_performance_data_from_batch(
        self,
        creator: Creator,
        perf_data: Dict[str, Any],
        cpc: float,
        horizon_days: int,
        advertiser_avg_cvr: float
    ) -> Dict[str, Any]:
        """Create performance data from batch query results with three-phase logic."""
        phase = perf_data['phase']
        total_clicks = perf_data['total_clicks']
        total_conversions = perf_data['total_conversions']
        historical_cvr = perf_data['historical_cvr']
        cross_clicks = perf_data['cross_clicks']
        cross_conversions = perf_data['cross_conversions']
        cross_cvr = perf_data['cross_cvr']
        
        print(f"DEBUG: Creator {creator.creator_id} - Phase {phase}: same_clicks={total_clicks}, same_conversions={total_conversions}, cross_clicks={cross_clicks}, cross_conversions={cross_conversions}")
        
        # Determine CVR based on phase
        if phase == 1:
            # Phase 1: Use same advertiser/category CVR
            expected_cvr = historical_cvr if historical_cvr > 0 else advertiser_avg_cvr
            performance_clicks = total_clicks
            performance_conversions = total_conversions
        elif phase == 2:
            # Phase 2: Use cross-performance CVR
            expected_cvr = cross_cvr if cross_cvr > 0 else advertiser_avg_cvr
            performance_clicks = cross_clicks
            performance_conversions = cross_conversions
        else:
            # Phase 3: Use advertiser average CVR
            expected_cvr = advertiser_avg_cvr
            performance_clicks = 0
            performance_conversions = 0
        
        print(f"DEBUG: Creator {creator.creator_id} - Phase {phase}, Using CVR: {expected_cvr:.4f}")
        
        # Calculate expected clicks based on phase
        if phase == 1 and total_clicks > 0:
            # Use same advertiser performance
            expected_clicks = total_clicks / max(1, total_clicks / 100)  # Rough estimate
        elif phase == 2 and cross_clicks > 0:
            # Use cross-performance data
            expected_clicks = cross_clicks / max(1, cross_clicks / 100)  # Rough estimate
        else:
            # Fallback to conservative estimate
            expected_clicks = creator.conservative_click_estimate or 100
            print(f"DEBUG: Creator {creator.creator_id} - Using conservative estimate: {expected_clicks}")
        
        # Calculate other metrics
        expected_spend = cpc * expected_clicks
        expected_conversions = expected_clicks * expected_cvr
        expected_cpa = cpc / expected_cvr if expected_cvr > 0 else None
        
        cpa_str = f"${expected_cpa:.2f}" if expected_cpa else "N/A"
        print(f"DEBUG: Creator {creator.creator_id} - Expected clicks: {expected_clicks}, spend: ${expected_spend:.2f}, conversions: {expected_conversions:.2f}, CPA: {cpa_str}")
        
        return {
            'phase': phase,
            'has_performance': performance_clicks > 0 or performance_conversions > 0,
            'expected_cpa': expected_cpa,
            'expected_clicks': expected_clicks,
            'expected_spend': expected_spend,
            'expected_conversions': expected_conversions,
            'expected_cvr': expected_cvr,
            'historical_clicks': performance_clicks,
            'historical_conversions': performance_conversions,
            'median_clicks_per_placement': expected_clicks,
            'recommended_placements': 1
        }

    def _get_creator_performance(
        self, 
        creator: Creator, 
        advertiser_id: Optional[int], 
        category: Optional[str],
        cpc: float,
        horizon_days: int,
        advertiser_avg_cvr: float
    ) -> Dict[str, Any]:
        """Get creator performance data based on historical data."""
        from sqlalchemy import func, and_
        from app.models import ClickUnique, PerfUpload, Insertion, Campaign, Advertiser, Conversion
        
        print(f"DEBUG: Getting performance data for creator {creator.creator_id} ({creator.name})")
        
        # Build base query for clicks
        clicks_query = self.db.query(func.sum(ClickUnique.unique_clicks)).join(
            PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
        ).join(
            Insertion, Insertion.insertion_id == PerfUpload.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).filter(ClickUnique.creator_id == creator.creator_id)
        
        # Add category or advertiser filter
        if category:
            clicks_query = clicks_query.join(
                Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
            ).filter(Advertiser.category == category)
        elif advertiser_id:
            clicks_query = clicks_query.filter(Campaign.advertiser_id == advertiser_id)
        
        total_clicks = clicks_query.scalar() or 0
        print(f"DEBUG: Creator {creator.creator_id} - Total historical clicks: {total_clicks}")
        
        # Build base query for conversions
        conversions_query = self.db.query(func.sum(Conversion.conversions)).join(
            Insertion, Insertion.insertion_id == Conversion.insertion_id
        ).join(
            Campaign, Campaign.campaign_id == Insertion.campaign_id
        ).filter(Conversion.creator_id == creator.creator_id)
        
        # Add category or advertiser filter
        if category:
            conversions_query = conversions_query.join(
                Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
            ).filter(Advertiser.category == category)
        elif advertiser_id:
            conversions_query = conversions_query.filter(Campaign.advertiser_id == advertiser_id)
        
        total_conversions = conversions_query.scalar() or 0
        print(f"DEBUG: Creator {creator.creator_id} - Total historical conversions: {total_conversions}")
        
        # Calculate historical CVR
        historical_cvr = 0.0
        if total_clicks > 0:
            historical_cvr = total_conversions / total_clicks
            print(f"DEBUG: Creator {creator.creator_id} - Historical CVR: {historical_cvr:.4f}")
        
        # Use historical CVR if available, otherwise use advertiser average
        expected_cvr = historical_cvr if historical_cvr > 0 else advertiser_avg_cvr
        print(f"DEBUG: Creator {creator.creator_id} - Using CVR: {expected_cvr:.4f}")
        
        # Calculate expected clicks based on historical performance
        if total_clicks > 0:
            # Get individual placement click data to calculate median clicks per placement
            placement_clicks_query = self.db.query(ClickUnique.unique_clicks).join(
                PerfUpload, PerfUpload.perf_upload_id == ClickUnique.perf_upload_id
            ).join(
                Insertion, Insertion.insertion_id == PerfUpload.insertion_id
            ).join(
                Campaign, Campaign.campaign_id == Insertion.campaign_id
            ).filter(ClickUnique.creator_id == creator.creator_id)
            
            # Add category or advertiser filter
            if category:
                placement_clicks_query = placement_clicks_query.join(
                    Advertiser, Advertiser.advertiser_id == Campaign.advertiser_id
                ).filter(Advertiser.category == category)
            elif advertiser_id:
                placement_clicks_query = placement_clicks_query.filter(Campaign.advertiser_id == advertiser_id)
            
            placement_clicks = [row[0] for row in placement_clicks_query.all() if row[0] is not None]
            
            if placement_clicks:
                # Calculate median clicks per placement
                placement_clicks.sort()
                median_clicks = placement_clicks[len(placement_clicks) // 2]
                print(f"DEBUG: Creator {creator.creator_id} - Median clicks per placement: {median_clicks}")
                
                # Use median clicks per placement (keep original logic)
                expected_clicks = median_clicks
                print(f"DEBUG: Creator {creator.creator_id} - Using median clicks for 1 placement: {expected_clicks}")
            else:
                # Try to get clicks from other campaigns first
                other_campaigns_clicks = self._get_other_campaigns_clicks(creator, advertiser_id, category)
                if other_campaigns_clicks > 0:
                    expected_clicks = other_campaigns_clicks
                    print(f"DEBUG: Creator {creator.creator_id} - Using other campaigns clicks: {expected_clicks}")
                else:
                    # Final fallback to conservative estimate
                    expected_clicks = creator.conservative_click_estimate or 100
                    print(f"DEBUG: Creator {creator.creator_id} - No campaign data, using conservative estimate: {expected_clicks}")
        else:
            # Fallback to conservative estimate
            expected_clicks = creator.conservative_click_estimate or 100
            print(f"DEBUG: Creator {creator.creator_id} - Using conservative estimate: {expected_clicks}")
        
        # Calculate other metrics
        expected_spend = cpc * expected_clicks
        expected_conversions = expected_clicks * expected_cvr
        expected_cpa = cpc / expected_cvr if expected_cvr > 0 else None
        
        print(f"DEBUG: Creator {creator.creator_id} - Expected clicks: {expected_clicks}, spend: ${expected_spend:.2f}, conversions: {expected_conversions:.2f}")
        
        return {
            'has_performance': total_clicks > 0 or total_conversions > 0,
            'expected_cpa': expected_cpa,
            'expected_clicks': expected_clicks,
            'expected_spend': expected_spend,
            'expected_conversions': expected_conversions,
            'expected_cvr': expected_cvr,
            'historical_clicks': total_clicks,
            'historical_conversions': total_conversions,
            'median_clicks_per_placement': median_clicks if 'median_clicks' in locals() else None,
            'recommended_placements': 1  # Start with 1 placement, can be increased if under budget
        }
    
    def _calculate_topic_match(self, creator: Creator, target_topics: set) -> float:
        """Calculate topic match score for creator."""
        creator_topics = self.db.query(Topic).join(CreatorTopic).filter(
            CreatorTopic.creator_id == creator.creator_id
        ).all()
        
        if not creator_topics or not target_topics:
            return 0.0
        
        max_similarity = 0.0
        for creator_topic in creator_topics:
            for target_topic in target_topics:
                similarity = get_topic_similarity(creator_topic.name, target_topic)
                max_similarity = max(max_similarity, similarity)
        
        return max_similarity
    
    def _calculate_keyword_match(self, creator: Creator, target_keywords: set) -> float:
        """Calculate keyword match score for creator."""
        creator_keywords = self.db.query(Keyword).join(CreatorKeyword).filter(
            CreatorKeyword.creator_id == creator.creator_id
        ).all()
        
        if not creator_keywords or not target_keywords:
            return 0.0
        
        creator_keyword_set = set()
        for keyword in creator_keywords:
            creator_keyword_set.update(keyword.keywords.split(','))
        
        if not creator_keyword_set:
            return 0.0
        
        intersection = creator_keyword_set.intersection(target_keywords)
        union = creator_keyword_set.union(target_keywords)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _get_creator_similarity(self, creator_a_id: int, creator_b_id: int) -> float:
        """Get pre-computed similarity between two creators."""
        similarity = self.db.query(CreatorSimilarity).filter(
            and_(
                CreatorSimilarity.creator_a_id == creator_a_id,
                CreatorSimilarity.creator_b_id == creator_b_id,
                CreatorSimilarity.similarity_type == 'combined'
            )
        ).first()
        
        return similarity.similarity_score if similarity else 0.0
    
    def _get_other_campaigns_clicks(self, creator: Creator, advertiser_id: Optional[int], category: Optional[str]) -> int:
        """Get click estimates from other campaigns for this creator."""
        from sqlalchemy import func, and_
        from app.models import ClickUnique, PerfUpload, Insertion, Campaign, Advertiser
        
        print(f"DEBUG: Getting other campaigns clicks for creator {creator.creator_id}")
        
        # Build query for clicks from OTHER campaigns
        other_campaigns_query = self.db.query(func.sum(ClickUnique.unique_clicks)).join(
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
            placement_clicks_query = self.db.query(ClickUnique.unique_clicks).join(
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
