#!/usr/bin/env python3
"""
Test script for ImageBind integration.
Tests basic functionality of the EMBEd application with ImageBind.
"""
import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test the health endpoint."""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed:")
            print(f"   - Status: {data['status']}")
            print(f"   - Models loaded: {data['models_loaded']}")
            print(f"   - Vector store connected: {data['vector_store_connected']}")
            return True
        else:
            print(f"❌ Health check failed with status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_supported_formats():
    """Test the supported formats endpoint."""
    print("\nTesting supported formats endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/supported-formats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Supported formats retrieved:")
            for modality, formats in data['formats'].items():
                print(f"   - {modality}: {', '.join(formats)}")
            return True
        else:
            print(f"❌ Failed with status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_vector_stores():
    """Test vector store operations."""
    print("\nTesting vector store operations...")

    # List vector stores
    print("  - Listing vector stores...")
    try:
        response = requests.get(f"{BASE_URL}/api/vector-stores", timeout=5)
        if response.status_code == 200:
            print("    ✅ Listed successfully")
        else:
            print(f"    ❌ Failed with status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"    ❌ Failed: {e}")
        return False

    # Create a test vector store
    print("  - Creating test vector store...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/vector-stores",
            json={"name": "test_imagebind", "description": "Test vector store for ImageBind"},
            timeout=10
        )
        if response.status_code in [200, 400]:  # 400 if already exists
            print("    ✅ Created or already exists")
            return True
        else:
            print(f"    ❌ Failed with status code: {response.status_code}")
            print(f"    Response: {response.text}")
            return False
    except Exception as e:
        print(f"    ❌ Failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("EMBEd - ImageBind Integration Test")
    print("=" * 60)

    # Wait for server to be ready
    print("\nWaiting for server to be ready...")
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{BASE_URL}/api/health", timeout=2)
            if response.status_code == 200:
                print("✅ Server is ready!")
                break
        except:
            pass

        if i < max_retries - 1:
            print(f"  Waiting... ({i+1}/{max_retries})")
            time.sleep(2)
        else:
            print("❌ Server not ready after 60 seconds")
            return

    # Run tests
    results = []
    results.append(("Health Check", test_health()))
    results.append(("Supported Formats", test_supported_formats()))
    results.append(("Vector Store Operations", test_vector_stores()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)

if __name__ == "__main__":
    main()
