#!/usr/bin/env python3
"""
Test runner script for the Kit Targeting App API.
"""
import subprocess
import sys
import os

def run_tests():
    """Run all tests with pytest."""
    # Change to the API directory
    api_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(api_dir)
    
    # Run pytest
    cmd = ["python3", "-m", "pytest", "tests/", "-v", "--tb=short"]
    
    print("Running API tests...")
    print("=" * 50)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 50)
        print("❌ Some tests failed!")
        return e.returncode

if __name__ == "__main__":
    sys.exit(run_tests())
