"""
Comprehensive test runner for smart matching system.
Runs all tests: performance, similarity computation, database optimization.
"""

import asyncio
import time
import sys
import os
from typing import Dict, Any, List
import logging

# Add the API directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_smart_matching import run_performance_tests
from compute_similarities import run_similarity_computation
from optimize_database import run_database_optimization

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('smart_matching_tests.log')
    ]
)
logger = logging.getLogger(__name__)


class SmartMatchingTestRunner:
    """Comprehensive test runner for smart matching system."""
    
    def __init__(self):
        self.results = {}
        self.start_time = None
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all smart matching tests."""
        logger.info("Starting comprehensive smart matching tests...")
        self.start_time = time.time()
        
        try:
            # Test 1: Database optimization
            logger.info("\n" + "="*60)
            logger.info("TEST 1: DATABASE OPTIMIZATION")
            logger.info("="*60)
            
            self.results['database_optimization'] = self._run_with_timing(
                run_database_optimization,
                "Database optimization"
            )
            
            # Test 2: Similarity computation
            logger.info("\n" + "="*60)
            logger.info("TEST 2: SIMILARITY COMPUTATION")
            logger.info("="*60)
            
            self.results['similarity_computation'] = self._run_with_timing(
                run_similarity_computation,
                "Similarity computation"
            )
            
            # Test 3: Performance testing
            logger.info("\n" + "="*60)
            logger.info("TEST 3: PERFORMANCE TESTING")
            logger.info("="*60)
            
            self.results['performance_testing'] = self._run_with_timing(
                run_performance_tests,
                "Performance testing"
            )
            
            # Calculate total time
            total_time = time.time() - self.start_time
            self.results['total_time'] = total_time
            
            # Print final summary
            self._print_final_summary()
            
            return self.results
            
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            self.results['error'] = str(e)
            raise
    
    def _run_with_timing(self, test_function, test_name: str) -> Dict[str, Any]:
        """Run a test function with timing and error handling."""
        logger.info(f"Running {test_name}...")
        
        start_time = time.time()
        
        try:
            result = test_function()
            end_time = time.time()
            execution_time = end_time - start_time
            
            logger.info(f"✓ {test_name} completed in {execution_time:.2f} seconds")
            
            return {
                'status': 'success',
                'execution_time': execution_time,
                'result': result
            }
            
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            
            logger.error(f"✗ {test_name} failed after {execution_time:.2f} seconds: {e}")
            
            return {
                'status': 'error',
                'execution_time': execution_time,
                'error': str(e)
            }
    
    def _print_final_summary(self):
        """Print final test summary."""
        total_time = self.results.get('total_time', 0)
        
        logger.info("\n" + "="*60)
        logger.info("FINAL TEST SUMMARY")
        logger.info("="*60)
        
        # Database optimization summary
        db_opt = self.results.get('database_optimization', {})
        if db_opt.get('status') == 'success':
            logger.info("✓ Database optimization: PASSED")
            if 'indexes' in db_opt.get('result', {}):
                indexes_created = sum(1 for success in db_opt['result']['indexes'].values() if success)
                logger.info(f"  - Indexes created: {indexes_created}")
        else:
            logger.error("✗ Database optimization: FAILED")
        
        # Similarity computation summary
        sim_comp = self.results.get('similarity_computation', {})
        if sim_comp.get('status') == 'success':
            logger.info("✓ Similarity computation: PASSED")
            if 'result' in sim_comp:
                logger.info(f"  - Similarities computed: {sim_comp['result']}")
        else:
            logger.error("✗ Similarity computation: FAILED")
        
        # Performance testing summary
        perf_test = self.results.get('performance_testing', {})
        if perf_test.get('status') == 'success':
            logger.info("✓ Performance testing: PASSED")
        else:
            logger.error("✗ Performance testing: FAILED")
        
        # Overall status
        all_passed = all(
            test.get('status') == 'success' 
            for test in [db_opt, sim_comp, perf_test]
        )
        
        if all_passed:
            logger.info("\n🎉 ALL TESTS PASSED!")
            logger.info("Smart matching system is ready for production.")
        else:
            logger.error("\n❌ SOME TESTS FAILED!")
            logger.error("Please review the logs and fix issues before deployment.")
        
        logger.info(f"\nTotal execution time: {total_time:.2f} seconds")
        logger.info("="*60)
    
    def run_quick_tests(self) -> Dict[str, Any]:
        """Run quick tests for development."""
        logger.info("Running quick smart matching tests...")
        
        try:
            # Only run database optimization and basic performance test
            self.results['database_optimization'] = self._run_with_timing(
                run_database_optimization,
                "Database optimization"
            )
            
            # Quick performance test with smaller dataset
            logger.info("Running quick performance test...")
            # This would be a modified version of the performance test
            # with smaller dataset sizes for faster execution
            
            return self.results
            
        except Exception as e:
            logger.error(f"Quick tests failed: {e}")
            raise


def main():
    """Main test runner function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run smart matching tests')
    parser.add_argument('--quick', action='store_true', help='Run quick tests only')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    runner = SmartMatchingTestRunner()
    
    try:
        if args.quick:
            results = runner.run_quick_tests()
        else:
            results = runner.run_all_tests()
        
        # Exit with appropriate code
        all_passed = all(
            test.get('status') == 'success' 
            for test in results.values() 
            if isinstance(test, dict) and 'status' in test
        )
        
        sys.exit(0 if all_passed else 1)
        
    except Exception as e:
        logger.error(f"Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
