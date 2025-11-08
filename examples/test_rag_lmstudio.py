#!/usr/bin/env python3
"""
Test RAG Application with LM Studio
====================================

Complete test of RAG application using:
- EMBEd for embeddings
- LM Studio with Qwen3-VL-4B for generation
- Multi-modal vector store

Usage:
    python test_rag_lmstudio.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_application import EMBEdRAG
from build_multimodal_store import build_vector_store


def test_lmstudio_connection(url: str = "http://localhost:1234/v1", model: str = "qwen/qwen3-vl-4b"):
    """Test LM Studio connection."""
    print("\n" + "="*80)
    print("🔌 Testing LM Studio Connection")
    print("="*80)
    
    try:
        from openai import OpenAI
        
        client = OpenAI(
            base_url=url,
            api_key="lm-studio"
        )
        
        print(f"\n📡 Connecting to LM Studio at {url}...")
        print(f"   Model: {model}")
        
        # Test with a simple query
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello, I am working!' in one sentence."}
            ],
            max_tokens=50,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        print(f"\n✅ LM Studio is working!")
        print(f"   Response: {answer}")
        return True
        
    except Exception as e:
        print(f"\n❌ LM Studio connection failed!")
        print(f"   Error: {e}")
        print("\n💡 Make sure:")
        print("   1. LM Studio is running")
        print("   2. Model 'qwen/qwen3-vl-4b' is loaded")
        print("   3. Server is started on port 1234")
        return False


def test_embed_connection(url: str = "http://localhost:8000"):
    """Test EMBEd connection."""
    print("\n" + "="*80)
    print("🔌 Testing EMBEd Connection")
    print("="*80)
    
    try:
        from openembed import OpenEmbedClient
        
        client = OpenEmbedClient(url)
        print(f"\n📡 Connecting to EMBEd at {url}...")
        
        # Test health endpoint
        health = client._request("GET", "/health")
        print(f"\n✅ EMBEd is working!")
        print(f"   Status: {health.get('status', 'unknown')}")
        return True
        
    except Exception as e:
        print(f"\n❌ EMBEd connection failed!")
        print(f"   Error: {e}")
        print("\n💡 Make sure:")
        print("   1. EMBEd server is running")
        print("   2. Docker container is up: docker-compose up -d")
        return False


def run_rag_tests(store_name: str = "multimodal_demo"):
    """Run comprehensive RAG tests."""
    print("\n" + "="*80)
    print("🧪 Running RAG Tests")
    print("="*80)
    
    # Initialize RAG
    print("\n1️⃣  Initializing RAG with LM Studio...")
    try:
        rag = EMBEdRAG(
            embed_url="http://localhost:8000",
            llm_provider="lmstudio",
            llm_url="http://localhost:1234/v1",
            llm_model="qwen/qwen3-vl-4b",
            mode="multimodal"
        )
    except Exception as e:
        print(f"❌ Failed to initialize RAG: {e}")
        return False
    
    # Test queries
    test_queries = [
        {
            "question": "What is artificial intelligence?",
            "description": "Text-based query about AI"
        },
        {
            "question": "Tell me about renewable energy sources",
            "description": "Query about renewable energy"
        },
        {
            "question": "What are the facts about climate change?",
            "description": "Query about climate change"
        },
        {
            "question": "Describe healthy eating principles",
            "description": "Query about nutrition"
        },
        {
            "question": "What are the milestones in space exploration?",
            "description": "Query about space"
        }
    ]
    
    print(f"\n2️⃣  Running {len(test_queries)} test queries...")
    
    results = []
    for i, test in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}/{len(test_queries)}: {test['description']}")
        print(f"{'='*80}")
        
        try:
            result = rag.query(
                store_name=store_name,
                question=test["question"],
                n_results=3,
                verbose=True
            )
            
            print(f"\n📝 ANSWER:")
            print("-" * 80)
            print(result["answer"])
            print("-" * 80)
            
            results.append({
                "question": test["question"],
                "success": True,
                "answer": result["answer"],
                "sources": result["n_sources"]
            })
            
        except Exception as e:
            print(f"\n❌ Query failed: {e}")
            results.append({
                "question": test["question"],
                "success": False,
                "error": str(e)
            })
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    successful = sum(1 for r in results if r["success"])
    total = len(results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {total - successful}")
    print(f"Success Rate: {successful/total*100:.1f}%")
    
    if successful == total:
        print("\n✅ All tests passed!")
        return True
    else:
        print("\n⚠️  Some tests failed")
        for r in results:
            if not r["success"]:
                print(f"   ❌ {r['question']}: {r.get('error', 'Unknown error')}")
        return False


def main():
    """Main test function."""
    print("\n" + "="*80)
    print("🚀 EMBEd RAG with LM Studio - Complete Test")
    print("="*80)
    print("\nThis script will:")
    print("1. Test LM Studio connection")
    print("2. Test EMBEd connection")
    print("3. Build multi-modal vector store")
    print("4. Run RAG queries with LM Studio")
    
    # Test connections
    lmstudio_ok = test_lmstudio_connection()
    embed_ok = test_embed_connection()
    
    if not lmstudio_ok or not embed_ok:
        print("\n❌ Prerequisites not met. Please fix the issues above.")
        sys.exit(1)
    
    # Build vector store
    print("\n" + "="*80)
    print("📦 Building Vector Store")
    print("="*80)
    
    store_name = "multimodal_demo"
    
    try:
        build_vector_store(store_name)
    except Exception as e:
        print(f"\n❌ Failed to build vector store: {e}")
        sys.exit(1)
    
    # Run RAG tests
    success = run_rag_tests(store_name)
    
    # Final summary
    print("\n" + "="*80)
    print("🎉 TEST COMPLETE")
    print("="*80)
    
    if success:
        print("\n✅ All systems working!")
        print("\n📚 Your multi-modal RAG is ready to use!")
        print(f"\nVector Store: {store_name}")
        print("LLM: LM Studio (qwen/qwen3-vl-4b)")
        print("Embeddings: EMBEd (ImageBind)")
        
        print("\n💡 Try it yourself:")
        print(f"\n  python rag_application.py \\")
        print(f"    --mode multimodal \\")
        print(f"    --store {store_name} \\")
        print(f"    --llm lmstudio \\")
        print(f"    --llm-model 'qwen/qwen3-vl-4b' \\")
        print(f"    --query 'Your question here'")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

