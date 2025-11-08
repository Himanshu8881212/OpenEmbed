#!/usr/bin/env python3
"""
Test script for get_started.py
Tests the SimpleRAG class programmatically
"""

import sys
import os
from pathlib import Path
import tempfile

# Add SDK to path
sdk_path = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

from get_started import SimpleRAG


def test_simple_rag():
    """Test SimpleRAG class with LM Studio."""
    print("="*80)
    print("🧪 Testing SimpleRAG Class")
    print("="*80)
    
    # Test 1: Initialize RAG
    print("\n1️⃣  Test: Initialize SimpleRAG")
    try:
        rag = SimpleRAG(
            embed_url="http://localhost:8000",
            llm_provider="lmstudio",
            llm_url="http://localhost:1234/v1",
            llm_model="qwen/qwen3-vl-4b"
        )
        print("✅ SimpleRAG initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return False
    
    # Test 2: Create vector store
    print("\n2️⃣  Test: Create Vector Store")
    store_name = "test_get_started"
    try:
        result = rag.create_vector_store(store_name, "Test store for get_started.py")
        print(f"✅ Vector store created: {result['name']}")
    except Exception as e:
        print(f"⚠️  Store might already exist: {e}")
    
    # Test 3: Create test documents
    print("\n3️⃣  Test: Create Test Documents")
    temp_dir = tempfile.mkdtemp()
    test_files = []
    
    # Create test text files
    test_docs = {
        "ai.txt": "Artificial intelligence (AI) is the simulation of human intelligence by machines. It includes machine learning, natural language processing, and computer vision.",
        "python.txt": "Python is a high-level programming language known for its simplicity and readability. It's widely used in data science, web development, and automation.",
        "embeddings.txt": "Embeddings are dense vector representations of data that capture semantic meaning. They enable similarity search and are fundamental to modern AI applications."
    }
    
    for filename, content in test_docs.items():
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w') as f:
            f.write(content)
        test_files.append(filepath)
        print(f"✅ Created: {filename}")
    
    # Test 4: Add documents
    print("\n4️⃣  Test: Add Documents to Vector Store")
    try:
        results = rag.add_documents(store_name, test_files)
        print(f"✅ Added {len(results)} documents successfully")
    except Exception as e:
        print(f"❌ Failed to add documents: {e}")
        return False
    
    # Test 5: Query the RAG system
    print("\n5️⃣  Test: Query RAG System")
    test_queries = [
        "What is artificial intelligence?",
        "Tell me about Python programming",
        "What are embeddings?"
    ]
    
    success_count = 0
    for i, question in enumerate(test_queries, 1):
        print(f"\n📝 Query {i}/{len(test_queries)}: {question}")
        try:
            result = rag.query(store_name, question, n_results=2)
            
            if result.get("answer"):
                print(f"✅ Got answer ({len(result['answer'])} chars)")
                print(f"   Retrieved {len(result.get('documents', []))} documents")
                success_count += 1
            else:
                print("❌ No answer received")
        except Exception as e:
            print(f"❌ Query failed: {e}")
    
    # Cleanup
    print("\n🧹 Cleaning up test files...")
    for filepath in test_files:
        try:
            os.remove(filepath)
        except:
            pass
    try:
        os.rmdir(temp_dir)
    except:
        pass
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    print(f"Total Queries: {len(test_queries)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(test_queries) - success_count}")
    print(f"Success Rate: {(success_count/len(test_queries)*100):.1f}%")
    
    if success_count == len(test_queries):
        print("\n✅ ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {len(test_queries) - success_count} tests failed")
        return False


if __name__ == "__main__":
    print("\n🚀 Starting get_started.py Tests\n")
    
    # Check if LM Studio is running
    print("🔍 Checking LM Studio connection...")
    try:
        from openai import OpenAI
        client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
        models = client.models.list()
        print(f"✅ LM Studio is running")
    except Exception as e:
        print(f"❌ LM Studio not running: {e}")
        print("\n⚠️  Please start LM Studio and load a model before running this test")
        sys.exit(1)
    
    # Check if EMBEd is running
    print("\n🔍 Checking EMBEd connection...")
    try:
        import requests
        response = requests.get("http://localhost:8000/api/health")
        if response.status_code == 200:
            print(f"✅ EMBEd is running")
        else:
            print(f"❌ EMBEd returned status {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ EMBEd not running: {e}")
        print("\n⚠️  Please start EMBEd before running this test")
        sys.exit(1)
    
    # Run tests
    success = test_simple_rag()
    
    if success:
        print("\n🎉 get_started.py is working perfectly!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)

