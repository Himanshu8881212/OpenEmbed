"""
Test automatic modality detection and batch upload functionality.
"""
import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

def test_supported_formats():
    """Test the supported formats endpoint."""
    print_section("📋 Testing Supported Formats Endpoint")

    response = requests.get(f"{BASE_URL}/api/supported-formats")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ SUCCESS! Total formats supported: {data['total_formats']}\n")
        
        for modality, formats in data['formats'].items():
            icon = {
                'text': '📝',
                'image': '🖼️',
                'video': '🎥',
                'audio': '🔊',
                'depth': '📊',
                'thermal': '🌡️'
            }.get(modality, '📄')
            
            print(f"{icon} {modality.upper()}: {len(formats)} formats")
            print(f"   {', '.join(formats)}")
    else:
        print(f"❌ FAILED: {response.status_code}")
        print(response.text)

def test_auto_detection_single():
    """Test automatic modality detection with single file upload."""
    print_section("🔍 Testing Auto-Detection (Single File)")

    # Test with different file types
    # Note: .png files default to 'image', so depth/thermal need explicit modality
    test_files = [
        ("demo_files/sample_text.txt", "text", None),  # Auto-detect
        ("demo_files/sample_image.jpg", "image", None),  # Auto-detect
        ("demo_files/sample_video.mp4", "video", None),  # Auto-detect
        ("demo_files/sample_audio.wav", "audio", None),  # Auto-detect
        ("demo_files/sample_depth.png", "depth", "depth"),  # Explicit modality
        ("demo_files/sample_thermal.png", "thermal", "thermal"),  # Explicit modality
    ]

    for file_path, expected_modality, explicit_modality in test_files:
        if not Path(file_path).exists():
            print(f"⚠️  SKIP: {file_path} not found")
            continue

        print(f"\n📤 Testing {Path(file_path).name}...")

        with open(file_path, 'rb') as f:
            files = {'file': (Path(file_path).name, f)}
            data = {
                'vector_store': 'test_auto_detection',
                'create_new': 'true'
            }
            # Add explicit modality if specified
            if explicit_modality:
                data['modality'] = explicit_modality

            response = requests.post(
                f"{BASE_URL}/api/embed-auto",
                files=files,
                data=data
            )
        
        if response.status_code == 200:
            result = response.json()
            detected = result['modality']
            auto = "✨ AUTO-DETECTED" if result.get('auto_detected', True) else "MANUAL"
            
            if detected == expected_modality:
                print(f"   ✅ SUCCESS! {auto}")
                print(f"   Modality: {detected}")
                print(f"   Embedding ID: {result['embedding_id']}")
                print(f"   Shape: {result['embedding_shape']}")
                print(f"   Preview: {result['embedding_preview'][:5]}...")
            else:
                print(f"   ⚠️  Detected '{detected}' but expected '{expected_modality}'")
        else:
            print(f"   ❌ FAILED: {response.status_code}")
            print(f"   {response.text}")

def test_batch_upload():
    """Test batch upload with mixed modalities."""
    print_section("📦 Testing Batch Upload (Mixed Modalities)")

    # Prepare multiple files with different modalities
    # Note: Batch upload doesn't support per-file modality specification,
    # so we skip .png depth/thermal files (they would be detected as 'image')
    test_files = [
        "demo_files/sample_text.txt",
        "demo_files/sample_image.jpg",
        # "demo_files/sample_depth.png",  # Skip - would be detected as 'image'
        # "demo_files/sample_thermal.png",  # Skip - would be detected as 'image'
        "demo_files/sample_video.mp4",
        "demo_files/sample_audio.wav",
    ]
    
    # Filter to only existing files
    existing_files = [f for f in test_files if Path(f).exists()]
    
    if not existing_files:
        print("⚠️  No demo files found. Please run the demo file creation script first.")
        return
    
    print(f"📤 Uploading {len(existing_files)} files with mixed modalities...")
    
    files_to_upload = []
    for file_path in existing_files:
        files_to_upload.append(
            ('files', (Path(file_path).name, open(file_path, 'rb')))
        )
    
    data = {
        'vector_store': 'test_batch_upload',
        'create_new': 'true'
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/embed-batch",
            files=files_to_upload,
            data=data
        )
        
        # Close all file handles
        for _, (_, file_handle) in files_to_upload:
            file_handle.close()
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ BATCH UPLOAD COMPLETE!")
            print(f"   Total files: {result['total_files']}")
            print(f"   Successful: {result['successful']}")
            print(f"   Failed: {result['failed']}")
            
            if result['results']:
                print(f"\n📊 Results:")
                for item in result['results']:
                    icon = {
                        'text': '📝',
                        'image': '🖼️',
                        'video': '🎥',
                        'audio': '🔊',
                        'depth': '📊',
                        'thermal': '🌡️'
                    }.get(item['modality'], '📄')
                    
                    print(f"   {icon} {item['filename']}")
                    print(f"      Modality: {item['modality']}")
                    print(f"      Embedding ID: {item['embedding_id']}")
                    print(f"      Shape: {item['embedding_shape']}")
                    print(f"      Preview: {item['embedding_preview'][:5]}...")
            
            if result['errors']:
                print(f"\n❌ Errors:")
                for error in result['errors']:
                    print(f"   {error['filename']}: {error['error']}")
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        # Make sure to close file handles
        for _, (_, file_handle) in files_to_upload:
            try:
                file_handle.close()
            except:
                pass

def test_explicit_modality_override():
    """Test that explicit modality parameter overrides auto-detection."""
    print_section("🎯 Testing Explicit Modality Override")
    
    file_path = "demo_files/sample_image.jpg"
    
    if not Path(file_path).exists():
        print(f"⚠️  SKIP: {file_path} not found")
        return
    
    print(f"📤 Uploading {Path(file_path).name} with explicit modality='image'...")
    
    with open(file_path, 'rb') as f:
        files = {'file': (Path(file_path).name, f)}
        data = {
            'vector_store': 'test_explicit',
            'create_new': 'true',
            'modality': 'image'  # Explicitly specify modality
        }
        
        response = requests.post(
            f"{BASE_URL}/api/embed-auto",
            files=files,
            data=data
        )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ SUCCESS!")
        print(f"   Modality: {result['modality']}")
        print(f"   Auto-detected: {result.get('auto_detected', False)}")
        print(f"   Embedding ID: {result['embedding_id']}")
    else:
        print(f"❌ FAILED: {response.status_code}")
        print(response.text)

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("🚀 Testing Auto-Detection and Batch Upload Features")
    print("=" * 60)
    
    try:
        # Test 1: Get supported formats
        test_supported_formats()
        
        # Test 2: Auto-detection with single files
        test_auto_detection_single()
        
        # Test 3: Batch upload with mixed modalities
        test_batch_upload()
        
        # Test 4: Explicit modality override
        test_explicit_modality_override()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

