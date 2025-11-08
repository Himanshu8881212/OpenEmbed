"""
OpenEmbed Production Validation Test Suite
Comprehensive end-to-end testing for production readiness.
"""
import requests
import time
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"
TEST_FILES_DIR = Path("test_files")

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class TestResults:
    """Track test results."""
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.failed_tests = []

    def add_pass(self):
        self.total += 1
        self.passed += 1

    def add_fail(self, test_name: str, reason: str):
        self.total += 1
        self.failed += 1
        self.failed_tests.append((test_name, reason))

    def add_warning(self):
        self.warnings += 1

    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100


results = TestResults()


def print_header(text: str, char: str = "="):
    """Print a formatted header."""
    width = 80
    print(f"\n{char * width}")
    print(f"{text:^{width}}")
    print(f"{char * width}\n")


def print_test(text: str):
    """Print test description."""
    print(f"{Colors.BLUE}▶{Colors.ENDC} {text}")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓{Colors.ENDC} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗{Colors.ENDC} {text}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.CYAN}ℹ{Colors.ENDC}   {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.ENDC}   {text}")


def cleanup_all_stores():
    """Clean up all existing vector stores."""
    try:
        response = requests.get(f"{API_BASE}/vector-stores", timeout=10)
        if response.status_code == 200:
            stores = response.json().get("stores", [])
            for store in stores:
                store_name = store.get("name")
                if store_name:
                    try:
                        requests.delete(f"{API_BASE}/vector-stores/{store_name}", timeout=10)
                        print_info(f"Cleaned up store: {store_name}")
                    except Exception as e:
                        print_warning(f"Failed to delete store {store_name}: {e}")
    except Exception as e:
        print_warning(f"Failed to cleanup stores: {e}")


def test_health_check() -> bool:
    """Test 1: API Health Check."""
    print_header("Test 1: API Health Check")
    print_test("Testing API health check...")
    
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_success("API is healthy")
            print_info(f"- Version: {data.get('version', 'N/A')}")
            
            # Check models loaded
            if data.get("models_loaded"):
                print_info("- Models: Loaded ✓")
            else:
                print_error("- Models: Not loaded")
                results.add_fail("Health Check", "Models not loaded")
                return False
            
            # Check vector store
            if data.get("vector_store_connected"):
                print_info("- Vector Store: Connected ✓")
            else:
                print_error("- Vector Store: Not connected")
                results.add_fail("Health Check", "Vector store not connected")
                return False
            
            results.add_pass()
            return True
        else:
            print_error(f"Health check failed with status {response.status_code}")
            results.add_fail("Health Check", f"Status code: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Health check failed: {e}")
        results.add_fail("Health Check", str(e))
        return False


