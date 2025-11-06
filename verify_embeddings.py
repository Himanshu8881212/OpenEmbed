#!/usr/bin/env python3
"""
Comprehensive verification script to ensure embeddings are correctly generated and stored.
This script validates the entire pipeline from file upload to vector storage.
"""

import requests
import numpy as np
from pathlib import Path
import json

BASE_URL = "http://localhost:8000"
TEST_COLLECTION = "verification_test"

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)

def verify_embedding_storage():
    """Verify that embeddings are actually being stored in ChromaDB."""
    print_section("🔍 VERIFICATION: Embedding Storage Pipeline")
    
    # Step 1: Create a new collection
    print("\n📋 Step 1: Creating fresh test collection...")
    collection_data = {
        "name": TEST_COLLECTION,
        "description": "Verification test collection"
    }
    response = requests.post(f"{BASE_URL}/api/vector-stores", json=collection_data)
    if response.status_code == 200:
        print(f"   ✅ Collection '{TEST_COLLECTION}' created successfully")
    else:
        print(f"   ⚠️  Collection might already exist, continuing...")
    
    # Step 2: Upload a test file and get embedding
    print("\n📤 Step 2: Uploading test file and generating embedding...")
    test_file = "demo_files/sample_text.txt"
    
    if not Path(test_file).exists():
        print(f"   ❌ Test file not found: {test_file}")
        return False
    
    with open(test_file, 'rb') as f:
        files = {'file': (Path(test_file).name, f)}
        data = {
            'vector_store': TEST_COLLECTION,
            'modality': 'text'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/embed",
            files=files,
            data=data
        )
    
    if response.status_code != 200:
        print(f"   ❌ Upload failed: {response.status_code}")
        print(f"   {response.text}")
        return False
    
    result = response.json()
    embedding_id = result['embedding_id']
    embedding_preview = result['embedding_preview']
    embedding_shape = result['embedding_shape']
    
    print(f"   ✅ File uploaded successfully")
    print(f"   📊 Embedding ID: {embedding_id}")
    print(f"   📊 Embedding Shape: {embedding_shape}")
    print(f"   📊 Embedding Preview (first 5): {embedding_preview[:5]}")
    
    # Step 3: Verify embedding is stored in ChromaDB
    print("\n🔎 Step 3: Verifying embedding in ChromaDB...")
    response = requests.get(f"{BASE_URL}/api/vector-stores/{TEST_COLLECTION}")
    
    if response.status_code != 200:
        print(f"   ❌ Failed to retrieve collection: {response.status_code}")
        return False
    
    collection_info = response.json()
    count = collection_info.get('count', 0)
    
    print(f"   ✅ Collection retrieved successfully")
    print(f"   📊 Total embeddings in collection: {count}")
    
    if count == 0:
        print(f"   ❌ ERROR: No embeddings found in collection!")
        return False
    
    # Step 4: Verify embedding properties
    print("\n🧪 Step 4: Verifying embedding properties...")
    
    # Check embedding dimension
    if embedding_shape != 768:
        print(f"   ❌ ERROR: Unexpected embedding dimension: {embedding_shape} (expected 768)")
        return False
    else:
        print(f"   ✅ Embedding dimension correct: {embedding_shape}")
    
    # Check embedding values are not all zeros
    if all(v == 0 for v in embedding_preview):
        print(f"   ❌ ERROR: Embedding contains all zeros!")
        return False
    else:
        print(f"   ✅ Embedding contains non-zero values")
    
    # Check embedding values are in reasonable range
    max_val = max(abs(v) for v in embedding_preview)
    if max_val > 10:
        print(f"   ⚠️  WARNING: Embedding values seem unusually large: {max_val}")
    else:
        print(f"   ✅ Embedding values in reasonable range (max: {max_val:.4f})")
    
    print("\n" + "="*60)
    print("✅ VERIFICATION PASSED: Embeddings are correctly generated and stored!")
    print("="*60)
    return True

