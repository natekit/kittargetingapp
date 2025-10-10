"""
Pre-compute creator similarities for performance optimization.
This script calculates and stores similarity scores between creators.
"""

import time
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Creator, CreatorSimilarity, Topic, Keyword, CreatorTopic, CreatorKeyword
from app.topic_similarities import get_topic_similarity, get_all_topics
from app.demographic_matching import calculate_demographic_similarity
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimilarityComputer:
    """Compute and store creator similarities for performance optimization."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def compute_topic_similarities(self, creators: List[Creator]) -> Dict[Tuple[int, int], float]:
        """Compute topic-based similarities between creators."""
        logger.info("Computing topic similarities...")
        
        similarities = {}
        total_pairs = len(creators) * (len(creators) - 1) // 2
        processed = 0
        
        for i, creator_a in enumerate(creators):
            for j, creator_b in enumerate(creators[i+1:], i+1):
                # Get topics for both creators
                topics_a = self._get_creator_topics(creator_a.creator_id)
                topics_b = self._get_creator_topics(creator_b.creator_id)
                
                # Calculate topic similarity
                similarity = self._calculate_topic_similarity(topics_a, topics_b)
                similarities[(creator_a.creator_id, creator_b.creator_id)] = similarity
                
                processed += 1
                if processed % 1000 == 0:
                    logger.info(f"Processed {processed}/{total_pairs} topic pairs")
        
        logger.info(f"Computed {len(similarities)} topic similarities")
        return similarities
    
    def compute_demographic_similarities(self, creators: List[Creator]) -> Dict[Tuple[int, int], float]:
        """Compute demographic-based similarities between creators."""
        logger.info("Computing demographic similarities...")
        
        similarities = {}
        total_pairs = len(creators) * (len(creators) - 1) // 2
        processed = 0
        
        for i, creator_a in enumerate(creators):
            for j, creator_b in enumerate(creators[i+1:], i+1):
                # Get demographics for both creators
                demo_a = {
                    'age_range': creator_a.age_range,
                    'gender_skew': creator_a.gender_skew,
                    'location': creator_a.location,
                    'interests': creator_a.interests
                }
                demo_b = {
                    'age_range': creator_b.age_range,
                    'gender_skew': creator_b.gender_skew,
                    'location': creator_b.location,
                    'interests': creator_b.interests
                }
                
                # Calculate demographic similarity
                similarity = calculate_demographic_similarity(demo_a, demo_b)
                similarities[(creator_a.creator_id, creator_b.creator_id)] = similarity
                
                processed += 1
                if processed % 1000 == 0:
                    logger.info(f"Processed {processed}/{total_pairs} demographic pairs")
        
        logger.info(f"Computed {len(similarities)} demographic similarities")
        return similarities
    
    def compute_combined_similarities(
        self, 
        topic_similarities: Dict[Tuple[int, int], float],
        demographic_similarities: Dict[Tuple[int, int], float]
    ) -> Dict[Tuple[int, int], float]:
        """Compute combined similarities from topic and demographic scores."""
        logger.info("Computing combined similarities...")
        
        combined_similarities = {}
        
        # Get all creator pairs
        all_pairs = set(topic_similarities.keys()) | set(demographic_similarities.keys())
        
        for pair in all_pairs:
            topic_score = topic_similarities.get(pair, 0.0)
            demo_score = demographic_similarities.get(pair, 0.0)
            
            # Weighted combination (60% topic, 40% demographic)
            combined_score = (topic_score * 0.6) + (demo_score * 0.4)
            combined_similarities[pair] = combined_score
        
        logger.info(f"Computed {len(combined_similarities)} combined similarities")
        return combined_similarities
    
    def store_similarities(
        self, 
        similarities: Dict[Tuple[int, int], float], 
        similarity_type: str
    ) -> int:
        """Store similarities in the database."""
        logger.info(f"Storing {similarity_type} similarities...")
        
        stored_count = 0
        batch_size = 1000
        
        # Clear existing similarities of this type
        self.db.query(CreatorSimilarity).filter(
            CreatorSimilarity.similarity_type == similarity_type
        ).delete()
        
        # Insert new similarities in batches
        similarity_records = []
        
        for (creator_a_id, creator_b_id), score in similarities.items():
            if score > 0.1:  # Only store meaningful similarities
                similarity_records.append({
                    'creator_a_id': creator_a_id,
                    'creator_b_id': creator_b_id,
                    'similarity_type': similarity_type,
                    'similarity_score': score
                })
                
                if len(similarity_records) >= batch_size:
                    self._insert_similarity_batch(similarity_records)
                    stored_count += len(similarity_records)
                    similarity_records = []
        
        # Insert remaining records
        if similarity_records:
            self._insert_similarity_batch(similarity_records)
            stored_count += len(similarity_records)
        
        self.db.commit()
        logger.info(f"Stored {stored_count} {similarity_type} similarities")
        return stored_count
    
    def _insert_similarity_batch(self, records: List[Dict[str, Any]]):
        """Insert a batch of similarity records."""
        try:
            self.db.bulk_insert_mappings(CreatorSimilarity, records)
            self.db.flush()
        except Exception as e:
            logger.error(f"Failed to insert similarity batch: {e}")
            self.db.rollback()
            raise
    
    def _get_creator_topics(self, creator_id: int) -> List[str]:
        """Get topic names for a creator."""
        topics = self.db.query(Topic.name).join(CreatorTopic).filter(
            CreatorTopic.creator_id == creator_id
        ).all()
        return [topic[0] for topic in topics]
    
    def _calculate_topic_similarity(self, topics_a: List[str], topics_b: List[str]) -> float:
        """Calculate topic similarity between two creators."""
        if not topics_a or not topics_b:
            return 0.0
        
        max_similarity = 0.0
        for topic_a in topics_a:
            for topic_b in topics_b:
                similarity = get_topic_similarity(topic_a, topic_b)
                max_similarity = max(max_similarity, similarity)
        
        return max_similarity
    
    def compute_all_similarities(self, creator_ids: List[int] = None) -> Dict[str, int]:
        """Compute all types of similarities for given creators."""
        logger.info("Starting similarity computation...")
        
        # Get creators to process
        if creator_ids:
            creators = self.db.query(Creator).filter(Creator.creator_id.in_(creator_ids)).all()
        else:
            creators = self.db.query(Creator).all()
        
        logger.info(f"Computing similarities for {len(creators)} creators")
        
        if len(creators) < 2:
            logger.warning("Need at least 2 creators to compute similarities")
            return {}
        
        start_time = time.time()
        results = {}
        
        try:
            # Compute topic similarities
            topic_similarities = self.compute_topic_similarities(creators)
            stored_topic = self.store_similarities(topic_similarities, 'topic')
            results['topic'] = stored_topic
            
            # Compute demographic similarities
            demographic_similarities = self.compute_demographic_similarities(creators)
            stored_demo = self.store_similarities(demographic_similarities, 'demographic')
            results['demographic'] = stored_demo
            
            # Compute combined similarities
            combined_similarities = self.compute_combined_similarities(
                topic_similarities, demographic_similarities
            )
            stored_combined = self.store_similarities(combined_similarities, 'combined')
            results['combined'] = stored_combined
            
            end_time = time.time()
            total_time = end_time - start_time
            
            logger.info(f"Similarity computation completed in {total_time:.2f} seconds")
            logger.info(f"Results: {results}")
            
            return results
            
        except Exception as e:
            logger.error(f"Similarity computation failed: {e}")
            self.db.rollback()
            raise


def run_similarity_computation():
    """Run similarity computation for all creators."""
    logger.info("Starting similarity computation...")
    
    # Get database session
    db = next(get_db())
    
    try:
        computer = SimilarityComputer(db)
        results = computer.compute_all_similarities()
        
        logger.info("Similarity computation completed successfully!")
        logger.info(f"Results: {results}")
        
    except Exception as e:
        logger.error(f"Similarity computation failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_similarity_computation()
