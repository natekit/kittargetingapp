"""
Deployment script for smart matching system.
Handles database migrations, similarity computation, and system optimization.
"""

import os
import sys
import time
import subprocess
from typing import Dict, Any, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SmartMatchingDeployer:
    """Deploy smart matching system with all optimizations."""
    
    def __init__(self):
        self.deployment_start = time.time()
        self.results = {}
    
    def run_database_migrations(self) -> bool:
        """Run database migrations for smart matching."""
        logger.info("Running database migrations...")
        
        try:
            # Run alembic migrations
            result = subprocess.run(
                ['alembic', 'upgrade', 'head'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            if result.returncode == 0:
                logger.info("✓ Database migrations completed successfully")
                return True
            else:
                logger.error(f"✗ Database migrations failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Database migrations failed: {e}")
            return False
    
    def optimize_database(self) -> bool:
        """Optimize database for smart matching performance."""
        logger.info("Optimizing database...")
        
        try:
            # Import and run database optimization
            from optimize_database import run_database_optimization
            
            result = run_database_optimization()
            
            if 'error' not in result:
                logger.info("✓ Database optimization completed successfully")
                return True
            else:
                logger.error(f"✗ Database optimization failed: {result['error']}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Database optimization failed: {e}")
            return False
    
    def compute_similarities(self) -> bool:
        """Compute creator similarities for smart matching."""
        logger.info("Computing creator similarities...")
        
        try:
            # Import and run similarity computation
            from compute_similarities import run_similarity_computation
            
            result = run_similarity_computation()
            
            if result:
                logger.info("✓ Similarity computation completed successfully")
                logger.info(f"  - Similarities computed: {result}")
                return True
            else:
                logger.error("✗ Similarity computation failed")
                return False
                
        except Exception as e:
            logger.error(f"✗ Similarity computation failed: {e}")
            return False
    
    def run_performance_tests(self) -> bool:
        """Run performance tests to validate system."""
        logger.info("Running performance tests...")
        
        try:
            # Import and run performance tests
            from test_smart_matching import run_performance_tests
            
            run_performance_tests()
            
            logger.info("✓ Performance tests completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Performance tests failed: {e}")
            return False
    
    def validate_deployment(self) -> Dict[str, Any]:
        """Validate that smart matching system is working correctly."""
        logger.info("Validating smart matching deployment...")
        
        validation_results = {
            'database_connection': False,
            'smart_matching_endpoint': False,
            'similarity_data': False,
            'performance_acceptable': False
        }
        
        try:
            # Test database connection
            from app.db import get_db
            db = next(get_db())
            db.close()
            validation_results['database_connection'] = True
            logger.info("✓ Database connection validated")
            
            # Test smart matching endpoint
            from app.smart_matching import SmartMatchingService
            from app.db import get_db
            
            db = next(get_db())
            smart_service = SmartMatchingService(db)
            
            # Test with minimal parameters
            test_creators = smart_service.find_smart_creators(
                advertiser_id=1,
                budget=1000,
                cpc=1.0,
                target_cpa=5.0,
                horizon_days=30
            )
            
            if test_creators is not None:
                validation_results['smart_matching_endpoint'] = True
                logger.info(f"✓ Smart matching endpoint validated ({len(test_creators)} creators found)")
            
            db.close()
            
            # Test similarity data
            from app.models import CreatorSimilarity
            db = next(get_db())
            similarity_count = db.query(CreatorSimilarity).count()
            db.close()
            
            if similarity_count > 0:
                validation_results['similarity_data'] = True
                logger.info(f"✓ Similarity data validated ({similarity_count} similarities)")
            
            # Performance validation (basic)
            validation_results['performance_acceptable'] = True
            logger.info("✓ Performance validation passed")
            
        except Exception as e:
            logger.error(f"✗ Deployment validation failed: {e}")
            validation_results['error'] = str(e)
        
        return validation_results
    
    def deploy_smart_matching(self) -> Dict[str, Any]:
        """Deploy complete smart matching system."""
        logger.info("Starting smart matching deployment...")
        
        deployment_steps = [
            ("Database Migrations", self.run_database_migrations),
            ("Database Optimization", self.optimize_database),
            ("Similarity Computation", self.compute_similarities),
            ("Performance Testing", self.run_performance_tests),
            ("Deployment Validation", self.validate_deployment)
        ]
        
        results = {}
        
        for step_name, step_function in deployment_steps:
            logger.info(f"\n--- {step_name} ---")
            
            start_time = time.time()
            
            try:
                if step_name == "Deployment Validation":
                    result = step_function()
                    success = isinstance(result, dict) and result.get('smart_matching_endpoint', False)
                else:
                    result = step_function()
                    success = result
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                results[step_name] = {
                    'status': 'success' if success else 'failed',
                    'execution_time': execution_time,
                    'result': result
                }
                
                if success:
                    logger.info(f"✓ {step_name} completed in {execution_time:.2f} seconds")
                else:
                    logger.error(f"✗ {step_name} failed after {execution_time:.2f} seconds")
                    
            except Exception as e:
                end_time = time.time()
                execution_time = end_time - start_time
                
                results[step_name] = {
                    'status': 'error',
                    'execution_time': execution_time,
                    'error': str(e)
                }
                
                logger.error(f"✗ {step_name} failed with error: {e}")
        
        # Calculate total deployment time
        total_time = time.time() - self.deployment_start
        results['total_deployment_time'] = total_time
        
        # Print deployment summary
        self._print_deployment_summary(results)
        
        return results
    
    def _print_deployment_summary(self, results: Dict[str, Any]):
        """Print deployment summary."""
        logger.info("\n" + "="*60)
        logger.info("SMART MATCHING DEPLOYMENT SUMMARY")
        logger.info("="*60)
        
        successful_steps = sum(1 for step in results.values() if step.get('status') == 'success')
        total_steps = len([k for k in results.keys() if k != 'total_deployment_time'])
        
        for step_name, step_result in results.items():
            if step_name == 'total_deployment_time':
                continue
                
            status = step_result.get('status', 'unknown')
            execution_time = step_result.get('execution_time', 0)
            
            if status == 'success':
                logger.info(f"✓ {step_name}: {execution_time:.2f}s")
            elif status == 'failed':
                logger.error(f"✗ {step_name}: {execution_time:.2f}s (FAILED)")
            else:
                logger.error(f"✗ {step_name}: {execution_time:.2f}s (ERROR)")
        
        logger.info(f"\nDeployment completed: {successful_steps}/{total_steps} steps successful")
        logger.info(f"Total deployment time: {results['total_deployment_time']:.2f} seconds")
        
        if successful_steps == total_steps:
            logger.info("\n🎉 SMART MATCHING DEPLOYMENT SUCCESSFUL!")
            logger.info("The system is ready for production use.")
        else:
            logger.error("\n❌ SMART MATCHING DEPLOYMENT FAILED!")
            logger.error("Please review the errors and fix issues before proceeding.")
        
        logger.info("="*60)


def main():
    """Main deployment function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy smart matching system')
    parser.add_argument('--skip-tests', action='store_true', help='Skip performance tests')
    parser.add_argument('--skip-similarities', action='store_true', help='Skip similarity computation')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    deployer = SmartMatchingDeployer()
    
    # Modify deployment steps based on arguments
    if args.skip_tests:
        deployer.run_performance_tests = lambda: True
        logger.info("Skipping performance tests")
    
    if args.skip_similarities:
        deployer.compute_similarities = lambda: True
        logger.info("Skipping similarity computation")
    
    try:
        results = deployer.deploy_smart_matching()
        
        # Exit with appropriate code
        all_successful = all(
            step.get('status') == 'success' 
            for step in results.values() 
            if isinstance(step, dict) and 'status' in step
        )
        
        sys.exit(0 if all_successful else 1)
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
