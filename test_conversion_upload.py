#!/usr/bin/env python3
"""
Test script to verify conversion upload functionality
"""
import requests
import json
import csv
import io

# Test data
test_csv_data = """Acct ID,Conversions
175313,16
1355267,4
1273792,2
2057,2
974198,2
1750918,1
2222091,1
22429,1
87856,1"""

def test_conversion_upload():
    """Test the conversion upload endpoint"""
    base_url = "http://localhost:8000"
    
    # First, let's check if the API is running
    try:
        response = requests.get(f"{base_url}/healthz")
        print(f"API Health Check: {response.status_code}")
        if response.status_code != 200:
            print("API is not running. Please start it with: make api-dev")
            return
    except requests.exceptions.ConnectionError:
        print("API is not running. Please start it with: make api-dev")
        return
    
    # Get advertisers to find a valid advertiser_id
    try:
        response = requests.get(f"{base_url}/api/advertisers")
        advertisers = response.json()
        print(f"Found {len(advertisers)} advertisers")
        
        if not advertisers:
            print("No advertisers found. Please create an advertiser first.")
            return
            
        advertiser_id = advertisers[0]['advertiser_id']
        print(f"Using advertiser_id: {advertiser_id}")
        
    except Exception as e:
        print(f"Error getting advertisers: {e}")
        return
    
    # Get campaigns for this advertiser
    try:
        response = requests.get(f"{base_url}/api/campaigns?advertiser_id={advertiser_id}")
        campaigns = response.json()
        print(f"Found {len(campaigns)} campaigns for advertiser {advertiser_id}")
        
        if not campaigns:
            print("No campaigns found. Please create a campaign first.")
            return
            
        campaign_id = campaigns[0]['campaign_id']
        print(f"Using campaign_id: {campaign_id}")
        
    except Exception as e:
        print(f"Error getting campaigns: {e}")
        return
    
    # Get insertions for this campaign
    try:
        response = requests.get(f"{base_url}/api/insertions?campaign_id={campaign_id}")
        insertions = response.json()
        print(f"Found {len(insertions)} insertions for campaign {campaign_id}")
        
        if not insertions:
            print("No insertions found. Please create an insertion first.")
            return
            
        insertion_id = insertions[0]['insertion_id']
        print(f"Using insertion_id: {insertion_id}")
        
    except Exception as e:
        print(f"Error getting insertions: {e}")
        return
    
    # Now test the conversion upload
    try:
        # Create a file-like object from the CSV data
        csv_file = io.StringIO(test_csv_data)
        
        # Prepare the form data
        files = {
            'file': ('test_conversions.csv', csv_file.getvalue(), 'text/csv')
        }
        
        params = {
            'advertiser_id': advertiser_id,
            'campaign_id': campaign_id,
            'insertion_id': insertion_id,
            'range_start': '2024-01-01',
            'range_end': '2024-01-31'
        }
        
        print(f"Uploading conversions with params: {params}")
        
        response = requests.post(
            f"{base_url}/api/uploads/conversions",
            files=files,
            params=params
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Inserted {result.get('inserted_rows', 0)} rows, replaced {result.get('replaced_rows', 0)} rows")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Error uploading conversions: {e}")

if __name__ == "__main__":
    test_conversion_upload()
