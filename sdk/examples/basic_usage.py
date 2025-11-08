"""
Basic Usage Examples for OpenEmbed SDK
======================================

This file demonstrates basic operations with OpenEmbed.
"""

import sys
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from openembed import OpenEmbedClient, OpenEmbedError


def example_1_search():
    """Example 1: Basic text search."""
    print("=" * 80)
    print("Example 1: Basic Text Search")
    print("=" * 80)
    
    client = OpenEmbedClient("http://localhost:8000")
    
    # Search with text query
    results = client.search(
        vector_store="my_multimodal_store",
        query="beautiful sunset over the ocean",
        n_results=5
    )
    
    print(f"\nFound {len(results)} results:")
    for i, result in enumerate(results, 1):
        filename = result['metadata']['filename']
        modality = result['modality']
        similarity = result['similarity']
        print(f"{i}. {filename} ({modality}) - {similarity:.1%} match")


def example_2_upload():
    """Example 2: Upload files."""
    print("\n" + "=" * 80)
    print("Example 2: Upload Files")
    print("=" * 80)
    
    client = OpenEmbedClient("http://localhost:8000")
    
    # Upload a single file
    # Uncomment to test:
    # result = client.upload(
    #     vector_store="my_multimodal_store",
    #     file_path="path/to/your/file.jpg",
    #     modality="image"
    # )
    # print(f"\nUploaded: {result['filename']}")
    # print(f"Embedding ID: {result['embedding_id']}")
    # print(f"File ID: {result['file_id']}")
    
    print("\n(Uncomment code to test upload)")


def example_3_list_stores():
    """Example 3: List all vector stores."""
    print("\n" + "=" * 80)
    print("Example 3: List Vector Stores")
    print("=" * 80)
    
    client = OpenEmbedClient("http://localhost:8000")
    
    stores = client.list_stores()
    
    print(f"\nTotal stores: {len(stores)}")
    for store in stores:
        name = store['name']
        count = store['count']
        size_kb = store['size_bytes'] / 1024
        modalities = store['metadata'].get('modality_counts', {})
        
        print(f"\n{name}:")
        print(f"  Files: {count}")
        print(f"  Size: {size_kb:.2f} KB")
        print(f"  Modalities: {list(modalities.keys())}")


def example_4_get_files():
    """Example 4: Get files in a store."""
    print("\n" + "=" * 80)
    print("Example 4: Get Files in Store")
    print("=" * 80)
    
    client = OpenEmbedClient("http://localhost:8000")
    
    files = client.get_files("my_multimodal_store")
    
    print(f"\nFiles in 'my_multimodal_store': {len(files)}")
    for file in files:
        print(f"  - {file['filename']} ({file['modality']})")


def example_5_error_handling():
    """Example 5: Error handling."""
    print("\n" + "=" * 80)
    print("Example 5: Error Handling")
    print("=" * 80)
    
    client = OpenEmbedClient("http://localhost:8000")
    
    try:
        # Try to search in non-existent store
        results = client.search("non_existent_store", "test query")
    except OpenEmbedError as e:
        print(f"\nCaught error: {e}")
        print("✓ Error handling works correctly")


def example_6_health_check():
    """Example 6: Health check."""
    print("\n" + "=" * 80)
    print("Example 6: Health Check")
    print("=" * 80)
    
    client = OpenEmbedClient("http://localhost:8000")
    
    status = client.health()
    print(f"\nAPI Status: {status.get('status', 'unknown')}")
    print(f"Message: {status.get('message', 'N/A')}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("OpenEmbed SDK - Basic Usage Examples")
    print("=" * 80)
    print("\nMake sure OpenEmbed is running at http://localhost:8000")
    print("and you have a vector store named 'my_multimodal_store'\n")
    
    try:
        example_1_search()
        example_2_upload()
        example_3_list_stores()
        example_4_get_files()
        example_5_error_handling()
        example_6_health_check()
        
        print("\n" + "=" * 80)
        print("All examples completed!")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("Make sure OpenEmbed is running and accessible.")

