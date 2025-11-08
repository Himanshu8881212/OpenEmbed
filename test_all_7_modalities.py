#!/usr/bin/env python3
"""
Comprehensive test for all 7 modalities in OpenEmbed.
Tests: text, image, video, audio, depth, thermal, and IMU.
"""
import requests
import json
from pathlib import Path
import time

API_BASE = "http://localhost:8000"
VECTOR_STORE = "test_all_modalities"

def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)

def print_success(text):
    """Print success message."""
    print(f"✅ {text}")

def print_error(text):
    """Print error message."""
    print(f"❌ {text}")

def print_info(text):
    """Print info message."""
    print(f"ℹ️  {text}")

def test_modality(file_path: str, modality: str, create_new: bool = False):
    """Test uploading and embedding a file."""
    print_header(f"Testing {modality.upper()} Modality")
    print_info(f"File: {file_path}")
    
    if not Path(file_path).exists():
        print_error(f"File not found: {file_path}")
        return False
    
    try:
        # Upload and embed file
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'modality': modality,
                'vector_store': VECTOR_STORE,
                'create_new': 'true' if create_new else 'false'
            }
            
            print_info("Uploading file and generating embedding...")
            response = requests.post(f"{API_BASE}/api/embed", files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                print_success(f"Upload successful!")
                print_info(f"Embedding ID: {result.get('embedding_id', 'N/A')}")
                print_info(f"Vector Store: {result.get('vector_store_name', 'N/A')}")

                # Show embedding preview if available
                if 'embedding_preview' in result:
                    preview = result['embedding_preview']
                    if isinstance(preview, dict):
                        print_info(f"Embedding shape: {preview.get('shape', 'N/A')}")
                        print_info(f"First 5 values: {preview.get('first_values', [])[:5]}")
                    elif isinstance(preview, list):
                        print_info(f"Embedding preview (first 5): {preview[:5]}")

                return True
            else:
                print_error(f"Upload failed: {response.status_code}")
                print_error(f"Error: {response.text}")
                return False
                
    except Exception as e:
        print_error(f"Exception occurred: {str(e)}")
        return False

def test_search(query_file: str, modality: str):
    """Test cross-modal search."""
    print_header(f"Testing Search with {modality.upper()}")
    print_info(f"Query file: {query_file}")
    
    if not Path(query_file).exists():
        print_error(f"Query file not found: {query_file}")
        return False
    
    try:
        with open(query_file, 'rb') as f:
            files = {'file': f}
            data = {
                'vector_store': VECTOR_STORE,
                'modality': modality,
                'top_k': '3'
            }

            print_info("Searching...")
            response = requests.post(f"{API_BASE}/api/search", files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                results = result.get('results', [])
                print_success(f"Search successful! Found {len(results)} results")
                
                for i, res in enumerate(results, 1):
                    print_info(f"Result {i}:")
                    print(f"   - Modality: {res.get('modality', 'N/A')}")
                    print(f"   - Similarity: {res.get('similarity', 0):.4f}")
                    print(f"   - File: {Path(res.get('file_path', '')).name}")
                
                return True
            else:
                print_error(f"Search failed: {response.status_code}")
                print_error(f"Error: {response.text}")
                return False
                
    except Exception as e:
        print_error(f"Exception occurred: {str(e)}")
        return False

def check_vector_store():
    """Check vector store contents."""
    print_header("Checking Vector Store")
    
    try:
        response = requests.get(f"{API_BASE}/api/vector-stores")
        if response.status_code == 200:
            stores = response.json().get('stores', [])
            
            # Find our test store
            test_store = None
            for store in stores:
                if store['name'] == VECTOR_STORE:
                    test_store = store
                    break
            
            if test_store:
                print_success(f"Vector store '{VECTOR_STORE}' found")
                print_info(f"Total embeddings: {test_store.get('count', 0)}")
                print_info(f"Modality: {test_store.get('modality', 'N/A')}")
                return True
            else:
                print_error(f"Vector store '{VECTOR_STORE}' not found")
                return False
        else:
            print_error(f"Failed to get vector stores: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Exception occurred: {str(e)}")
        return False

def main():
    """Run comprehensive tests for all 7 modalities."""
    print_header("OpenEmbed - Comprehensive 7-Modality Test Suite")
    print_info("Testing: Text, Image, Video, Audio, Depth, Thermal, IMU")
    
    # Test files
    test_files = [
        ('demo_files/sample_text.txt', 'text', True),  # Create new store
        ('demo_files/sample_image.jpg', 'image', False),
        ('demo_files/sample_video.mp4', 'video', False),
        ('demo_files/sample_audio.wav', 'audio', False),
        ('demo_files/sample_depth.png', 'depth', False),
        ('demo_files/sample_thermal.png', 'thermal', False),
        ('demo_files/sample_imu.csv', 'imu', False),
    ]
    
    # Track results
    upload_results = []
    
    # Test uploads
    print_header("Phase 1: Upload and Embed All Modalities")
    for file_path, modality, create_new in test_files:
        result = test_modality(file_path, modality, create_new)
        upload_results.append((modality, result))
        time.sleep(1)  # Brief pause between uploads
    
    # Check vector store
    time.sleep(2)
    check_vector_store()
    
    # Test search with different modalities
    print_header("Phase 2: Cross-Modal Search Tests")
    
    search_tests = [
        ('demo_files/sample_text.txt', 'text'),
        ('demo_files/sample_image.jpg', 'image'),
        ('demo_files/sample_imu.csv', 'imu'),
    ]
    
    search_results = []
    for query_file, modality in search_tests:
        result = test_search(query_file, modality)
        search_results.append((modality, result))
        time.sleep(1)
    
    # Summary
    print_header("Test Summary")
    
    print("\n📤 Upload Results:")
    for modality, success in upload_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {modality.upper():10s} - {status}")
    
    print("\n🔍 Search Results:")
    for modality, success in search_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {modality.upper():10s} - {status}")
    
    # Overall result
    all_uploads_passed = all(result for _, result in upload_results)
    all_searches_passed = all(result for _, result in search_results)
    
    print("\n" + "=" * 80)
    if all_uploads_passed and all_searches_passed:
        print_success("ALL TESTS PASSED! 🎉")
        print_info("OpenEmbed is working correctly with all 7 modalities!")
    else:
        print_error("SOME TESTS FAILED")
        if not all_uploads_passed:
            print_error("Upload tests failed")
        if not all_searches_passed:
            print_error("Search tests failed")
    print("=" * 80)

if __name__ == "__main__":
    main()

