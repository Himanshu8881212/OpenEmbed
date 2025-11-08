#!/usr/bin/env python3
"""
EMBEd RAG Demo
==============

Interactive demo showing text-only and multi-modal RAG.

This demo creates sample documents and shows how easy it is to switch
between text-only and multi-modal RAG.

Usage:
    python demo.py
"""

import os
import sys
from pathlib import Path
import tempfile

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_application import EMBEdRAG


def create_sample_documents():
    """Create sample documents for demo."""
    temp_dir = Path(tempfile.mkdtemp(prefix="embed_demo_"))
    
    # Sample text documents
    docs = {
        "company_policy.txt": """
Company Vacation Policy

All full-time employees are entitled to paid vacation days:
- New employees: 10 days per year
- After 3 years: 15 days per year  
- After 5 years: 20 days per year

Vacation requests must be submitted at least 2 weeks in advance.
Unused vacation days can be carried over (maximum 5 days).
""",
        "expense_policy.txt": """
Expense Reimbursement Policy

Employees can submit expense reports for:
- Travel expenses (flights, hotels, meals)
- Office supplies
- Client entertainment
- Professional development

All expenses must be submitted within 30 days with receipts.
Reimbursement is processed within 2 weeks.
Maximum meal allowance: $50 per day.
""",
        "remote_work.txt": """
Remote Work Policy

Employees may work remotely up to 3 days per week.

Requirements:
- Stable internet connection (minimum 25 Mbps)
- Dedicated workspace
- Available during core hours (10 AM - 3 PM)
- Attend all team meetings

Remote work requests must be approved by your manager.
Equipment will be provided for home office setup.
"""
    }
    
    for filename, content in docs.items():
        (temp_dir / filename).write_text(content.strip())
    
    print(f"✅ Created {len(docs)} sample documents in {temp_dir}")
    return temp_dir, list(docs.keys())


def demo_text_rag():
    """Demo text-only RAG."""
    print("\n" + "="*80)
    print("📝 DEMO 1: TEXT-ONLY RAG (Company Knowledge Base)")
    print("="*80)
    
    # Create sample documents
    temp_dir, filenames = create_sample_documents()
    file_paths = [str(temp_dir / f) for f in filenames]
    
    # Initialize RAG in text mode
    print("\n1️⃣  Initializing Text-Only RAG...")
    rag = EMBEdRAG(
        embed_url="http://localhost:8000",
        llm_provider="openai",
        mode="text"  # ← Text-only mode
    )
    
    # Create vector store
    print("\n2️⃣  Creating vector store...")
    store_name = "demo_company_kb"
    rag.create_vector_store(store_name, "Demo company knowledge base")
    
    # Index documents
    print("\n3️⃣  Indexing documents...")
    rag.index_documents(store_name, file_paths)
    
    # Query 1
    print("\n4️⃣  Asking questions...")
    result1 = rag.query(
        store_name=store_name,
        question="How many vacation days do new employees get?",
        n_results=3
    )
    
    print("\n" + "="*80)
    print("📝 ANSWER 1")
    print("="*80)
    print(result1["answer"])
    print("="*80)
    
    # Query 2
    result2 = rag.query(
        store_name=store_name,
        question="What is the meal allowance for travel?",
        n_results=3,
        verbose=False
    )
    
    print("\n" + "="*80)
    print("📝 ANSWER 2")
    print("="*80)
    print(result2["answer"])
    print("="*80)
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    print("\n✅ Text-only RAG demo complete!")
    return store_name


