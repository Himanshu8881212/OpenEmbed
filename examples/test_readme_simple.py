"""
Simple, realistic README example that actually works.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python'))

from openembed import OpenEmbedClient

print("\n" + "=" * 60)
print("README Example - Simple Search")
print("=" * 60 + "\n")

# Connect to EMBEd service
client = OpenEmbedClient("http://localhost:8000")

# Search your documents (using existing test store)
print("Searching for: 'artificial intelligence'\n")

results = client.search(
    vector_store="test_get_started",
    query="artificial intelligence",
    n_results=3
)

print(f"Found {len(results)} results:\n")

# Display results
for i, result in enumerate(results, 1):
    print(f"{i}. {result['metadata']['filename']}")
    print(f"   Similarity: {result['similarity']:.1%}")
    print(f"   Modality: {result['metadata'].get('modality', 'N/A')}")
    print()

print("=" * 60)
print("✅ Search completed!")
print("=" * 60)