def verify_all_modalities():
    """Verify all 6 modalities can generate and store embeddings."""
    print_section("🎯 VERIFICATION: All Modalities")
    
    test_files = [
        ("demo_files/sample_text.txt", "text"),
        ("demo_files/sample_image.jpg", "image"),
        ("demo_files/sample_video.mp4", "video"),
        ("demo_files/sample_audio.wav", "audio"),
        ("demo_files/sample_depth.png", "depth"),
        ("demo_files/sample_thermal.png", "thermal"),
    ]
    
    results = []
    
    for file_path, modality in test_files:
        if not Path(file_path).exists():
            print(f"\n⚠️  Skipping {modality}: File not found")
            continue
        
        print(f"\n📤 Testing {modality.upper()} modality...")
        
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
            result = response.json()
            embedding_shape = result['embedding_shape']
            embedding_preview = result['embedding_preview']
            
            # Verify embedding
            is_valid = (
                embedding_shape == 768 and
                not all(v == 0 for v in embedding_preview) and
                max(abs(v) for v in embedding_preview) < 10
            )
            
            if is_valid:
                print(f"   ✅ {modality.upper()}: Valid embedding generated (shape: {embedding_shape})")
                results.append((modality, True, embedding_preview[:3]))
            else:
                print(f"   ❌ {modality.upper()}: Invalid embedding!")
                results.append((modality, False, None))
        else:
            print(f"   ❌ {modality.upper()}: Upload failed ({response.status_code})")
            results.append((modality, False, None))
    
    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY: Modality Verification Results")
    print("="*60)
    
    for modality, is_valid, preview in results:
        status = "✅ PASS" if is_valid else "❌ FAIL"
        print(f"{status} - {modality.upper()}")
        if preview:
            print(f"         Preview: {preview}")
    
    all_passed = all(is_valid for _, is_valid, _ in results)
    
    if all_passed:
        print("\n✅ ALL MODALITIES VERIFIED SUCCESSFULLY!")
    else:
        print("\n❌ SOME MODALITIES FAILED VERIFICATION!")
    
    return all_passed

def verify_vector_store_retrieval():
    """Verify that we can retrieve embeddings from the vector store."""
    print_section("🔍 VERIFICATION: Vector Store Retrieval")
    
    print("\n📊 Retrieving collection information...")
    response = requests.get(f"{BASE_URL}/api/vector-stores/{TEST_COLLECTION}")
    
    if response.status_code != 200:
        print(f"   ❌ Failed to retrieve collection")
        return False
    
    collection_info = response.json()
    print(f"   ✅ Collection: {collection_info['name']}")
    print(f"   📊 Total embeddings: {collection_info['count']}")
    print(f"   📊 Description: {collection_info.get('description', 'N/A')}")
    
    if collection_info['count'] > 0:
        print(f"\n   ✅ Vector store contains {collection_info['count']} embeddings")
        print(f"   ✅ Embeddings are persisted and retrievable")
        return True
    else:
        print(f"\n   ❌ Vector store is empty!")
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 openEmbed - Comprehensive Embedding Verification")
    print("="*60)
    print("\nThis script will verify that:")
    print("1. Embeddings are correctly generated from files")
    print("2. Embeddings are stored in ChromaDB vector store")
    print("3. All 6 modalities work correctly")
    print("4. Embeddings can be retrieved from the vector store")
    
    # Run verifications
    test1 = verify_embedding_storage()
    test2 = verify_all_modalities()
    test3 = verify_vector_store_retrieval()
    
    # Final summary
    print("\n" + "="*60)
    print("🎯 FINAL VERIFICATION RESULTS")
    print("="*60)
    print(f"{'✅' if test1 else '❌'} Embedding Storage Pipeline")
    print(f"{'✅' if test2 else '❌'} All Modalities Working")
    print(f"{'✅' if test3 else '❌'} Vector Store Retrieval")
    
    if test1 and test2 and test3:
        print("\n🎉 ALL VERIFICATIONS PASSED!")
        print("✅ Your embeddings are being correctly generated and stored.")
        print("✅ The system is ready for RAG applications!")
    else:
        print("\n⚠️  SOME VERIFICATIONS FAILED!")
        print("Please review the errors above.")