def test_individual_uploads() -> Dict[str, str]:
    """Test 2: Individual Modality Uploads."""
    print_header("Test 2: Individual Modality Upload & Embedding Generation")
    
    uploaded_files = {}
    test_files = {
        "text": "demo_files/sample_text.txt",
        "image": "test_files/test_image.jpg",
        "video": "demo_files/sample_video.mp4",
        "audio": "test_files/test_audio.wav",
        "depth": "test_files/test_depth.png",
        "thermal": "test_files/test_thermal.png",
        "imu": "demo_files/sample_imu.csv"
    }
    
    for modality, filepath in test_files.items():
        print_test(f"Testing {modality.upper()} upload...")
        file_path = Path(filepath)

        if not file_path.exists():
            print_error(f"Test file not found: {file_path}")
            results.add_fail(f"Upload {modality}", "Test file not found")
            continue

        try:
            filename = file_path.name
            with open(file_path, "rb") as f:
                files = {"file": (filename, f)}
                data = {"modality": modality}
                response = requests.post(f"{API_BASE}/upload", files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                file_id = result.get("file_id")
                uploaded_files[modality] = file_id
                print_success(f"{modality.upper()} upload successful")
                print_info(f"- File: {filename}")
                print_info(f"- Modality: {modality}")
                print_info(f"- File ID: {file_id}")
                print_info(f"- Size: {file_path.stat().st_size} bytes")
                results.add_pass()
            else:
                print_error(f"{modality.upper()} upload failed: {response.status_code}")
                print_error(f"Response: {response.text}")
                results.add_fail(f"Upload {modality}", f"Status: {response.status_code}")
        except Exception as e:
            print_error(f"{modality.upper()} upload failed: {e}")
            results.add_fail(f"Upload {modality}", str(e))
    
    return uploaded_files


def test_multi_modal_upload() -> bool:
    """Test 3: Multi-Modal Upload."""
    print_header("Test 3: Multi-Modal Upload (Simultaneous)")
    print_test("Testing multi-modal upload (text + image + audio)...")
    
    files_to_upload = [
        ("demo_files/test_sunset_ocean.txt", "text"),
        ("test_files/test_image.jpg", "image"),
        ("test_files/test_audio.wav", "audio")
    ]

    uploaded_count = 0
    for filepath, modality in files_to_upload:
        file_path = Path(filepath)
        filename = file_path.name
        if not file_path.exists():
            print_warning(f"File not found: {filename}, skipping")
            continue
        
        try:
            with open(file_path, "rb") as f:
                files = {"file": (filename, f)}
                data = {"modality": modality}
                response = requests.post(f"{API_BASE}/upload", files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                print_info(f"- {filename} ({modality}): uploaded")
                uploaded_count += 1
            else:
                print_warning(f"- {filename} ({modality}): failed")
        except Exception as e:
            print_warning(f"- {filename} ({modality}): error - {e}")
    
    if uploaded_count > 0:
        print_success(f"Multi-modal upload successful: {uploaded_count} files processed")
        results.add_pass()
        return True
    else:
        print_error("Multi-modal upload failed: no files uploaded")
        results.add_fail("Multi-modal upload", "No files uploaded")
        return False


def test_vector_store_creation() -> List[str]:
    """Test 4: Vector Store Creation."""
    print_header("Test 4: Vector Store Creation")
    
    created_stores = []
    stores_to_create = [
        ("test_text_store", "text", "Text embeddings store"),
        ("test_image_store", "image", "Image embeddings store"),
        ("test_video_store", "video", "Video embeddings store"),
        ("test_audio_store", "audio", "Audio embeddings store")
    ]
    
    for store_name, modality, description in stores_to_create:
        print_test(f"Creating vector store '{store_name}' for {modality}...")
        
        data = {
            "name": store_name,
            "description": description,
            "modality": modality
        }
        
        try:
            response = requests.post(f"{API_BASE}/vector-stores", json=data, timeout=10)
            
            if response.status_code == 200:
                print_success(f"Vector store '{store_name}' created successfully")
                created_stores.append(store_name)
                results.add_pass()
            elif response.status_code == 400 and "already exists" in response.text.lower():
                print_warning(f"Vector store '{store_name}' already exists, using existing")
                created_stores.append(store_name)
                results.add_pass()
            else:
                print_error(f"Vector store creation failed: {response.status_code}")
                print_error(f"Response: {response.text}")
                results.add_fail(f"Create store {store_name}", f"Status: {response.status_code}")
        except Exception as e:
            print_error(f"Vector store creation failed: {e}")
            results.add_fail(f"Create store {store_name}", str(e))
    
    return created_stores


def test_add_embeddings(uploaded_files: Dict[str, str], stores: List[str]) -> bool:
    """Test 5: Add Embeddings to Vector Stores."""
    print_header("Test 5: Add Embeddings to Vector Stores")

    if not uploaded_files or not stores:
        print_warning("Skipping: No uploaded files or stores available")
        return False

    # Map modalities to stores
    modality_store_map = {
        "text": "test_text_store",
        "image": "test_image_store",
        "video": "test_video_store",
        "audio": "test_audio_store"
    }

    success_count = 0
    for modality, file_id in uploaded_files.items():
        store_name = modality_store_map.get(modality)
        if not store_name or store_name not in stores:
            continue

        print_test(f"Adding {modality} embedding to {store_name}...")

        # Re-upload with vector store specified
        test_files = {
            "text": "sample_text.txt",
            "image": "sample_image.jpg",
            "video": "sample_video.mp4",
            "audio": "sample_audio.wav"
        }

        filename = test_files.get(modality)
        if not filename:
            continue

        file_path = TEST_FILES_DIR / filename
        if not file_path.exists():
            continue

        try:
            with open(file_path, "rb") as f:
                files = {"file": (filename, f)}
                data = {"modality": modality, "vector_store": store_name}
                response = requests.post(f"{API_BASE}/upload", files=files, data=data, timeout=30)

            if response.status_code == 200:
                print_success(f"Embedding added to {store_name}")
                success_count += 1
                results.add_pass()
            else:
                print_error(f"Failed to add embedding: {response.status_code}")
                results.add_fail(f"Add embedding {modality}", f"Status: {response.status_code}")
        except Exception as e:
            print_error(f"Failed to add embedding: {e}")
            results.add_fail(f"Add embedding {modality}", str(e))

    return success_count > 0


def test_list_stores() -> bool:
    """Test 6: List All Vector Stores."""
    print_header("Test 6: List All Vector Stores")
    print_test("Listing all vector stores...")

    try:
        response = requests.get(f"{API_BASE}/vector-stores", timeout=10)

        if response.status_code == 200:
            data = response.json()
            stores = data.get("stores", [])
            print_success(f"Found {len(stores)} vector stores")

            for store in stores:
                name = store.get("name", "Unknown")
                modality = store.get("modality", "Unknown")
                count = store.get("count", 0)
                size_bytes = store.get("size_bytes", 0)
                size_mb = size_bytes / (1024 * 1024) if size_bytes > 0 else 0
                print_info(f"- {name} ({modality}): {count} files, {size_mb:.2f} MB")

            results.add_pass()
            return True
        else:
            print_error(f"Failed to list stores: {response.status_code}")
            results.add_fail("List stores", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to list stores: {e}")
        results.add_fail("List stores", str(e))
        return False


def test_semantic_search() -> bool:
    """Test 7: Semantic Search & Retrieval."""
    print_header("Test 7: Semantic Search & Retrieval")
    print_test("Testing semantic search across all stores...")

    search_queries = [
        "machine learning and artificial intelligence",
        "sunset over the ocean",
        "music and audio"
    ]

    success_count = 0
    # Get first available store
    stores_response = requests.get(f"{API_BASE}/vector-stores", timeout=10)
    if stores_response.status_code != 200 or not stores_response.json().get("stores"):
        print_warning("No vector stores available for search")
        return False

    first_store = stores_response.json()["stores"][0]["name"]

    for query in search_queries:
        print_test(f"Searching for: '{query}'")

        try:
            search_data = {
                "vector_store_name": first_store,
                "query_modality": "text",
                "query_text": query,
                "n_results": 5
            }
            response = requests.post(f"{API_BASE}/search-by-id", json=search_data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                results_list = result.get("results", [])
                print_success(f"Search successful: {len(results_list)} results")

                for i, res in enumerate(results_list[:3], 1):
                    similarity = res.get("similarity", 0)
                    filename = res.get("metadata", {}).get("filename", "Unknown")
                    print_info(f"  {i}. {filename} (similarity: {similarity:.4f})")

                success_count += 1
                results.add_pass()
            else:
                print_error(f"Search failed: {response.status_code}")
                results.add_fail(f"Search '{query}'", f"Status: {response.status_code}")
        except Exception as e:
            print_error(f"Search failed: {e}")
            results.add_fail(f"Search '{query}'", str(e))

    return success_count > 0


def test_cross_modal_search() -> bool:
    """Test 8: Cross-Modal Search."""
    print_header("Test 8: Cross-Modal Search (Text → All Modalities)")
    print_test("Testing cross-modal search (text query → all modalities)...")

    # Get first available store
    stores_response = requests.get(f"{API_BASE}/vector-stores", timeout=10)
    if stores_response.status_code != 200 or not stores_response.json().get("stores"):
        print_warning("No vector stores available for search")
        return False

    first_store = stores_response.json()["stores"][0]["name"]

    try:
        search_data = {
            "vector_store_name": first_store,
            "query_modality": "text",
            "query_text": "beautiful landscape with water",
            "n_results": 10
        }
        response = requests.post(f"{API_BASE}/search-by-id", json=search_data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            results_list = result.get("results", [])

            # Group by modality
            modality_counts = {}
            for res in results_list:
                modality = res.get("metadata", {}).get("modality", "unknown")
                modality_counts[modality] = modality_counts.get(modality, 0) + 1

            print_success(f"Cross-modal search successful: {len(results_list)} results")
            print_info(f"Results by modality: {modality_counts}")

            results.add_pass()
            return True
        else:
            print_error(f"Cross-modal search failed: {response.status_code}")
            results.add_fail("Cross-modal search", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Cross-modal search failed: {e}")
        results.add_fail("Cross-modal search", str(e))
        return False


def test_file_serving(uploaded_files: Dict[str, str]) -> bool:
    """Test 9: File Serving."""
    print_header("Test 9: File Serving Endpoint")

    if not uploaded_files:
        print_warning("Skipping: No uploaded files available")
        return False

    success_count = 0
    for modality, file_id in list(uploaded_files.items())[:3]:  # Test first 3
        print_test(f"Testing file serving for {modality} file...")

        try:
            response = requests.get(f"{API_BASE}/uploads/{modality}/{file_id}", timeout=10)

            if response.status_code == 200:
                print_success(f"File served successfully ({len(response.content)} bytes)")
                success_count += 1
                results.add_pass()
            else:
                print_error(f"File serving failed: {response.status_code}")
                results.add_fail(f"Serve {modality} file", f"Status: {response.status_code}")
        except Exception as e:
            print_error(f"File serving failed: {e}")
            results.add_fail(f"Serve {modality} file", str(e))

    return success_count > 0


def print_final_results():
    """Print final test results."""
    print_header("Production Validation Test Results")

    print(f"\nSummary:")
    print(f"  Total Tests: {results.total}")
    print(f"  {Colors.GREEN}Passed: {results.passed}{Colors.ENDC}")
    print(f"  {Colors.RED}Failed: {results.failed}{Colors.ENDC}")
    print(f"  {Colors.YELLOW}Warnings: {results.warnings}{Colors.ENDC}")

    success_rate = results.success_rate()
    print(f"\n{Colors.BOLD}Success Rate: {success_rate:.1f}%{Colors.ENDC}")

    if results.failed > 0:
        print(f"\n{Colors.RED}Failed Tests:{Colors.ENDC}")
        for test_name, reason in results.failed_tests:
            print(f"  - {test_name}: {reason}")

    print()
    if success_rate >= 95:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ PRODUCTION READY{Colors.ENDC}")
        return 0
    elif success_rate >= 80:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ NEEDS ATTENTION - MOSTLY READY{Colors.ENDC}")
        return 1
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ NOT READY FOR PRODUCTION{Colors.ENDC}")
        return 2


def main():
    """Run all tests."""
    print_header("OpenEmbed Production Validation Test Suite", "=")

    # Cleanup before starting
    print_test("Cleaning up existing vector stores...")
    cleanup_all_stores()
    time.sleep(1)

    # Run tests
    test_health_check()
    uploaded_files = test_individual_uploads()
    test_multi_modal_upload()
    created_stores = test_vector_store_creation()
    test_add_embeddings(uploaded_files, created_stores)
    test_list_stores()
    test_semantic_search()
    test_cross_modal_search()
    test_file_serving(uploaded_files)

    # Print results
    exit_code = print_final_results()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

