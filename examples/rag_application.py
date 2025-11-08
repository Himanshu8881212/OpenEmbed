"""
EMBEd RAG Application Template
===============================

A complete RAG (Retrieval Augmented Generation) application template that works with EMBEd.

Features:
- Switch between text-only and multi-modal RAG with one parameter
- Uses EMBEd for embedding generation and retrieval
- Integrates with OpenAI/Anthropic for answer generation
- Simple, production-ready code

Usage:
    # Text-only RAG
    python rag_application.py --mode text --store my_docs --query "What is our vacation policy?"
    
    # Multi-modal RAG
    python rag_application.py --mode multimodal --store my_media --query "Show me red sneakers"

Author: EMBEd Team
License: MIT
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from openembed import OpenEmbedClient
except ImportError:
    print("❌ Error: openembed SDK not found!")
    print("Please install: pip install requests")
    print("Or add sdk/python to your PYTHONPATH")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("⚠️  Warning: OpenAI not installed. Install with: pip install openai")
    OpenAI = None

try:
    from anthropic import Anthropic
except ImportError:
    print("⚠️  Warning: Anthropic not installed. Install with: pip install anthropic")
    Anthropic = None

try:
    import requests
except ImportError:
    print("❌ Error: requests not installed. Install with: pip install requests")
    sys.exit(1)


class EMBEdRAG:
    """
    RAG Application using EMBEd for embeddings and retrieval.
    
    Supports both text-only and multi-modal RAG with a simple switch.
    """
    
    def __init__(
        self,
        embed_url: str = "http://localhost:8000",
        llm_provider: str = "openai",
        llm_url: Optional[str] = None,
        llm_model: Optional[str] = None,
        mode: str = "text"
    ):
        """
        Initialize RAG application.

        Args:
            embed_url: EMBEd API URL
            llm_provider: LLM provider ("openai", "anthropic", or "lmstudio")
            llm_url: LLM API URL (for LM Studio)
            llm_model: Model name (for LM Studio)
            mode: RAG mode ("text" or "multimodal")
        """
        self.mode = mode
        self.embed_client = OpenEmbedClient(embed_url)

        # Initialize LLM client
        if llm_provider == "openai":
            if OpenAI is None:
                raise ImportError("OpenAI not installed. Run: pip install openai")
            self.llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.llm_model = llm_model or "gpt-4"
        elif llm_provider == "anthropic":
            if Anthropic is None:
                raise ImportError("Anthropic not installed. Run: pip install anthropic")
            self.llm_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            self.llm_model = llm_model or "claude-3-sonnet-20240229"
        elif llm_provider == "lmstudio":
            # LM Studio uses OpenAI-compatible API
            if llm_url is None:
                llm_url = "http://localhost:1234/v1"
            if llm_model is None:
                raise ValueError("Model name required for LM Studio. Use --llm-model 'qwen/qwen3-vl-4b'")

            # Create OpenAI client pointing to LM Studio
            self.llm_client = OpenAI(
                base_url=llm_url,
                api_key="lm-studio"  # LM Studio doesn't require real API key
            )
            self.llm_model = llm_model
            self.llm_url = llm_url
        else:
            raise ValueError(f"Unknown LLM provider: {llm_provider}")

        self.llm_provider = llm_provider

        print(f"✅ Initialized EMBEd RAG")
        print(f"   Mode: {mode}")
        print(f"   LLM: {llm_provider} ({self.llm_model})")
        if llm_provider == "lmstudio":
            print(f"   LM Studio URL: {llm_url}")
        print(f"   EMBEd: {embed_url}")
    
    def create_vector_store(
        self,
        store_name: str,
        description: Optional[str] = None
    ) -> bool:
        """Create a new vector store."""
        try:
            if description is None:
                description = f"{'Multi-modal' if self.mode == 'multimodal' else 'Text-only'} RAG vector store"
            
            result = self.embed_client.create_store(store_name, description)
            print(f"✅ Created vector store: {store_name}")
            return True
        except Exception as e:
            if "already exists" in str(e):
                print(f"ℹ️  Vector store '{store_name}' already exists")
                return True
            print(f"❌ Error creating vector store: {e}")
            return False
    
    def index_documents(
        self,
        store_name: str,
        file_paths: List[str],
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Index documents into vector store.
        
        Args:
            store_name: Name of vector store
            file_paths: List of file paths to index
            show_progress: Show progress messages
        
        Returns:
            Dictionary with indexing results
        """
        if show_progress:
            print(f"\n📥 Indexing {len(file_paths)} files into '{store_name}'...")
        
        result = self.embed_client.upload_batch(store_name, file_paths)
        
        if show_progress:
            print(f"✅ Indexed {result.get('successful', 0)} files")
            if result.get('failed', 0) > 0:
                print(f"⚠️  Failed: {result['failed']} files")
        
        return result
    
    def retrieve(
        self,
        store_name: str,
        query: str,
        n_results: int = 5,
        modality_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents from vector store.
        
        Args:
            store_name: Name of vector store
            query: Search query
            n_results: Number of results to retrieve
            modality_filter: Optional modality filter (image, video, audio, etc.)
        
        Returns:
            List of retrieved documents with metadata
        """
        results = self.embed_client.search(
            vector_store=store_name,
            query=query,
            n_results=n_results,
            modality_filter=modality_filter
        )
        
        return results
    
    def generate_answer(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate answer using LLM.

        Args:
            query: User question
            context: Retrieved context
            system_prompt: Optional system prompt

        Returns:
            Generated answer
        """
        if system_prompt is None:
            if self.mode == "multimodal":
                system_prompt = (
                    "You are a helpful assistant that answers questions based on the provided context. "
                    "The context may include text, images, videos, and audio files. "
                    "Reference specific files when relevant."
                )
            else:
                system_prompt = (
                    "You are a helpful assistant that answers questions based on the provided context. "
                    "Only use information from the context to answer questions."
                )

        if self.llm_provider in ["openai", "lmstudio"]:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content

        elif self.llm_provider == "anthropic":
            response = self.llm_client.messages.create(
                model=self.llm_model,
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
                ]
            )
            return response.content[0].text
    
    def format_context(self, results: List[Dict[str, Any]]) -> str:
        """
        Format retrieved results into context string.
        
        Args:
            results: Retrieved documents
        
        Returns:
            Formatted context string
        """
        if not results:
            return "No relevant information found."
        
        context_parts = []
        
        for i, result in enumerate(results, 1):
            metadata = result.get('metadata', {})
            filename = metadata.get('filename', 'Unknown')
            modality = result.get('modality', 'unknown')
            similarity = result.get('similarity', 0)
            
            if self.mode == "multimodal":
                # Include modality information for multi-modal RAG
                context_parts.append(
                    f"[{i}] {modality.upper()}: {filename} (relevance: {similarity:.1%})"
                )
                
                # Add content if available
                if 'content' in metadata:
                    context_parts.append(f"    Content: {metadata['content'][:200]}...")
            else:
                # Text-only format
                context_parts.append(f"[{i}] {filename} (relevance: {similarity:.1%})")
                if 'content' in metadata:
                    context_parts.append(f"    {metadata['content'][:300]}...")
            
            context_parts.append("")  # Empty line between results
        
        return "\n".join(context_parts)
    
    def query(
        self,
        store_name: str,
        question: str,
        n_results: int = 5,
        modality_filter: Optional[str] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Complete RAG query: retrieve + generate.
        
        Args:
            store_name: Name of vector store
            question: User question
            n_results: Number of documents to retrieve
            modality_filter: Optional modality filter
            verbose: Print detailed information
        
        Returns:
            Dictionary with answer and metadata
        """
        if verbose:
            print(f"\n🔍 Query: {question}")
            print(f"   Store: {store_name}")
            print(f"   Mode: {self.mode}")
            if modality_filter:
                print(f"   Filter: {modality_filter}")
        
        # Step 1: Retrieve relevant documents
        if verbose:
            print(f"\n📚 Retrieving top {n_results} relevant documents...")
        
        results = self.retrieve(store_name, question, n_results, modality_filter)
        
        if verbose:
            print(f"✅ Retrieved {len(results)} documents")
            for i, r in enumerate(results, 1):
                print(f"   {i}. {r.get('modality', 'text')}: {r['metadata'].get('filename', 'Unknown')} ({r['similarity']:.1%})")
        
        # Step 2: Format context
        context = self.format_context(results)
        
        # Step 3: Generate answer
        if verbose:
            print(f"\n🤖 Generating answer with {self.llm_provider}...")
        
        answer = self.generate_answer(question, context)
        
        return {
            "question": question,
            "answer": answer,
            "sources": results,
            "n_sources": len(results),
            "mode": self.mode
        }


def main():
    """Main function with CLI interface."""
    parser = argparse.ArgumentParser(
        description="EMBEd RAG Application - Text-only or Multi-modal RAG"
    )
    
    parser.add_argument(
        "--mode",
        choices=["text", "multimodal"],
        default="text",
        help="RAG mode: 'text' for text-only, 'multimodal' for multi-modal"
    )
    
    parser.add_argument(
        "--store",
        required=True,
        help="Vector store name"
    )
    
    parser.add_argument(
        "--query",
        help="Query to ask"
    )
    
    parser.add_argument(
        "--index",
        nargs="+",
        help="Files to index (can be multiple files or glob patterns)"
    )
    
    parser.add_argument(
        "--llm",
        choices=["openai", "anthropic", "lmstudio"],
        default="lmstudio",
        help="LLM provider"
    )

    parser.add_argument(
        "--llm-url",
        default="http://localhost:1234/v1",
        help="LLM API URL (for LM Studio)"
    )

    parser.add_argument(
        "--llm-model",
        default="qwen/qwen3-vl-4b",
        help="Model name (for LM Studio)"
    )

    parser.add_argument(
        "--embed-url",
        default="http://localhost:8000",
        help="EMBEd API URL"
    )
    
    parser.add_argument(
        "--create-store",
        action="store_true",
        help="Create vector store if it doesn't exist"
    )
    
    args = parser.parse_args()
    
    # Initialize RAG
    try:
        rag = EMBEdRAG(
            embed_url=args.embed_url,
            llm_provider=args.llm,
            llm_url=args.llm_url if args.llm == "lmstudio" else None,
            llm_model=args.llm_model if args.llm == "lmstudio" else None,
            mode=args.mode
        )
    except Exception as e:
        print(f"❌ Error initializing RAG: {e}")
        sys.exit(1)
    
    # Create store if requested
    if args.create_store:
        rag.create_vector_store(args.store)
    
    # Index files if provided
    if args.index:
        files = []
        for pattern in args.index:
            if "*" in pattern:
                # Glob pattern
                files.extend([str(p) for p in Path(".").glob(pattern)])
            else:
                files.append(pattern)
        
        if files:
            rag.index_documents(args.store, files)
        else:
            print("⚠️  No files found to index")
    
    # Query if provided
    if args.query:
        result = rag.query(args.store, args.query)
        
        print("\n" + "="*80)
        print("📝 ANSWER")
        print("="*80)
        print(result["answer"])
        print("\n" + "="*80)
        print(f"📚 Sources: {result['n_sources']} documents")
        print("="*80)
    
    if not args.index and not args.query:
        print("\n⚠️  No action specified. Use --index to add files or --query to ask questions.")
        print("   Example: python rag_application.py --mode text --store my_docs --index *.txt --query 'What is this about?'")


if __name__ == "__main__":
    main()

