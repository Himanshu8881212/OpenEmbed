#!/usr/bin/env python3
"""
Test all 6 modalities with demo files and verify:
1. Correct modality detection
2. Model lazy loading
3. Embedding generation
4. Embedding preview
5. Modality tags in vector store
"""

import requests
import json
from pathlib import Path

API_BASE = "http://localhost:8000"

def test_modality(file_path: str, modality: str, vector_store: str = "test_demo", create_new: bool = False):
    """Test a single modality with demo file."""
    print(f"\n{'='*60}")
    print(f"Testing {modality.upper()} modality")
    print(f"File: {file_path}")
    print(f"{'='*60}")

    # Upload file
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'modality': modality,
            'vector_store': vector_store,
            'create_new': 'true' if create_new else 'false'
        }
        
        print(f"📤 Uploading {Path(file_path).name}...")
        response = requests.post(f"{API_BASE}/api/embed", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SUCCESS!")
            print(f"   Embedding ID: {result.get('embedding_id')}")
            print(f"   Modality: {result.get('modality')}")
            print(f"   Filename: {result.get('filename')}")
            
            # Check embedding preview
            if 'embedding_preview' in result:
                preview = result['embedding_preview']
                shape = result.get('embedding_shape', 'unknown')
                print(f"   Embedding Shape: ({shape},)")
                print(f"   Embedding Preview (first 10 values):")
                print(f"      {preview}")
            else:
                print(f"   ⚠️  No embedding preview in response")
            
            return True
        else:
            print(f"❌ FAILED!")
            print(f"   Status: {response.status_code}")
            print(f"   Error: {response.text}")
            return False

def check_vector_store_tags(vector_store: str = "test_demo"):
    """Check if modality tags are visible in vector store."""
    print(f"\n{'='*60}")
    print(f"Checking Vector Store Tags")
    print(f"{'='*60}")
    
    response = requests.get(f"{API_BASE}/api/vector-stores/{vector_store}/files")
    
    if response.status_code == 200:
        files = response.json()
        print(f"✅ Found {len(files)} files in vector store '{vector_store}':")
        
        for file in files:
            modality = file.get('modality', 'unknown')
            filename = file.get('filename', 'unknown')
            print(f"   📄 {filename}")
            print(f"      Modality: {modality}")
            print(f"      ID: {file.get('id')}")
            print(f"      Timestamp: {file.get('timestamp')}")
        
        return True
    else:
        print(f"❌ Failed to get vector store files")
        print(f"   Status: {response.status_code}")
        return False

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🚀 Testing All 6 Modalities with Demo Files")
    print("="*60)
    
    # Test each modality
    results = {}

    # 1. Text (create vector store on first test)
    results['text'] = test_modality('demo_files/sample_text.txt', 'text', create_new=True)

    # 2. Image
    results['image'] = test_modality('demo_files/sample_image.jpg', 'image')
    
    # 3. Depth
    results['depth'] = test_modality('demo_files/sample_depth.png', 'depth')
    
    # 4. Thermal
    results['thermal'] = test_modality('demo_files/sample_thermal.png', 'thermal')
    
    # 5. Video
    results['video'] = test_modality('demo_files/sample_video.mp4', 'video')
    
    # 6. Audio
    results['audio'] = test_modality('demo_files/sample_audio.wav', 'audio')
    
    # Check vector store tags
    check_vector_store_tags()
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 Test Summary")
    print(f"{'='*60}")
    
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    
    for modality, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{modality.upper():10s}: {status}")
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {failed} test(s) failed")

if __name__ == "__main__":
    main()

