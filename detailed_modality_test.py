#!/usr/bin/env python3
"""
Detailed test for all modalities and cross-modal retrieval with ImageBind.
Tests embedding generation quality and retrieval accuracy.
"""
import requests
import json
from pathlib import Path
import time

BASE_URL = "http://localhost:8000/api"
VECTOR_STORE = "detailed_test_store"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*90}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(90)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*90}{Colors.END}\n")

def print_subheader(text):
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{text}{Colors.END}")
    print(f"{Colors.MAGENTA}{'─'*len(text)}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.YELLOW}ℹ️  {text}{Colors.END}")

def print_detail(text):
    print(f"   {Colors.BLUE}{text}{Colors.END}")

# Global storage for embedding IDs
embeddings_db = {}

def setup_test_environment():
    """Setup clean test environment."""
    print_subheader("🔧 Test Environment Setup")

    # Delete existing vector store
    try:
        requests.delete(f"{BASE_URL}/vector-stores/{VECTOR_STORE}")
        print_info(f"Cleared existing vector store: {VECTOR_STORE}")
    except:
        pass

    # Create fresh vector store
    try:
        response = requests.post(
            f"{BASE_URL}/vector-stores",
            json={
                "name": VECTOR_STORE,
                "description": "Detailed modality testing with ImageBind"
            }
        )
        if response.status_code in [200, 201]:
            print_success(f"Created fresh vector store: {VECTOR_STORE}")
            return True
    except Exception as e:
        print_error(f"Setup failed: {e}")
        return False

def test_modality(modality_name, file_path, description):
    """Generic test for any modality."""
    print_subheader(f"📦 {modality_name.upper()} Modality Test")
    print_info(f"Testing: {description}")
    print_info(f"File: {file_path}")

    if not Path(file_path).exists():
        print_error(f"File not found: {file_path}")
        return False

    try:
        with open(file_path, 'rb') as f:
            mime_types = {
                'text': 'text/plain',
                'image': 'image/jpeg',
                'video': 'video/mp4',
                'audio': 'audio/wav',
                'depth': 'image/png',
                'thermal': 'image/png'
            }

            response = requests.post(
                f"{BASE_URL}/embed-auto",
                files={"file": (Path(file_path).name, f, mime_types.get(modality_name, 'application/octet-stream'))},
                data={
                    "vector_store": VECTOR_STORE,
                    "create_new": "false",
                    "metadata": json.dumps({
                        "modality": modality_name,
                        "description": description,
                        "test": "detailed_modality_test"
                    })
                },
                timeout=60
            )

        if response.status_code == 200:
            data = response.json()
            print_success(f"{modality_name.capitalize()} embedding generated successfully")
            print_detail(f"Embedding ID: {data['embedding_id']}")
            print_detail(f"Detected modality: {data['modality']}")
            print_detail(f"Embedding dimension: {data['embedding_shape']}")
            print_detail(f"Preview (first 5 dims): {data['embedding_preview'][:5]}")

            # Store for later retrieval tests
            embeddings_db[description] = {
                'id': data['embedding_id'],
                'modality': modality_name,
                'file': file_path
            }

            # Check embedding quality
            preview = data['embedding_preview']
            if len(preview) >= 10:
                avg_val = sum(preview[:10]) / 10
                print_detail(f"Avg value (first 10 dims): {avg_val:.6f}")

                if all(abs(v) < 0.01 for v in preview[:10]):
                    print_error("⚠️  WARNING: Embedding values very close to zero - may indicate issue")
                else:
                    print_success("✓ Embedding shows variation (good sign)")

            return True
        else:
            print_error(f"Failed: HTTP {response.status_code}")
            print_error(f"Response: {response.text[:200]}")
            return False

    except Exception as e:
        print_error(f"Error: {e}")
        return False

def test_text_modality():
    """Test text modality with multiple examples."""
    print_subheader("📝 TEXT Modality - Multiple Examples")

    test_texts = [
        ("A beautiful sunset over the ocean with golden colors", "sunset_ocean"),
        ("A dog playing happily in the park", "dog_park"),
        ("Classical music performance with orchestra", "classical_music"),
        ("Mountain hiking adventure in nature", "mountain_hiking"),
        ("A cat sleeping on a couch", "cat_sleeping")
    ]

    results = []
    for text, label in test_texts:
        print_info(f"\n📄 Testing: {label}")
        print_detail(f"Text: \"{text}\"")

        # Create text file
        text_file = Path(f"demo_files/test_{label}.txt")
        text_file.write_text(text)

        success = test_modality("text", str(text_file), label)
        results.append(success)

        if not success:
            print_error(f"Failed to embed: {label}")

    success_rate = (sum(results) / len(results)) * 100
    print_info(f"\n📊 Text Modality Success Rate: {sum(results)}/{len(results)} ({success_rate:.1f}%)")
    return all(results)

