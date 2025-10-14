"""
Performance testing script for smart matching algorithm.
Tests with large datasets (1000-5000 creators) and measures performance.
"""

import asyncio
import time
import random
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.db import get_db
from app.smart_matching import SmartMatchingService
from app.models import Creator, Advertiser, Topic, Keyword, CreatorTopic, CreatorKeyword
from app.topic_similarities import get_all_topics
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SmartMatchingTester:
    """Test smart matching performance with large datasets."""
    
    def __init__(self, db: Session):
        self.db = db
        self.smart_service = SmartMatchingService(db)
    
    def generate_test_data(self, num_creators: int = 1000) -> Dict[str, Any]:
        """Generate test data for performance testing."""
        logger.info(f"Generating test data for {num_creators} creators")
        
        # Get existing advertisers
        advertisers = self.db.query(Advertiser).limit(5).all()
        if not advertisers:
            logger.error("No advertisers found. Please seed the database first.")
            return {}
        
        # Get all topics
        all_topics = get_all_topics()
        
        # Generate test creators
        test_creators = []
        for i in range(num_creators):
            creator_data = {
                'name': f'Test Creator {i+1}',
                'acct_id': f'test_{i+1:06d}',
                'owner_email': f'test{i+1}@example.com',
                'age_range': random.choice(['18-24', '25-34', '35-44', '45-54', '25-44', '25-54']),
                'gender_skew': random.choice(['mostly men', 'mostly women', 'even split']),
                'location': random.choice(['US', 'UK', 'AU', 'NZ', 'CA']),
                'interests': ', '.join(random.sample(['cooking', 'fitness', 'travel', 'technology', 'fashion', 'gaming', 'parenting', 'business'], random.randint(1, 4))),
                'conservative_click_estimate': random.randint(10, 1000)
            }
            test_creators.append(creator_data)
        
        return {
            'creators': test_creators,
            'advertisers': advertisers,
            'topics': all_topics
        }
    
    def seed_test_data(self, test_data: Dict[str, Any]) -> List[int]:
        """Seed the database with test data."""
        logger.info("Seeding test data...")
        
        creator_ids = []
        
        # Create creators
        for creator_data in test_data['creators']:
            creator = Creator(
                name=creator_data['name'],
                acct_id=creator_data['acct_id'],
                owner_email=creator_data['owner_email'],
                age_range=creator_data['age_range'],
                gender_skew=creator_data['gender_skew'],
                location=creator_data['location'],
                interests=creator_data['interests'],
                conservative_click_estimate=creator_data['conservative_click_estimate'],
                created_at=time.time(),
                updated_at=time.time()
            )
            self.db.add(creator)
            self.db.flush()
            creator_ids.append(creator.creator_id)
        
        # Create topics if they don't exist
        existing_topics = {topic.name: topic for topic in self.db.query(Topic).all()}
        for topic_name in test_data['topics']:
            if topic_name not in existing_topics:
                topic = Topic(name=topic_name, description=f"Test topic: {topic_name}")
                self.db.add(topic)
        
        self.db.commit()
        logger.info(f"Created {len(creator_ids)} test creators")
        return creator_ids
    
    def test_performance(self, num_creators: int = 1000, num_tests: int = 5) -> Dict[str, Any]:
        """Test smart matching performance with different dataset sizes."""
        logger.info(f"Testing performance with {num_creators} creators, {num_tests} iterations")
        
        # Generate test data
        test_data = self.generate_test_data(num_creators)
        if not test_data:
            return {}
        
        # Seed database
        creator_ids = self.seed_test_data(test_data)
        
        # Test parameters
        test_cases = [
            {
                'name': 'Basic Smart Matching',
                'advertiser_id': 1,
                'budget': 10000,
                'cpc': 1.5,
                'target_cpa': 5.0,
                'horizon_days': 30
            },
            {
                'name': 'With Target Demographics',
                'advertiser_id': 1,
                'budget': 10000,
                'cpc': 1.5,
                'target_cpa': 5.0,
                'horizon_days': 30,
                'target_demographics': {
                    'target_age_range': '25-34',
                    'target_gender_skew': 'mostly women',
                    'target_location': 'US',
                    'target_interests': 'cooking, fitness'
                }
            },
            {
                'name': 'High Budget Scenario',
                'advertiser_id': 1,
                'budget': 50000,
                'cpc': 2.0,
                'target_cpa': 10.0,
                'horizon_days': 60
            }
        ]
        
        results = {}
        
        for test_case in test_cases:
            logger.info(f"Testing: {test_case['name']}")
            
            times = []
            creator_counts = []
            
            for i in range(num_tests):
                start_time = time.time()
                
                try:
                    matched_creators = self.smart_service.find_smart_creators(
                        advertiser_id=test_case['advertiser_id'],
                        budget=test_case['budget'],
                        cpc=test_case['cpc'],
                        target_cpa=test_case.get('target_cpa'),
                        horizon_days=test_case['horizon_days'],
                        target_demographics=test_case.get('target_demographics')
                    )
                    
                    end_time = time.time()
                    execution_time = end_time - start_time
                    
                    times.append(execution_time)
                    creator_counts.append(len(matched_creators))
                    
                    logger.info(f"  Iteration {i+1}: {execution_time:.3f}s, {len(matched_creators)} creators")
                    
                except Exception as e:
                    logger.error(f"  Iteration {i+1} failed: {e}")
                    times.append(float('inf'))
                    creator_counts.append(0)
            
            # Calculate statistics
            valid_times = [t for t in times if t != float('inf')]
            if valid_times:
                results[test_case['name']] = {
                    'avg_time': sum(valid_times) / len(valid_times),
                    'min_time': min(valid_times),
                    'max_time': max(valid_times),
                    'avg_creators': sum(creator_counts) / len(creator_counts),
                    'success_rate': len(valid_times) / len(times)
                }
            else:
                results[test_case['name']] = {
                    'avg_time': float('inf'),
                    'min_time': float('inf'),
                    'max_time': float('inf'),
                    'avg_creators': 0,
                    'success_rate': 0
                }
        
        return results
    
    def test_scalability(self) -> Dict[str, Any]:
        """Test scalability with different dataset sizes."""
        logger.info("Testing scalability...")
        
        dataset_sizes = [100, 500, 1000, 2000, 5000]
        scalability_results = {}
        
        for size in dataset_sizes:
            logger.info(f"Testing with {size} creators...")
            
            try:
                results = self.test_performance(size, num_tests=3)
                scalability_results[size] = results
                
                # Log performance metrics
                for test_name, metrics in results.items():
                    logger.info(f"  {test_name}: {metrics['avg_time']:.3f}s avg, {metrics['avg_creators']:.0f} creators")
                    
            except Exception as e:
                logger.error(f"Failed to test with {size} creators: {e}")
                scalability_results[size] = {'error': str(e)}
        
        return scalability_results
    
    def cleanup_test_data(self, creator_ids: List[int]):
        """Clean up test data."""
        logger.info(f"Cleaning up {len(creator_ids)} test creators...")
        
        try:
            # Delete creator relationships first
            self.db.query(CreatorTopic).filter(CreatorTopic.creator_id.in_(creator_ids)).delete()
            self.db.query(CreatorKeyword).filter(CreatorKeyword.creator_id.in_(creator_ids)).delete()
            
            # Delete creators
            self.db.query(Creator).filter(Creator.creator_id.in_(creator_ids)).delete()
            
            self.db.commit()
            logger.info("Test data cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Failed to cleanup test data: {e}")
            self.db.rollback()


