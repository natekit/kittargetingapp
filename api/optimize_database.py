"""
Database optimization script for smart matching performance.
Creates indexes, analyzes query performance, and optimizes database structure.
"""

import time
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import get_db
from app.models import Creator, CreatorSimilarity, Topic, Keyword, CreatorTopic, CreatorKeyword
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """Optimize database for smart matching performance."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_indexes(self) -> Dict[str, bool]:
        """Create performance indexes for smart matching."""
        logger.info("Creating performance indexes...")
        
        indexes = {
            'creator_demographics': False,
            'creator_similarities': False,
            'creator_topics': False,
            'creator_keywords': False,
            'similarity_lookup': False
        }
        
        try:
            # Index for creator demographic queries
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_creators_demographics 
                ON creators (age_range, gender_skew, location) 
                WHERE age_range IS NOT NULL
            """))
            indexes['creator_demographics'] = True
            logger.info("✓ Created creator demographics index")
            
            # Index for similarity lookups
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_creator_similarities_lookup 
                ON creator_similarities (creator_a_id, similarity_type, similarity_score DESC)
            """))
            indexes['creator_similarities'] = True
            logger.info("✓ Created creator similarities index")
            
            # Index for topic queries
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_creator_topics_lookup 
                ON creator_topics (creator_id, topic_id)
            """))
            indexes['creator_topics'] = True
            logger.info("✓ Created creator topics index")
            
            # Index for keyword queries
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_creator_keywords_lookup 
                ON creator_keywords (creator_id, keyword_id)
            """))
            indexes['creator_keywords'] = True
            logger.info("✓ Created creator keywords index")
            
            # Composite index for similarity queries
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_similarity_composite 
                ON creator_similarities (creator_a_id, creator_b_id, similarity_type, similarity_score DESC)
            """))
            indexes['similarity_lookup'] = True
            logger.info("✓ Created similarity composite index")
            
            self.db.commit()
            logger.info("All indexes created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            self.db.rollback()
            raise
        
        return indexes
    
    def analyze_query_performance(self) -> Dict[str, Any]:
        """Analyze query performance for smart matching."""
        logger.info("Analyzing query performance...")
        
        test_queries = {
            'creator_demographic_filter': """
                SELECT creator_id, name, age_range, gender_skew, location 
                FROM creators 
                WHERE age_range = '25-34' 
                AND gender_skew = 'mostly women' 
                AND location = 'US'
                LIMIT 100
            """,
            'similarity_lookup': """
                SELECT cs.creator_b_id, cs.similarity_score, c.name
                FROM creator_similarities cs
                JOIN creators c ON cs.creator_b_id = c.creator_id
                WHERE cs.creator_a_id = 1 
                AND cs.similarity_type = 'combined'
                ORDER BY cs.similarity_score DESC
                LIMIT 50
            """,
            'topic_similarity': """
                SELECT ct1.creator_id, ct2.creator_id, COUNT(*) as common_topics
                FROM creator_topics ct1
                JOIN creator_topics ct2 ON ct1.topic_id = ct2.topic_id
                WHERE ct1.creator_id != ct2.creator_id
                GROUP BY ct1.creator_id, ct2.creator_id
                HAVING COUNT(*) > 0
                LIMIT 100
            """,
            'creator_stats': """
                SELECT c.creator_id, c.name, c.conservative_click_estimate,
                       COUNT(cu.creator_id) as total_clicks,
                       COUNT(conv.creator_id) as total_conversions
                FROM creators c
                LEFT JOIN click_uniques cu ON c.creator_id = cu.creator_id
                LEFT JOIN conversions conv ON c.creator_id = conv.creator_id
                GROUP BY c.creator_id, c.name, c.conservative_click_estimate
                LIMIT 100
            """
        }
        
        results = {}
        
        for query_name, query_sql in test_queries.items():
            try:
                start_time = time.time()
                
                # Execute query
                result = self.db.execute(text(query_sql))
                rows = result.fetchall()
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                results[query_name] = {
                    'execution_time': execution_time,
                    'row_count': len(rows),
                    'status': 'success'
                }
                
                logger.info(f"✓ {query_name}: {execution_time:.3f}s, {len(rows)} rows")
                
            except Exception as e:
                results[query_name] = {
                    'execution_time': float('inf'),
                    'row_count': 0,
                    'status': 'error',
                    'error': str(e)
                }
                logger.error(f"✗ {query_name}: {e}")
        
        return results
    
    def optimize_database_settings(self) -> Dict[str, Any]:
        """Optimize database settings for performance."""
        logger.info("Optimizing database settings...")
        
        optimizations = {}
        
        try:
            # Analyze tables for better query planning
            self.db.execute(text("ANALYZE creators"))
            self.db.execute(text("ANALYZE creator_similarities"))
            self.db.execute(text("ANALYZE creator_topics"))
            self.db.execute(text("ANALYZE creator_keywords"))
            
            optimizations['analyze_tables'] = True
            logger.info("✓ Analyzed tables for query optimization")
            
            # Update table statistics
            self.db.execute(text("VACUUM ANALYZE creators"))
            self.db.execute(text("VACUUM ANALYZE creator_similarities"))
            
            optimizations['vacuum_analyze'] = True
            logger.info("✓ Updated table statistics")
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to optimize database settings: {e}")
            self.db.rollback()
            raise
        
        return optimizations
    
    def check_database_health(self) -> Dict[str, Any]:
        """Check database health and performance metrics."""
        logger.info("Checking database health...")
        
        health_metrics = {}
        
        try:
            # Check table sizes
            table_sizes = self.db.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """)).fetchall()
            
            health_metrics['table_sizes'] = [
                {'table': row[1], 'size': row[2]} for row in table_sizes
            ]
            
            # Check index usage
            index_usage = self.db.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes 
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
            """)).fetchall()
            
            health_metrics['index_usage'] = [
                {
                    'table': row[1],
                    'index': row[2],
                    'scans': row[3],
                    'tuples_read': row[4],
                    'tuples_fetched': row[5]
                } for row in index_usage
            ]
            
            # Check slow queries
            slow_queries = self.db.execute(text("""
                SELECT 
                    query,
                    calls,
                    total_time,
                    mean_time,
                    rows
                FROM pg_stat_statements 
                WHERE mean_time > 1000
                ORDER BY mean_time DESC
                LIMIT 10
            """)).fetchall()
            
            health_metrics['slow_queries'] = [
                {
                    'query': row[0][:100] + '...' if len(row[0]) > 100 else row[0],
                    'calls': row[1],
                    'total_time': row[2],
                    'mean_time': row[3],
                    'rows': row[4]
                } for row in slow_queries
            ]
            
            logger.info("✓ Database health check completed")
            
        except Exception as e:
            logger.error(f"Failed to check database health: {e}")
            health_metrics['error'] = str(e)
        
        return health_metrics
    
    def run_full_optimization(self) -> Dict[str, Any]:
        """Run complete database optimization."""
        logger.info("Starting full database optimization...")
        
        start_time = time.time()
        results = {}
        
        try:
            # Create indexes
            results['indexes'] = self.create_indexes()
            
            # Optimize database settings
            results['settings'] = self.optimize_database_settings()
            
            # Analyze query performance
            results['query_performance'] = self.analyze_query_performance()
            
            # Check database health
            results['health'] = self.check_database_health()
            
            end_time = time.time()
            results['total_time'] = end_time - start_time
            
            logger.info(f"Database optimization completed in {results['total_time']:.2f} seconds")
            
            # Print summary
            logger.info("\n" + "="*50)
            logger.info("OPTIMIZATION SUMMARY")
            logger.info("="*50)
            
            # Index summary
            indexes_created = sum(1 for success in results['indexes'].values() if success)
            logger.info(f"Indexes created: {indexes_created}/{len(results['indexes'])}")
            
            # Query performance summary
            successful_queries = sum(1 for q in results['query_performance'].values() if q['status'] == 'success')
            logger.info(f"Query performance: {successful_queries}/{len(results['query_performance'])} queries successful")
            
            # Health summary
            if 'table_sizes' in results['health']:
                logger.info(f"Tables analyzed: {len(results['health']['table_sizes'])}")
            
            logger.info("Database optimization completed successfully!")
            
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            results['error'] = str(e)
            raise
        
        return results


def run_database_optimization():
    """Run complete database optimization."""
    logger.info("Starting database optimization...")
    
    # Get database session
    db = next(get_db())
    
    try:
        optimizer = DatabaseOptimizer(db)
        results = optimizer.run_full_optimization()
        
        logger.info("Database optimization completed successfully!")
        return results
        
    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_database_optimization()
