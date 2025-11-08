"""
Test the README example to make sure it actually works.
This is the EXACT code that will be in the README.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python'))

from openembed import OpenEmbedClient

print("=" * 80)
print("Testing README Example - Basic Search")
print("=" * 80)

# EXACT code from README "Step 3: Query from Python"
client = OpenEmbedClient("http://localhost:8000")

# Search your documents
results = client.search(
    vector_store="test_get_started",  # Using store from get_started.py
    query="What is artificial intelligence?",
    n_results=5
)

# Use the results
for result in results:
    print(f"📄 {result['metadata']['filename']}")
    print(f"   Similarity: {result['similarity']:.1%}")
    content = result['metadata'].get('text_content', 'N/A')
    print(f"   Content: {content[:200]}")
    print()

print("=" * 80)
print("✅ Basic example works!")
print("=" * 80)
print()

# Now test RAG example
print("=" * 80)
print("Testing README Example - RAG with Mock LLM")
print("=" * 80)

# 1. Get relevant documents from EMBEd
results = client.search("test_get_started", "What is Python?", n_results=3)

print(f"\n📚 Retrieved {len(results)} documents:")
for i, r in enumerate(results, 1):
    print(f"   {i}. {r['metadata']['filename']} ({r['similarity']:.1%} match)")

# 2. Build context from results
context = "\n\n".join([
    f"Source: {r['metadata']['filename']}\n{r['metadata'].get('text_content', '')}"
    for r in results
])

print(f"\n📝 Context built ({len(context)} characters)")
print(f"Context preview:\n{context[:300]}...\n")

# 3. Send to LLM (mocked - just show the context)
print("🤖 In real usage, you would send this context to:")
print("   - OpenAI (gpt-4, gpt-3.5-turbo)")
print("   - Anthropic (claude-3-opus, claude-3-sonnet)")
print("   - Ollama (llama2, mistral)")
print("   - LM Studio (local models)")
print()

print("=" * 80)
print("✅ RAG example works!")
print("=" * 80)
