#!/usr/bin/env python3
"""
Test file download functionality
"""

import requests
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_file_download():
    """Test that files can be downloaded from vector stores."""
    
    print("\n" + "="*80)
    print("Testing File Download Functionality")
    print("="*80 + "\n")
    
    # Get vector stores
    response = requests.get(f"{BASE_URL}/api/vector-stores")
    stores = response.json()['stores']
    
    if not stores:
        print("❌ No vector stores found")
        return False
    
    print(f"✓ Found {len(stores)} vector stores\n")
    
    # Test each store
    for store in stores:
        print(f"Testing store: {store['name']}")
        print(f"  - Files: {store['count']}")
        print(f"  - Storage: {store['size_bytes'] / 1024:.2f} KB")
        
        # Get files in store
        response = requests.get(f"{BASE_URL}/api/vector-stores/{store['name']}/files")
        files = response.json()
        
        if not files:
            print(f"  ⚠ No files in store\n")
            continue
        
        # Try to download first file
        file = files[0]
        print(f"  Testing download: {file['filename']} ({file['modality']})")
        print(f"    File ID: {file['id']}")
        
        download_url = f"{BASE_URL}/api/uploads/{file['modality']}/{file['id']}"
        print(f"    URL: {download_url}")
        
        try:
            response = requests.get(download_url)
            if response.status_code == 200:
                print(f"    ✓ Download successful ({len(response.content)} bytes)")
            else:
                print(f"    ❌ Download failed: {response.status_code}")
                print(f"    Error: {response.text}")
        except Exception as e:
            print(f"    ❌ Download error: {e}")
        
        print()
    
    return True

if __name__ == "__main__":
    test_file_download()