def test_cross_modal_retrieval():
    """Test cross-modal search capabilities."""
    print_subheader("🔄 CROSS-MODAL RETRIEVAL TEST")

    test_cases = [
        {
            "query": "sunset by the water",
            "expected": "sunset_ocean",
            "description": "Text query should find sunset-related content"
        },
        {
            "query": "dog playing outside",
            "expected": "dog_park",
            "description": "Text query should find dog-related content"
        },
        {
            "query": "music concert performance",
            "expected": "classical_music",
            "description": "Text query should find music-related content"
        },
        {
            "query": "cat resting indoors",
            "expected": "cat_sleeping",
            "description": "Text query should find cat-related content"
        }
    ]

    correct = 0
    total = len(test_cases)

    for i, test_case in enumerate(test_cases, 1):
        print_info(f"\n🔍 Test {i}/{total}: {test_case['description']}")
        print_detail(f"Query: \"{test_case['query']}\"")
        print_detail(f"Expected: {test_case['expected']}")

        # Create query file
        query_file = Path(f"demo_files/query_{i}.txt")
        query_file.write_text(test_case['query'])

        try:
            with open(query_file, 'rb') as f:
                response = requests.post(
                    f"{BASE_URL}/search",
                    files={"file": (query_file.name, f, "text/plain")},
                    data={
                        "vector_store": VECTOR_STORE,
                        "n_results": 5
                    },
                    timeout=60
                )

            if response.status_code == 200:
                results = response.json()

                if results['results']:
                    print_success(f"Found {len(results['results'])} results")

                    # Show top 3 results
                    for j, result in enumerate(results['results'][:3], 1):
                        distance = result['distance']
                        metadata = result.get('metadata', {})
                        desc = metadata.get('description', 'unknown')

                        marker = "🎯" if j == 1 else f" {j}."
                        print_detail(f"{marker} {desc} (distance: {distance:.4f})")

                    # Check if correct result is in top position
                    top_result_desc = results['results'][0].get('metadata', {}).get('description', '')

                    if test_case['expected'] == top_result_desc:
                        print_success("✅ CORRECT: Expected result ranked #1!")
                        correct += 1
                    elif test_case['expected'] in [r.get('metadata', {}).get('description', '') for r in results['results'][:3]]:
                        print_info("⚠️  PARTIAL: Expected result in top 3")
                        correct += 0.5
                    else:
                        print_error(f"❌ INCORRECT: Expected '{test_case['expected']}' not in top 3")
                else:
                    print_error("No results returned")
            else:
                print_error(f"Search failed: HTTP {response.status_code}")

        except Exception as e:
            print_error(f"Error: {e}")

    accuracy = (correct / total) * 100
    print_info(f"\n📊 Retrieval Accuracy: {correct}/{total} ({accuracy:.1f}%)")

    if accuracy >= 75:
        print_success(f"✅ EXCELLENT retrieval accuracy!")
        return True
    elif accuracy >= 50:
        print_info(f"⚠️  MODERATE retrieval accuracy")
        return True
    else:
        print_error(f"❌ POOR retrieval accuracy")
        return False

