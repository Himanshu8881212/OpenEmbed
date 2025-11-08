#!/usr/bin/env python3
"""
Comprehensive test script for all 7 modalities in OpenEmbed.
Tests: Text, Image, Video, Audio, Depth, Thermal, IMU
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.imagebind_service import ImageBindService
from pathlib import Path
import numpy as np

def test_text_embedding():
    """Test text modality."""
    print("\n" + "="*60)
    print("Testing TEXT Modality")
    print("="*60)
    
    try:
        text = "A beautiful sunset over the ocean"
        embedding = imagebind_service.generate_text_embedding(text)
        
        if embedding is not None:
            print(f"✅ TEXT embedding generated successfully!")
            print(f"   Shape: {embedding.shape}")
            print(f"   Dtype: {embedding.dtype}")
            print(f"   Range: [{embedding.min():.4f}, {embedding.max():.4f}]")
            print(f"   Mean: {embedding.mean():.4f}, Std: {embedding.std():.4f}")
            return True
        else:
            print("❌ TEXT embedding generation failed!")
            return False
    except Exception as e:
        print(f"❌ TEXT embedding error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_image_embedding(test_dir):
    """Test image modality."""
    print("\n" + "="*60)
    print("Testing IMAGE Modality")
    print("="*60)
    
    image_path = test_dir / "sample_image.jpg"
    if not image_path.exists():
        print(f"⚠️  Image file not found: {image_path}")
        return None
    
    try:
        embedding = imagebind_service.generate_image_embedding(image_path)
        
        if embedding is not None:
            print(f"✅ IMAGE embedding generated successfully!")
            print(f"   Shape: {embedding.shape}")
            print(f"   Dtype: {embedding.dtype}")
            print(f"   Range: [{embedding.min():.4f}, {embedding.max():.4f}]")
            print(f"   Mean: {embedding.mean():.4f}, Std: {embedding.std():.4f}")
            return True
        else:
            print("❌ IMAGE embedding generation failed!")
            return False
    except Exception as e:
        print(f"❌ IMAGE embedding error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_video_embedding(test_dir):
    """Test video modality."""
    print("\n" + "="*60)
    print("Testing VIDEO Modality")
    print("="*60)
    
    video_path = test_dir / "sample_video.mp4"
    if not video_path.exists():
        print(f"⚠️  Video file not found: {video_path}")
        return None
    
    try:
        embedding = imagebind_service.generate_video_embedding(video_path)
        
        if embedding is not None:
            print(f"✅ VIDEO embedding generated successfully!")
            print(f"   Shape: {embedding.shape}")
            print(f"   Dtype: {embedding.dtype}")
            print(f"   Range: [{embedding.min():.4f}, {embedding.max():.4f}]")
            print(f"   Mean: {embedding.mean():.4f}, Std: {embedding.std():.4f}")
            return True
        else:
            print("❌ VIDEO embedding generation failed!")
            return False
    except Exception as e:
        print(f"❌ VIDEO embedding error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_audio_embedding(test_dir):
    """Test audio modality."""
    print("\n" + "="*60)
    print("Testing AUDIO Modality")
    print("="*60)
    
    audio_path = test_dir / "sample_audio.wav"
    if not audio_path.exists():
        print(f"⚠️  Audio file not found: {audio_path}")
        return None
    
    try:
        embedding = imagebind_service.generate_audio_embedding(audio_path)
        
        if embedding is not None:
            print(f"✅ AUDIO embedding generated successfully!")
            print(f"   Shape: {embedding.shape}")
            print(f"   Dtype: {embedding.dtype}")
            print(f"   Range: [{embedding.min():.4f}, {embedding.max():.4f}]")
            print(f"   Mean: {embedding.mean():.4f}, Std: {embedding.std():.4f}")
            return True
        else:
            print("❌ AUDIO embedding generation failed!")
            return False
    except Exception as e:
        print(f"❌ AUDIO embedding error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_depth_embedding(test_dir):
    """Test depth modality."""
    print("\n" + "="*60)
    print("Testing DEPTH Modality")
    print("="*60)
    
    depth_path = test_dir / "sample_depth.png"
    if not depth_path.exists():
        print(f"⚠️  Depth file not found: {depth_path}")
        return None
    
    try:
        embedding = imagebind_service.generate_depth_embedding(depth_path)
        
        if embedding is not None:
            print(f"✅ DEPTH embedding generated successfully!")
            print(f"   Shape: {embedding.shape}")
            print(f"   Dtype: {embedding.dtype}")
            print(f"   Range: [{embedding.min():.4f}, {embedding.max():.4f}]")
            print(f"   Mean: {embedding.mean():.4f}, Std: {embedding.std():.4f}")
            return True
        else:
            print("❌ DEPTH embedding generation failed!")
            return False
    except Exception as e:
        print(f"❌ DEPTH embedding error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_thermal_embedding(test_dir):
    """Test thermal modality."""
    print("\n" + "="*60)
    print("Testing THERMAL Modality")
    print("="*60)
    
    thermal_path = test_dir / "sample_thermal.png"
    if not thermal_path.exists():
        print(f"⚠️  Thermal file not found: {thermal_path}")
        return None
    
    try:
        embedding = imagebind_service.generate_thermal_embedding(thermal_path)
        
        if embedding is not None:
            print(f"✅ THERMAL embedding generated successfully!")
            print(f"   Shape: {embedding.shape}")
            print(f"   Dtype: {embedding.dtype}")
            print(f"   Range: [{embedding.min():.4f}, {embedding.max():.4f}]")
            print(f"   Mean: {embedding.mean():.4f}, Std: {embedding.std():.4f}")
            return True
        else:
            print("❌ THERMAL embedding generation failed!")
            return False
    except Exception as e:
        print(f"❌ THERMAL embedding error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_imu_embedding(test_dir):
    """Test IMU modality."""
    print("\n" + "="*60)
    print("Testing IMU Modality")
    print("="*60)
    
    imu_path = test_dir / "sample_imu.csv"
    if not imu_path.exists():
        print(f"⚠️  IMU file not found: {imu_path}")
        return None
    
    try:
        embedding = imagebind_service.generate_imu_embedding(imu_path)
        
        if embedding is not None:
            print(f"✅ IMU embedding generated successfully!")
            print(f"   Shape: {embedding.shape}")
            print(f"   Dtype: {embedding.dtype}")
            print(f"   Range: [{embedding.min():.4f}, {embedding.max():.4f}]")
            print(f"   Mean: {embedding.mean():.4f}, Std: {embedding.std():.4f}")
            return True
        else:
            print("❌ IMU embedding generation failed!")
            return False
    except Exception as e:
        print(f"❌ IMU embedding error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("OpenEmbed - 7 Modality Test Suite")
    print("="*60)
    
    # Initialize service
    print("\nInitializing ImageBind service...")
    imagebind_service = ImageBindService()
    
    if not imagebind_service.initialize():
        print("❌ Failed to initialize ImageBind service!")
        sys.exit(1)
    
    print("✅ ImageBind service initialized successfully!")
    
    # Test directory
    test_dir = Path("demo_files")
    
    # Run tests
    results = {
        'text': test_text_embedding(),
        'image': test_image_embedding(test_dir),
        'video': test_video_embedding(test_dir),
        'audio': test_audio_embedding(test_dir),
        'depth': test_depth_embedding(test_dir),
        'thermal': test_thermal_embedding(test_dir),
        'imu': test_imu_embedding(test_dir),
    }
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for modality, result in results.items():
        status = "✅ PASS" if result is True else "❌ FAIL" if result is False else "⚠️  SKIP"
        print(f"{modality.upper():10s}: {status}")
    
    print(f"\nTotal: {len(results)} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    print("="*60)

