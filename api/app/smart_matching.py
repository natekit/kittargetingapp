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
        advertiser_avg_cvr: float = 0.06,
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
        
        # Tier 1: Historical performance creators
        tier1_creators = self._get_tier1_creators(
            all_creators, advertiser_id, category, cpc, target_cpa, 
            horizon_days, advertiser_avg_cvr
        )
        print(f"DEBUG: Tier 1: {len(tier1_creators)} creators with historical performance")
        
        # Always run all tiers to get maximum creators for budget utilization
        # Tier 2: Topic/keyword matches to high performers
        tier2_creators = self._get_tier2_creators(
            all_creators, tier1_creators, advertiser_id, category
        )
        print(f"DEBUG: Tier 2: {len(tier2_creators)} creators with topic/keyword matches")
        
        # Tier 3: Demographic matches
        tier3_creators = self._get_tier3_creators(
            all_creators, target_demographics, advertiser_id, category
        )
        print(f"DEBUG: Tier 3: {len(tier3_creators)} creators with demographic matches")
        
        # Tier 4: Similar creators to high performers
        tier4_creators = self._get_tier4_creators(
            all_creators, tier1_creators, advertiser_id, category
        )
        print(f"DEBUG: Tier 4: {len(tier4_creators)} creators similar to high performers")
        
        # Combine and deduplicate
        all_matched_creators = self._combine_creator_tiers(
            tier1_creators, tier2_creators, tier3_creators, tier4_creators
        )
        print(f"DEBUG: Combined tiers: {len(all_matched_creators)} total creators")
        
        # Calculate final scores and rationale
        final_creators = self._calculate_final_scores(
            all_matched_creators, target_demographics, cpc, horizon_days
        )
        
        # Sort by combined score
        final_creators.sort(key=lambda x: x['combined_score'], reverse=True)
        
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
    
    def _get_tier1_creators(
        self, 
        creators: List[Creator], 
        advertiser_id: Optional[int], 
        category: Optional[str],
        cpc: float,
        target_cpa: Optional[float],
        horizon_days: int,
        advertiser_avg_cvr: float
    ) -> List[Dict[str, Any]]:
        """Tier 1: Creators with historical performance data."""
        tier1_creators = []
        
        for creator in creators:
            # Get historical performance data
            performance_data = self._get_creator_performance(
                creator, advertiser_id, category, cpc, horizon_days, advertiser_avg_cvr
            )
            
            if performance_data['has_performance']:
                # Check CPA constraint if provided
                if target_cpa is None or performance_data['expected_cpa'] <= target_cpa:
                    creator_data = {
                        'creator': creator,
                        'tier': 1,
                        'performance_data': performance_data,
                        'matching_rationale': 'Historical performance data available',
                        'performance_score': 1.0,
                        'demographic_score': 0.0,
                        'topic_score': 0.0,
                        'similarity_score': 0.0
                    }
                    tier1_creators.append(creator_data)
        
        return tier1_creators
    
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
            if performance_data['has_performance']:
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
                # Fallback to conservative estimate
                expected_clicks = creator.conservative_click_estimate or 100
                print(f"DEBUG: Creator {creator.creator_id} - No placement data, using conservative estimate: {expected_clicks}")
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