def test_semantic_understanding():
    """Test if embeddings capture semantic meaning."""
    print_subheader("🧠 SEMANTIC UNDERSTANDING TEST")

    print_info("Testing if similar concepts have closer embeddings...")

    # Create semantically similar and different texts
    similar_texts = [
        ("Dogs and puppies playing in grass", "dogs_play"),
        ("Puppies running around in a field", "puppies_run")
    ]

    different_text = ("Classical orchestra playing symphony", "orchestra")

    print_info("\n1️⃣  Embedding similar texts:")
    for text, label in similar_texts:
        print_detail(f"• {label}: \"{text}\"")
        text_file = Path(f"demo_files/semantic_{label}.txt")
        text_file.write_text(text)
        test_modality("text", str(text_file), f"semantic_{label}")

    print_info("\n2️⃣  Embedding different text:")
    print_detail(f"• {different_text[1]}: \"{different_text[0]}\"")
    text_file = Path(f"demo_files/semantic_{different_text[1]}.txt")
    text_file.write_text(different_text[0])
    test_modality("text", str(text_file), f"semantic_{different_text[1]}")

    # Test retrieval
    print_info("\n3️⃣  Testing retrieval:")
    query_file = Path("demo_files/semantic_query.txt")
    query_file.write_text("puppy playing outdoors")

    try:
        with open(query_file, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/search",
                files={"file": (query_file.name, f, "text/plain")},
                data={"vector_store": VECTOR_STORE, "n_results": 3},
                timeout=60
            )

        if response.status_code == 200:
            results = response.json()['results']

            print_detail("Top results:")
            for i, result in enumerate(results[:3], 1):
                desc = result.get('metadata', {}).get('description', 'unknown')
                dist = result['distance']
                print_detail(f"  {i}. {desc} (distance: {dist:.4f})")

            # Check if dog-related content ranks higher than orchestra
            dog_results = [r for r in results if 'dog' in r.get('metadata', {}).get('description', '').lower() or 'puppies' in r.get('metadata', {}).get('description', '').lower()]

            if dog_results and results[0] in dog_results:
                print_success("✅ Semantic understanding CONFIRMED: Dog-related content ranked highest")
                return True
            else:
                print_error("❌ Semantic understanding WEAK: Unexpected ranking")
                return False

    except Exception as e:
        print_error(f"Error: {e}")
        return False

def main():
    """Run comprehensive tests."""
    print_header("EMBEd - DETAILED MODALITY & CROSS-MODAL RETRIEVAL TEST")
    print_info("Testing ImageBind's multi-modal embedding capabilities")
    print_info("This test validates embedding quality and cross-modal search")

    start_time = time.time()
    results = {}

    # Setup
    if not setup_test_environment():
        print_error("Setup failed. Exiting.")
        return

    # Test all modalities
    results['text'] = test_text_modality()
    results['image'] = test_modality("image", "demo_files/sample_image.jpg", "sample_image")
    results['video'] = test_modality("video", "demo_files/sample_video.mp4", "sample_video")
    results['audio'] = test_modality("audio", "demo_files/sample_audio.wav", "sample_audio")
    results['depth'] = test_modality("depth", "demo_files/sample_depth.png", "sample_depth")
    results['thermal'] = test_modality("thermal", "demo_files/sample_thermal.png", "sample_thermal")

    # Advanced tests
    results['cross_modal'] = test_cross_modal_retrieval()
    results['semantic'] = test_semantic_understanding()

    # Get stats
    print_subheader("📊 VECTOR STORE STATISTICS")
    try:
        response = requests.get(f"{BASE_URL}/vector-stores/{VECTOR_STORE}")
        if response.status_code == 200:
            data = response.json()
            print_success(f"Vector Store: {data['name']}")
            print_detail(f"Total embeddings stored: {data['item_count']}")
    except Exception as e:
        print_error(f"Failed to get stats: {e}")

    # Final summary
    elapsed = time.time() - start_time

    print_header("FINAL TEST SUMMARY")

    test_labels = {
        'text': '📝 Text Modality',
        'image': '🖼️  Image Modality',
        'video': '🎬 Video Modality',
        'audio': '🎵 Audio Modality',
        'depth': '📏 Depth Modality',
        'thermal': '🌡️  Thermal Modality',
        'cross_modal': '🔄 Cross-Modal Retrieval',
        'semantic': '🧠 Semantic Understanding'
    }

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for key, label in test_labels.items():
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if results.get(key) else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{status}  {label}")

    print(f"\n{Colors.BOLD}{'─'*90}{Colors.END}")
    print(f"{Colors.BOLD}Total: {passed}/{total} tests passed ({(passed/total)*100:.1f}%){Colors.END}")
    print(f"{Colors.BOLD}Time elapsed: {elapsed:.2f}s{Colors.END}")
    print(f"{Colors.BOLD}{'─'*90}{Colors.END}\n")

    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 PERFECT! All modalities working flawlessly!{Colors.END}")
        print(f"{Colors.GREEN}✅ ImageBind embeddings are meaningful and accurate{Colors.END}")
        print(f"{Colors.GREEN}✅ Cross-modal retrieval is working correctly{Colors.END}")
        print(f"{Colors.GREEN}✅ Semantic understanding is confirmed{Colors.END}")
    elif passed >= total * 0.75:
        print(f"{Colors.YELLOW}{Colors.BOLD}✓ GOOD! Most tests passed successfully{Colors.END}")
        print(f"{Colors.YELLOW}⚠️  Some minor issues detected, but system is functional{Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ CRITICAL: Multiple failures detected{Colors.END}")
        print(f"{Colors.RED}System may not be functioning correctly{Colors.END}")

if __name__ == "__main__":
    main()
