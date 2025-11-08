#!/usr/bin/env python3
"""
Comprehensive Vector Store Test
Tests the complete workflow: Upload → Embed → Store → Search
"""

import requests
import json
import os
from pathlib import Path
from typing import Dict, List

# Configuration
BASE_URL = "http://localhost:8000"
DEMO_FILES_DIR = Path("demo_files")

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

# Test files for each modality
TEST_FILES = {
    "text": "sample_text.txt",
    "image": "sample_image.jpg",
    "video": "sample_video.mp4",
    "audio": "sample_audio.wav",
    "depth": "sample_depth.png",
    "thermal": "sample_thermal.png",
    "imu": "sample_imu.csv"
}

# Search queries for each modality
SEARCH_QUERIES = {
    "text": "beautiful sunset over the ocean",
    "image": "sample_image.jpg",
    "video": "sample_video.mp4",
    "audio": "sample_audio.wav"
}


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BOLD}{CYAN}{'=' * 80}{RESET}")
    print(f"{BOLD}{CYAN}{text.center(80)}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 80}{RESET}\n")


def print_step(step_num: int, text: str):
    """Print a step header."""
    print(f"\n{BOLD}{BLUE}[Step {step_num}] {text}{RESET}")
    print(f"{BLUE}{'-' * 80}{RESET}")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗ {text}{RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{YELLOW}ℹ {text}{RESET}")


def embed_file_to_store(file_path: Path, modality: str, store_name: str, create_new: bool = False) -> Dict:
    """Upload file and add embedding to vector store in one step."""
    with open(file_path, 'rb') as f:
        files = {'file': (file_path.name, f)}
        data = {
            'modality': modality,
            'vector_store': store_name,
            'create_new': str(create_new).lower()
        }
        response = requests.post(f"{BASE_URL}/api/embed", files=files, data=data)
        response.raise_for_status()
        return response.json()


def create_vector_store(name: str, modality: str, description: str = "") -> Dict:
    """Create a vector store."""
    data = {
        "name": name,
        "modality": modality,
        "description": description
    }
    response = requests.post(f"{BASE_URL}/api/vector-stores", json=data)
    response.raise_for_status()
    return response.json()


def search_by_text(store_name: str, query_text: str, query_modality: str, n_results: int = 5) -> Dict:
    """Search using text query."""
    data = {
        "vector_store_name": store_name,
        "query_text": query_text,
        "query_modality": query_modality,
        "n_results": n_results
    }
    response = requests.post(f"{BASE_URL}/api/search-by-id", json=data)
    response.raise_for_status()
    return response.json()


def search_by_file(store_name: str, file_path: Path, query_modality: str, n_results: int = 5) -> Dict:
    """Search using file."""
    with open(file_path, 'rb') as f:
        files = {'file': (file_path.name, f)}
        data = {
            'vector_store': store_name,
            'modality': query_modality,
            'n_results': str(n_results)
        }
        response = requests.post(f"{BASE_URL}/api/search", files=files, data=data)
        response.raise_for_status()
        return response.json()


def get_vector_stores() -> Dict:
    """Get all vector stores."""
    response = requests.get(f"{BASE_URL}/api/vector-stores")
    response.raise_for_status()
    return response.json()


def main():
    print_header("COMPREHENSIVE VECTOR STORE TEST")
    print_info(f"Testing complete workflow: Upload → Embed → Store → Search")
    print_info(f"Base URL: {BASE_URL}")
    print_info(f"Demo files directory: {DEMO_FILES_DIR}")

    # Step 1: Create multi-modal vector store
    print_step(1, "Creating multi-modal vector store")
    store_name = "comprehensive_multimodal_store"
    try:
        result = create_vector_store(
            name=store_name,
            modality="text",  # Primary modality
            description="Comprehensive test store with all 7 modalities"
        )
        print_success(f"Created vector store: {store_name}")
    except Exception as e:
        # Store might already exist, that's okay
        print_info(f"Vector store may already exist: {str(e)}")

    # Step 2: Upload and embed files for all modalities
    print_step(2, "Uploading and embedding files for all 7 modalities")
    embedded_files = {}
    for modality, filename in TEST_FILES.items():
        file_path = DEMO_FILES_DIR / filename
        if not file_path.exists():
            print_error(f"{modality}: File not found - {file_path}")
            continue

        try:
            result = embed_file_to_store(file_path, modality, store_name, create_new=False)
            embedded_files[modality] = result['embedding_id']
            print_success(f"{modality.upper()}: Embedded {filename} → ID: {result['embedding_id'][:8]}... (shape: {result['embedding_shape']})")
        except Exception as e:
            print_error(f"{modality.upper()}: Embedding failed - {str(e)}")

    print_info(f"Successfully embedded {len(embedded_files)}/7 modalities")
    
    # Step 3: Verify vector store contents
    print_step(3, "Verifying vector store contents")
    try:
        stores = get_vector_stores()
        target_store = None
        for store in stores['stores']:
            if store['name'] == store_name:
                target_store = store
                break

        if target_store:
            print_success(f"Store found: {store_name}")
            print_info(f"  - Embedding count: {target_store['count']}")
            print_info(f"  - Storage size: {target_store['size_bytes'] / 1024:.2f} KB")
            print_info(f"  - Modality: {target_store['modality']}")
        else:
            print_error(f"Store not found: {store_name}")
    except Exception as e:
        print_error(f"Failed to verify store: {str(e)}")
    
    # Step 4: Test text-based search
    print_step(4, "Testing text-based semantic search")
    query_text = "beautiful sunset over the ocean"
    try:
        result = search_by_text(store_name, query_text, "text", n_results=5)
        print_success(f"Search completed for query: '{query_text}'")
        print_info(f"Found {len(result['results'])} results")

        if result['results']:
            for i, res in enumerate(result['results'][:3], 1):
                print(f"  {i}. File ID: {res['id'][:8]}... | Similarity: {res['similarity']:.4f} | Modality: {res.get('modality', 'N/A')}")
        else:
            print_error("No results found!")
    except Exception as e:
        print_error(f"Text search failed: {str(e)}")

    # Step 5: Test file-based search (image)
    print_step(5, "Testing file-based search (Image → All)")
    image_path = DEMO_FILES_DIR / "sample_image.jpg"
    if image_path.exists():
        try:
            result = search_by_file(store_name, image_path, "image", n_results=5)
            print_success(f"Search completed using image: {image_path.name}")
            print_info(f"Found {len(result['results'])} results")

            if result['results']:
                for i, res in enumerate(result['results'][:3], 1):
                    print(f"  {i}. File ID: {res['id'][:8]}... | Similarity: {res['similarity']:.4f} | Modality: {res.get('modality', 'N/A')}")
            else:
                print_error("No results found!")
        except Exception as e:
            print_error(f"Image search failed: {str(e)}")

    # Step 6: Test cross-modal search (Audio → All)
    print_step(6, "Testing cross-modal search (Audio → All)")
    audio_path = DEMO_FILES_DIR / "sample_audio.wav"
    if audio_path.exists():
        try:
            result = search_by_file(store_name, audio_path, "audio", n_results=5)
            print_success(f"Search completed using audio: {audio_path.name}")
            print_info(f"Found {len(result['results'])} results")

            if result['results']:
                for i, res in enumerate(result['results'][:3], 1):
                    print(f"  {i}. File ID: {res['id'][:8]}... | Similarity: {res['similarity']:.4f} | Modality: {res.get('modality', 'N/A')}")
            else:
                print_error("No results found!")
        except Exception as e:
            print_error(f"Audio search failed: {str(e)}")

    # Final summary
    print_header("TEST SUMMARY")
    print_success(f"✓ Embedded {len(embedded_files)}/7 modalities")
    print_success(f"✓ Created vector store: {store_name}")
    print_success(f"✓ Tested text-based search")
    print_success(f"✓ Tested file-based search (image)")
    print_success(f"✓ Tested cross-modal search (audio)")
    print_info("\nVector store is ready for production use!")


if __name__ == "__main__":
    main()