def demo_multimodal_rag():
    """Demo multi-modal RAG."""
    print("\n" + "="*80)
    print("🌈 DEMO 2: MULTI-MODAL RAG (Product Catalog)")
    print("="*80)
    
    print("\n⚠️  Note: This demo requires actual image/video files.")
    print("For a full multi-modal demo, add your own media files and run:")
    print("\n    python rag_application.py \\")
    print("      --mode multimodal \\")
    print("      --store product_catalog \\")
    print("      --create-store \\")
    print("      --index 'images/*.jpg' 'videos/*.mp4' 'descriptions/*.txt'")
    print("\nThen query:")
    print("\n    python rag_application.py \\")
    print("      --mode multimodal \\")
    print("      --store product_catalog \\")
    print("      --query 'red sneakers'")
    
    print("\n" + "="*80)
    print("🎯 KEY POINT: Switching from Text to Multi-Modal")
    print("="*80)
    print("\nTo switch from text-only to multi-modal RAG:")
    print("\n  # Text-only")
    print("  rag = EMBEdRAG(mode='text')")
    print("\n  # Multi-modal - JUST CHANGE ONE PARAMETER!")
    print("  rag = EMBEdRAG(mode='multimodal')  # ← That's it!")
    print("\nEverything else stays the same!")
    print("="*80)


def demo_comparison():
    """Show side-by-side comparison."""
    print("\n" + "="*80)
    print("📊 COMPARISON: Text-Only vs Multi-Modal RAG")
    print("="*80)
    
    comparison = """
┌─────────────────────┬──────────────────────┬──────────────────────┐
│ Feature             │ Text-Only RAG        │ Multi-Modal RAG      │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ Input Files         │ .txt, .pdf, .docx    │ .txt, .jpg, .mp4,    │
│                     │                      │ .mp3, .wav, etc.     │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ Search Capability   │ Text → Text          │ Text → All modalities│
│                     │                      │ Image → All          │
│                     │                      │ Video → All          │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ Use Cases           │ • Q&A systems        │ • Product search     │
│                     │ • Knowledge bases    │ • Media libraries    │
│                     │ • Document search    │ • Content discovery  │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ Code Change         │ mode="text"          │ mode="multimodal"    │
│                     │                      │ ← ONLY THIS!         │
└─────────────────────┴──────────────────────┴──────────────────────┘

Example Code:

# Text-Only RAG
rag = EMBEdRAG(mode="text")
rag.index_documents("my_store", ["doc1.txt", "doc2.pdf"])
result = rag.query("my_store", "What is the vacation policy?")

# Multi-Modal RAG - SAME CODE, DIFFERENT MODE!
rag = EMBEdRAG(mode="multimodal")  # ← Only change
rag.index_documents("my_store", ["doc.txt", "img.jpg", "vid.mp4"])
result = rag.query("my_store", "Show me red products")
"""
    print(comparison)


def main():
    """Run all demos."""
    print("\n" + "="*80)
    print("🚀 EMBEd RAG Application Demo")
    print("="*80)
    print("\nThis demo shows how easy it is to build RAG applications with EMBEd.")
    print("You can switch between text-only and multi-modal RAG with ONE parameter!")
    
    # Check prerequisites
    print("\n📋 Checking prerequisites...")
    
    # Check EMBEd server
    try:
        from openembed import OpenEmbedClient
        client = OpenEmbedClient("http://localhost:8000")
        health = client._request("GET", "/health")
        print("✅ EMBEd server is running")
    except Exception as e:
        print("❌ EMBEd server not running!")
        print("   Start it with: docker-compose up -d")
        print(f"   Error: {e}")
        return
    
    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  OPENAI_API_KEY not set!")
        print("   Set it with: export OPENAI_API_KEY='sk-...'")
        print("\n   Skipping LLM demos (will show retrieval only)")
        demo_retrieval_only = True
    else:
        print("✅ OpenAI API key found")
        demo_retrieval_only = False
    
    # Run demos
    if not demo_retrieval_only:
        try:
            demo_text_rag()
        except Exception as e:
            print(f"\n❌ Error in text RAG demo: {e}")
            import traceback
            traceback.print_exc()
    
    demo_multimodal_rag()
    demo_comparison()
    
    print("\n" + "="*80)
    print("🎉 Demo Complete!")
    print("="*80)
    print("\nNext Steps:")
    print("1. Try the examples in examples/README.md")
    print("2. Build your own RAG application")
    print("3. Switch between text and multi-modal with one parameter!")
    print("\nQuestions? Check the documentation:")
    print("  - EMBEd: ../README.md")
    print("  - Examples: examples/README.md")
    print("  - SDK: ../sdk/python/README.md")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

