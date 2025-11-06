#!/usr/bin/env python3
"""
Test script to verify all 6 modalities are working correctly.
Tests: text, image, video, audio, depth, thermal
"""
import sys
import os
from pathlib import Path
import numpy as np
from PIL import Image
import torch

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.languagebind_service import languagebind_service
from app.core.logger import app_logger as logger


def create_test_image(path: Path, size=(224, 224)):
    """Create a test image."""
    img = Image.new('RGB', size, color=(73, 109, 137))
    img.save(path)
    logger.info(f"Created test image: {path}")


def create_test_depth_map(path: Path, size=(224, 224)):
    """Create a test depth map (grayscale image)."""
    img = Image.new('L', size, color=128)
    img.save(path)
    logger.info(f"Created test depth map: {path}")


def create_test_thermal_image(path: Path, size=(224, 224)):
    """Create a test thermal image (grayscale with gradient)."""
    arr = np.linspace(0, 255, size[0] * size[1]).reshape(size).astype(np.uint8)
    img = Image.fromarray(arr, mode='L')
    img.save(path)
    logger.info(f"Created test thermal image: {path}")


def test_text_embedding():
    """Test text embedding generation."""
    print("\n" + "="*60)
    print("Testing TEXT modality...")
    print("="*60)
    
    test_text = "This is a test sentence for embedding generation."
    
    try:
        embedding = languagebind_service.generate_text_embedding(test_text)
        
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


def test_image_embedding(test_dir: Path):
    """Test image embedding generation."""
    print("\n" + "="*60)
    print("Testing IMAGE modality...")
    print("="*60)
    
    image_path = test_dir / "test_image.jpg"
    create_test_image(image_path)
    
    try:
        embedding = languagebind_service.generate_image_embedding(image_path)
        
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


def test_depth_embedding(test_dir: Path):
    """Test depth map embedding generation."""
    print("\n" + "="*60)
    print("Testing DEPTH modality...")
    print("="*60)
    
    depth_path = test_dir / "test_depth.png"
    create_test_depth_map(depth_path)
    
    try:
        embedding = languagebind_service.generate_depth_embedding(depth_path)
        
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


def test_thermal_embedding(test_dir: Path):
    """Test thermal image embedding generation."""
    print("\n" + "="*60)
    print("Testing THERMAL modality...")
    print("="*60)
    
    thermal_path = test_dir / "test_thermal.png"
    create_test_thermal_image(thermal_path)
    
    try:
        embedding = languagebind_service.generate_thermal_embedding(thermal_path)
        
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


def test_video_embedding(test_dir: Path):
    """Test video embedding generation."""
    print("\n" + "="*60)
    print("Testing VIDEO modality...")
    print("="*60)
    print("⚠️  Skipping VIDEO test - requires actual video file")
    print("   To test video: provide a .mp4 file and uncomment the code below")
    return None
    
    # Uncomment to test with actual video file:
    # video_path = test_dir / "test_video.mp4"
    # if not video_path.exists():
    #     print(f"❌ Video file not found: {video_path}")
    #     return False
    # 
    # try:
    #     embedding = languagebind_service.generate_video_embedding(video_path)
    #     if embedding is not None:
    #         print(f"✅ VIDEO embedding generated successfully!")
    #         print(f"   Shape: {embedding.shape}")
    #         return True
    #     else:
    #         print("❌ VIDEO embedding generation failed!")
    #         return False
    # except Exception as e:
    #     print(f"❌ VIDEO embedding error: {e}")
    #     return False


def test_audio_embedding(test_dir: Path):
    """Test audio embedding generation."""
    print("\n" + "="*60)
    print("Testing AUDIO modality...")
    print("="*60)
    print("⚠️  Skipping AUDIO test - requires actual audio file")
    print("   To test audio: provide a .wav or .mp3 file and uncomment the code below")
    return None
    
    # Uncomment to test with actual audio file:
    # audio_path = test_dir / "test_audio.wav"
    # if not audio_path.exists():
    #     print(f"❌ Audio file not found: {audio_path}")
    #     return False
    # 
    # try:
    #     embedding = languagebind_service.generate_audio_embedding(audio_path)
    #     if embedding is not None:
    #         print(f"✅ AUDIO embedding generated successfully!")
    #         print(f"   Shape: {embedding.shape}")
    #         return True
    #     else:
    #         print("❌ AUDIO embedding generation failed!")
    #         return False
    # except Exception as e:
    #     print(f"❌ AUDIO embedding error: {e}")
    #     return False


def main():
    """Run all modality tests."""
    print("\n" + "="*60)
    print("openEmbed - All Modalities Test")
    print("="*60)
    
    # Create test directory
    test_dir = Path("test_files")
    test_dir.mkdir(exist_ok=True)
    
    # Initialize service
    print("\nInitializing LanguageBind service...")
    if not languagebind_service.is_initialized():
        languagebind_service.initialize()
    
    if not languagebind_service.is_initialized():
        print("❌ Failed to initialize LanguageBind service!")
        return
    
    print("✅ LanguageBind service initialized successfully!")
    
    # Run tests
    results = {
        'text': test_text_embedding(),
        'image': test_image_embedding(test_dir),
        'depth': test_depth_embedding(test_dir),
        'thermal': test_thermal_embedding(test_dir),
        'video': test_video_embedding(test_dir),
        'audio': test_audio_embedding(test_dir),
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
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed > 0:
        print("\n❌ Some tests failed! Please check the errors above.")
        sys.exit(1)
    else:
        print("\n✅ All available modalities are working correctly!")
        sys.exit(0)


if __name__ == "__main__":
    main()

