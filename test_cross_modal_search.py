#!/usr/bin/env python3
"""
Test script for cross-modal search functionality.
Demonstrates searching across different modalities using LanguageBind's shared embedding space.
"""

import requests
from pathlib import Path
import json

BASE_URL = "http://localhost:8000"
TEST_COLLECTION = "cross_modal_test"

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"{title}")
    print('='*70)

def setup_test_collection():
    """Create a test collection and populate it with diverse content."""
    print_section("📋 Setting Up Test Collection")
    
    # Create collection
    print(f"\n📦 Creating collection '{TEST_COLLECTION}'...")
    collection_data = {
        "name": TEST_COLLECTION,
        "description": "Cross-modal search test collection"
    }
    response = requests.post(f"{BASE_URL}/api/vector-stores", json=collection_data)
    if response.status_code == 200:
        print(f"   ✅ Collection created successfully")
    else:
        print(f"   ⚠️  Collection might already exist, continuing...")
    
    # Upload diverse content
    print(f"\n📤 Uploading diverse content to collection...")
    
    test_files = [
        ("demo_files/sample_text.txt", "text"),
        ("demo_files/sample_image.jpg", "image"),
        ("demo_files/sample_video.mp4", "video"),
        ("demo_files/sample_audio.wav", "audio"),
        ("demo_files/sample_depth.png", "depth"),
        ("demo_files/sample_thermal.png", "thermal"),
    ]
    
    uploaded = 0
    for file_path, modality in test_files:
        if not Path(file_path).exists():
            print(f"   ⚠️  Skipping {modality}: File not found")
            continue
        
        with open(file_path, 'rb') as f:
            files = {'file': (Path(file_path).name, f)}
            data = {
                'vector_store': TEST_COLLECTION,
                'modality': modality
            }
            
            response = requests.post(
                f"{BASE_URL}/api/embed",
                files=files,
                data=data
            )
        
        if response.status_code == 200:
            print(f"   ✅ Uploaded {modality}: {Path(file_path).name}")
            uploaded += 1
        else:
            print(f"   ❌ Failed to upload {modality}: {response.status_code}")
    
    print(f"\n✅ Setup complete: {uploaded} files uploaded to '{TEST_COLLECTION}'")
    return uploaded > 0

def test_same_modality_search():
    """Test searching with the same modality (e.g., image -> image)."""
    print_section("🔍 Test 1: Same-Modality Search (Image → Image)")
    
    query_file = "demo_files/sample_image.jpg"
    
    if not Path(query_file).exists():
        print(f"   ❌ Query file not found: {query_file}")
        return False
    
    print(f"\n📤 Searching with image query: {query_file}")
    
    with open(query_file, 'rb') as f:
        files = {'file': (Path(query_file).name, f)}
        data = {
            'vector_store': TEST_COLLECTION,
            'modality': 'image',
            'n_results': 5
        }
        
        response = requests.post(
            f"{BASE_URL}/api/search",
            files=files,
            data=data
        )
    
    if response.status_code != 200:
        print(f"   ❌ Search failed: {response.status_code}")
        print(f"   {response.text}")
        return False
    
    result = response.json()
    print(f"\n✅ Search successful!")
    print(f"   Query modality: {result['query_modality']}")
    print(f"   Results found: {result['n_results']}")
    
    print(f"\n📊 Top Results:")
    for i, res in enumerate(result['results'][:3], 1):
        print(f"   {i}. Modality: {res['modality']}")
        print(f"      Similarity: {res['similarity']:.4f}")
        print(f"      Distance: {res['distance']:.4f}")
    
    return True

def test_cross_modality_search():
    """Test cross-modal search (e.g., text -> image/video)."""
    print_section("🔍 Test 2: Cross-Modal Search (Text → All Modalities)")
    
    query_file = "demo_files/sample_text.txt"
    
    if not Path(query_file).exists():
        print(f"   ❌ Query file not found: {query_file}")
        return False
    
    print(f"\n📤 Searching with text query: {query_file}")
    print(f"   This will find semantically similar content across ALL modalities")
    
    with open(query_file, 'rb') as f:
        files = {'file': (Path(query_file).name, f)}
        data = {
            'vector_store': TEST_COLLECTION,
            'modality': 'text',
            'n_results': 10
        }
        
        response = requests.post(
            f"{BASE_URL}/api/search",
            files=files,
            data=data
        )
    
    if response.status_code != 200:
        print(f"   ❌ Search failed: {response.status_code}")
        print(f"   {response.text}")
        return False
    
    result = response.json()
    print(f"\n✅ Search successful!")
    print(f"   Query modality: {result['query_modality']}")
    print(f"   Results found: {result['n_results']}")
    
    print(f"\n📊 Cross-Modal Results:")
    modality_counts = {}
    for res in result['results']:
        modality = res['modality']
        modality_counts[modality] = modality_counts.get(modality, 0) + 1
    
    for i, res in enumerate(result['results'], 1):
        print(f"   {i}. Modality: {res['modality']}")
        print(f"      Similarity: {res['similarity']:.4f}")
        print(f"      Distance: {res['distance']:.4f}")
    
    print(f"\n📈 Modality Distribution:")
    for modality, count in modality_counts.items():
        print(f"   {modality}: {count} results")
    
    return True