def run_performance_tests():
    """Run comprehensive performance tests."""
    logger.info("Starting smart matching performance tests...")
    
    # Get database session
    db = next(get_db())
    
    try:
        tester = SmartMatchingTester(db)
        
        # Test with different dataset sizes
        scalability_results = tester.test_scalability()
        
        # Print results
        logger.info("\n" + "="*50)
        logger.info("PERFORMANCE TEST RESULTS")
        logger.info("="*50)
        
        for size, results in scalability_results.items():
            logger.info(f"\nDataset Size: {size} creators")
            logger.info("-" * 30)
            
            if 'error' in results:
                logger.error(f"Error: {results['error']}")
                continue
            
            for test_name, metrics in results.items():
                logger.info(f"{test_name}:")
                logger.info(f"  Average Time: {metrics['avg_time']:.3f}s")
                logger.info(f"  Min Time: {metrics['min_time']:.3f}s")
                logger.info(f"  Max Time: {metrics['max_time']:.3f}s")
                logger.info(f"  Average Creators: {metrics['avg_creators']:.0f}")
                logger.info(f"  Success Rate: {metrics['success_rate']:.1%}")
        
        # Performance recommendations
        logger.info("\n" + "="*50)
        logger.info("PERFORMANCE RECOMMENDATIONS")
        logger.info("="*50)
        
        # Analyze results and provide recommendations
        max_size = max([size for size in scalability_results.keys() if isinstance(size, int)])
        if max_size in scalability_results and 'error' not in scalability_results[max_size]:
            max_results = scalability_results[max_size]
            
            for test_name, metrics in max_results.items():
                if metrics['avg_time'] > 5.0:
                    logger.warning(f"⚠️  {test_name} is slow ({metrics['avg_time']:.3f}s) - consider optimization")
                elif metrics['avg_time'] > 2.0:
                    logger.info(f"⚡ {test_name} is acceptable ({metrics['avg_time']:.3f}s)")
                else:
                    logger.info(f"✅ {test_name} is fast ({metrics['avg_time']:.3f}s)")
        
        logger.info("\nPerformance testing completed!")
        
    except Exception as e:
        logger.error(f"Performance testing failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_performance_tests()
