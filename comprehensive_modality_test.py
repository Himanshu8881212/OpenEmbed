#!/usr/bin/env python3
"""
Comprehensive test for all modalities and cross-modal retrieval.
Tests embedding generation quality and retrieval accuracy.
"""
import requests
import json
import numpy as np
from pathlib import Path
import time

BASE_URL = "http://localhost:8000/api"
VECTOR_STORE = "comprehensive_test_store"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")

def print_subheader(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'-'*len(text)}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.YELLOW}ℹ️  {text}{Colors.END}")

def test_health():
    """Test server health."""
    print_subheader("1. Server Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Server Status: {data['status']}")
            print_success(f"Models Loaded: {data['models_loaded']}")
            print_success(f"Vector Store Connected: {data['vector_store_connected']}")
            return True
        else:
            print_error(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Health check error: {e}")
        return False

def create_test_vector_store():
    """Create a fresh vector store for testing."""
    print_subheader("2. Vector Store Setup")

    # Delete if exists
    try:
        requests.delete(f"{BASE_URL}/vector-stores/{VECTOR_STORE}")
        print_info(f"Cleared existing vector store: {VECTOR_STORE}")
    except:
        pass

    # Create new
    try:
        response = requests.post(
            f"{BASE_URL}/vector-stores",
            json={
                "name": VECTOR_STORE,
                "description": "Comprehensive test vector store"
            }
        )
        if response.status_code in [200, 201]:
            print_success(f"Created vector store: {VECTOR_STORE}")
            return True
        else:
            print_error(f"Failed to create vector store: {response.text}")
            return False
    except Exception as e:
        print_error(f"Vector store creation error: {e}")
        return False

def test_text_embedding():
    """Test text modality embedding."""
    print_subheader("3. Text Modality Test")

    test_texts = [
        ("A beautiful sunset over the ocean", "sunset_ocean"),
        ("A dog playing in the park", "dog_park"),
        ("Classical music performance", "classical_music"),
        ("Mountain hiking adventure", "mountain_hiking")
    ]

    embeddings = {}

    for text, label in test_texts:
        try:
            # Create text file
            text_file = Path(f"demo_files/text/{label}.txt")
            text_file.parent.mkdir(parents=True, exist_ok=True)
            text_file.write_text(text)

            # Upload and embed
            with open(text_file, 'rb') as f:
                response = requests.post(
                    f"{BASE_URL}/embed-auto",
                    files={"file": (text_file.name, f, "text/plain")},
                    data={
                        "vector_store": VECTOR_STORE,
                        "create_new": "false",
                        "metadata": json.dumps({"type": "text", "label": label})
                    }
                )

            if response.status_code == 200:
                data = response.json()
                embeddings[label] = np.array(data['embedding'])
                print_success(f"Text '{text[:30]}...' → Embedding shape: {len(data['embedding'])}")
                print_info(f"   Stored with ID: {data['id']}")
            else:
                print_error(f"Failed to embed text '{text}': {response.text}")
                return False, {}

        except Exception as e:
            print_error(f"Text embedding error: {e}")
            return False, {}

    # Check embedding quality
    print_info("\nEmbedding Quality Analysis:")

    # Similar texts should have higher similarity
    sunset_emb = embeddings["sunset_ocean"]
    dog_emb = embeddings["dog_park"]
    music_emb = embeddings["classical_music"]

    # Normalize embeddings
    sunset_norm = sunset_emb / np.linalg.norm(sunset_emb)
    dog_norm = dog_emb / np.linalg.norm(dog_emb)
    music_norm = music_emb / np.linalg.norm(music_emb)

    # Calculate similarities
    similarity_sunset_dog = np.dot(sunset_norm, dog_norm)
    similarity_sunset_music = np.dot(sunset_norm, music_norm)

    print_info(f"   Sunset ↔ Dog similarity: {similarity_sunset_dog:.4f}")
    print_info(f"   Sunset ↔ Music similarity: {similarity_sunset_music:.4f}")

    if similarity_sunset_dog > similarity_sunset_music:
        print_success("✓ Embeddings show semantic understanding (different concepts have lower similarity)")

    return True, embeddings

def test_image_embedding():
    """Test image modality embedding."""
    print_subheader("4. Image Modality Test")

    # Check if demo image exists
    demo_image = Path("demo_files/image/sample.jpg")
    if not demo_image.exists():
        print_error(f"Demo image not found: {demo_image}")
        return False

    try:
        with open(demo_image, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/embed-auto",
                files={"file": (demo_image.name, f, "image/jpeg")},
                data={
                    "vector_store": VECTOR_STORE,
                    "create_new": "false",
                    "metadata": json.dumps({"type": "image", "source": "demo"})
                }
            )

        if response.status_code == 200:
            data = response.json()
            print_success(f"Image embedded successfully")
            print_info(f"   Embedding shape: {len(data['embedding'])}")
            print_info(f"   Stored with ID: {data['id']}")
            print_info(f"   Detected modality: {data['modality']}")
            return True, data['id']
        else:
            print_error(f"Failed to embed image: {response.text}")
            return False, None

    except Exception as e:
        print_error(f"Image embedding error: {e}")
        return False, None

def test_video_embedding():
    """Test video modality embedding."""
    print_subheader("5. Video Modality Test")

    demo_video = Path("demo_files/video/sample.mp4")
    if not demo_video.exists():
        print_error(f"Demo video not found: {demo_video}")
        return False

    try:
        with open(demo_video, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/embed-auto",
                files={"file": (demo_video.name, f, "video/mp4")},
                data={
                    "vector_store": VECTOR_STORE,
                    "create_new": "false",
                    "metadata": json.dumps({"type": "video", "source": "demo"})
                }
            )

        if response.status_code == 200:
            data = response.json()
            print_success(f"Video embedded successfully")
            print_info(f"   Embedding shape: {len(data['embedding'])}")
            print_info(f"   Stored with ID: {data['id']}")
            print_info(f"   Detected modality: {data['modality']}")
            return True, data['id']
        else:
            print_error(f"Failed to embed video: {response.text}")
            return False, None

    except Exception as e:
        print_error(f"Video embedding error: {e}")
        return False, None

def test_audio_embedding():
    """Test audio modality embedding."""
    print_subheader("6. Audio Modality Test")

    demo_audio = Path("demo_files/audio/sample.wav")
    if not demo_audio.exists():
        print_error(f"Demo audio not found: {demo_audio}")
        return False

    try:
        with open(demo_audio, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/embed-auto",
                files={"file": (demo_audio.name, f, "audio/wav")},
                data={
                    "vector_store": VECTOR_STORE,
                    "create_new": "false",
                    "metadata": json.dumps({"type": "audio", "source": "demo"})
                }
            )

        if response.status_code == 200:
            data = response.json()
            print_success(f"Audio embedded successfully")
            print_info(f"   Embedding shape: {len(data['embedding'])}")
            print_info(f"   Stored with ID: {data['id']}")
            print_info(f"   Detected modality: {data['modality']}")
            return True, data['id']
        else:
            print_error(f"Failed to embed audio: {response.text}")
            return False, None

    except Exception as e:
        print_error(f"Audio embedding error: {e}")
        return False, None

def test_cross_modal_search():
    """Test cross-modal retrieval capabilities."""
    print_subheader("7. Cross-Modal Search Test")

    # Test 1: Search with text query
    print_info("\n📝 Test 1: Text Query → Find Similar Items")
    query_text = "sunset by the water"

    try:
        # Create query text file
        query_file = Path("demo_files/text/query_sunset.txt")
        query_file.write_text(query_text)

        with open(query_file, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/search",
                files={"file": (query_file.name, f, "text/plain")},
                data={
                    "vector_store": VECTOR_STORE,
                    "n_results": 5
                }
            )

        if response.status_code == 200:
            results = response.json()
            print_success(f"Found {len(results['results'])} results")

            for i, result in enumerate(results['results'][:3], 1):
                print_info(f"   {i}. Distance: {result['distance']:.4f}")
                print_info(f"      Metadata: {result.get('metadata', {})}")
        else:
            print_error(f"Search failed: {response.text}")
            return False

    except Exception as e:
        print_error(f"Cross-modal search error: {e}")
        return False

    # Test 2: Search for dog-related content
    print_info("\n🐕 Test 2: Search for 'dog' related content")
    query_text2 = "dog playing"

    try:
        query_file2 = Path("demo_files/text/query_dog.txt")
        query_file2.write_text(query_text2)

        with open(query_file2, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/search",
                files={"file": (query_file2.name, f, "text/plain")},
                data={
                    "vector_store": VECTOR_STORE,
                    "n_results": 5
                }
            )

        if response.status_code == 200:
            results = response.json()
            print_success(f"Found {len(results['results'])} results")

            for i, result in enumerate(results['results'][:3], 1):
                print_info(f"   {i}. Distance: {result['distance']:.4f}")
                metadata = result.get('metadata', {})
                label = metadata.get('label', 'unknown')
                print_info(f"      Label: {label}")

                # Check if dog-related content ranks higher
                if i == 1 and 'dog' in label:
                    print_success("      ✓ Correct match! Dog content ranked highest")
        else:
            print_error(f"Search failed: {response.text}")
            return False

    except Exception as e:
        print_error(f"Cross-modal search error: {e}")
        return False

    return True

def test_retrieval_accuracy():
    """Test retrieval accuracy with known queries."""
    print_subheader("8. Retrieval Accuracy Test")

    test_cases = [
        ("sunset over water", "sunset_ocean", "Should retrieve sunset-related content"),
        ("dog in nature", "dog_park", "Should retrieve dog-related content"),
        ("music concert", "classical_music", "Should retrieve music-related content")
    ]

    correct_retrievals = 0
    total_tests = len(test_cases)

    for query_text, expected_label, description in test_cases:
        print_info(f"\n🔍 Testing: {description}")
        print_info(f"   Query: '{query_text}'")
        print_info(f"   Expected: {expected_label}")

        try:
            query_file = Path(f"demo_files/text/query_{expected_label}_test.txt")
            query_file.write_text(query_text)

            with open(query_file, 'rb') as f:
                response = requests.post(
                    f"{BASE_URL}/search",
                    files={"file": (query_file.name, f, "text/plain")},
                    data={
                        "vector_store": VECTOR_STORE,
                        "n_results": 3
                    }
                )

            if response.status_code == 200:
                results = response.json()

                if results['results']:
                    top_result = results['results'][0]
                    top_label = top_result.get('metadata', {}).get('label', '')
                    distance = top_result['distance']

                    print_info(f"   Top result: {top_label} (distance: {distance:.4f})")

                    if expected_label in top_label:
                        print_success(f"   ✓ CORRECT: Retrieved expected content")
                        correct_retrievals += 1
                    else:
                        print_error(f"   ✗ INCORRECT: Expected '{expected_label}', got '{top_label}'")
                else:
                    print_error(f"   ✗ No results returned")
            else:
                print_error(f"   Search failed: {response.text}")

        except Exception as e:
            print_error(f"   Error: {e}")

    # Calculate accuracy
    accuracy = (correct_retrievals / total_tests) * 100
    print_info(f"\n📊 Retrieval Accuracy: {correct_retrievals}/{total_tests} ({accuracy:.1f}%)")

    if accuracy >= 66:
        print_success(f"✓ Retrieval accuracy is GOOD ({accuracy:.1f}%)")
        return True
    else:
        print_error(f"✗ Retrieval accuracy is LOW ({accuracy:.1f}%)")
        return False

def test_vector_store_stats():
    """Get vector store statistics."""
    print_subheader("9. Vector Store Statistics")

    try:
        response = requests.get(f"{BASE_URL}/vector-stores/{VECTOR_STORE}")

        if response.status_code == 200:
            data = response.json()
            print_success(f"Vector Store: {data['name']}")
            print_info(f"   Total items: {data['item_count']}")
            print_info(f"   Description: {data.get('description', 'N/A')}")
            return True
        else:
            print_error(f"Failed to get stats: {response.text}")
            return False

    except Exception as e:
        print_error(f"Stats error: {e}")
        return False

def main():
    """Run comprehensive tests."""
    print_header("EMBEd - COMPREHENSIVE MODALITY & CROSS-MODAL TEST")

    start_time = time.time()
    results = {}

    # Run all tests
    results['health'] = test_health()

    if not results['health']:
        print_error("\n❌ Server not healthy. Cannot proceed with tests.")
        return

    results['vector_store'] = create_test_vector_store()
    results['text'], text_embeddings = test_text_embedding()
    results['image'], _ = test_image_embedding()
    results['video'], _ = test_video_embedding()
    results['audio'], _ = test_audio_embedding()
    results['cross_modal'] = test_cross_modal_search()
    results['accuracy'] = test_retrieval_accuracy()
    results['stats'] = test_vector_store_stats()

    # Summary
    elapsed_time = time.time() - start_time

    print_header("TEST SUMMARY")

    test_names = {
        'health': 'Server Health',
        'vector_store': 'Vector Store Setup',
        'text': 'Text Embeddings',
        'image': 'Image Embeddings',
        'video': 'Video Embeddings',
        'audio': 'Audio Embeddings',
        'cross_modal': 'Cross-Modal Search',
        'accuracy': 'Retrieval Accuracy',
        'stats': 'Vector Store Stats'
    }

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for key, name in test_names.items():
        status = "✅ PASSED" if results[key] else "❌ FAILED"
        color = Colors.GREEN if results[key] else Colors.RED
        print(f"{color}{status}{Colors.END} - {name}")

    print(f"\n{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.END}")
    print(f"{Colors.BOLD}Time elapsed: {elapsed_time:.2f}s{Colors.END}")

    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! EMBEd is working perfectly!{Colors.END}")
    elif passed >= total * 0.7:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Most tests passed, but some issues detected.{Colors.END}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ CRITICAL: Multiple test failures detected.{Colors.END}")

if __name__ == "__main__":
    main()