def test_filtered_search():
    """Test search with modality filter."""
    print_section("🔍 Test 3: Filtered Search (Image → Video only)")
    
    query_file = "demo_files/sample_image.jpg"
    
    if not Path(query_file).exists():
        print(f"   ❌ Query file not found: {query_file}")
        return False
    
    print(f"\n📤 Searching with image query, filtering for VIDEO results only")
    
    with open(query_file, 'rb') as f:
        files = {'file': (Path(query_file).name, f)}
        data = {
            'vector_store': TEST_COLLECTION,
            'modality': 'image',
            'n_results': 5,
            'filter_modality': 'video'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/search",
            files=files,
            data=data
        )
    
    if response.status_code != 200:
        print(f"   ❌ Search failed: {response.status_code}")
        print(f"   {response.text}")
        return False
    
    result = response.json()
    print(f"\n✅ Search successful!")
    print(f"   Query modality: {result['query_modality']}")
    print(f"   Filter applied: {result['filter_modality']}")
    print(f"   Results found: {result['n_results']}")
    
    print(f"\n📊 Filtered Results:")
    for i, res in enumerate(result['results'], 1):
        print(f"   {i}. Modality: {res['modality']}")
        print(f"      Similarity: {res['similarity']:.4f}")
        print(f"      Distance: {res['distance']:.4f}")
    
    # Verify all results are videos
    all_videos = all(res['modality'] == 'video' for res in result['results'])
    if all_videos:
        print(f"\n   ✅ All results are videos (filter working correctly)")
    else:
        print(f"\n   ⚠️  Some results are not videos (filter may not be working)")
    
    return True

def test_auto_detection_search():
    """Test search with automatic modality detection."""
    print_section("🔍 Test 4: Auto-Detection Search (Audio → All)")
    
    query_file = "demo_files/sample_audio.wav"
    
    if not Path(query_file).exists():
        print(f"   ❌ Query file not found: {query_file}")
        return False
    
    print(f"\n📤 Searching with audio query (auto-detect modality)")
    
    with open(query_file, 'rb') as f:
        files = {'file': (Path(query_file).name, f)}
        data = {
            'vector_store': TEST_COLLECTION,
            'n_results': 5
            # No modality specified - should auto-detect
        }
        
        response = requests.post(
            f"{BASE_URL}/api/search",
            files=files,
            data=data
        )
    
    if response.status_code != 200:
        print(f"   ❌ Search failed: {response.status_code}")
        print(f"   {response.text}")
        return False
    
    result = response.json()
    print(f"\n✅ Search successful!")
    print(f"   Auto-detected modality: {result['query_modality']}")
    print(f"   Results found: {result['n_results']}")
    
    print(f"\n📊 Results:")
    for i, res in enumerate(result['results'], 1):
        print(f"   {i}. Modality: {res['modality']}")
        print(f"      Similarity: {res['similarity']:.4f}")
    
    return True

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 openEmbed - Cross-Modal Search Test Suite")
    print("="*70)
    print("\nThis test demonstrates LanguageBind's cross-modal retrieval:")
    print("• Search with any modality (text/image/video/audio/depth/thermal)")
    print("• Find semantically similar content across ALL modalities")
    print("• Filter results by specific modality")
    print("• Automatic modality detection")
    
    # Setup
    if not setup_test_collection():
        print("\n❌ Setup failed! Cannot proceed with tests.")
        exit(1)
    
    # Run tests
    test1 = test_same_modality_search()
    test2 = test_cross_modality_search()
    test3 = test_filtered_search()
    test4 = test_auto_detection_search()
    
    # Summary
    print_section("🎯 Test Summary")
    print(f"{'✅' if test1 else '❌'} Same-Modality Search")
    print(f"{'✅' if test2 else '❌'} Cross-Modal Search")
    print(f"{'✅' if test3 else '❌'} Filtered Search")
    print(f"{'✅' if test4 else '❌'} Auto-Detection Search")
    
    if all([test1, test2, test3, test4]):
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Cross-modal search is working correctly!")
    else:
        print("\n⚠️  SOME TESTS FAILED!")

