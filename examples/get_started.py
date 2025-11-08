#!/usr/bin/env python3
"""
EMBEd Get Started - Quick RAG Setup
====================================

This script helps you quickly set up a RAG (Retrieval-Augmented Generation) 
application using EMBEd for embeddings and your choice of LLM.

Usage:
    python get_started.py

Requirements:
    - EMBEd server running (Docker or local)
    - LLM provider (LM Studio, OpenAI, or Anthropic)
    - Python packages: openai, anthropic (optional)
"""

import sys
import os
from pathlib import Path

# Add SDK to path
sdk_path = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

from openembed import OpenEmbedClient
from openai import OpenAI
import json


class SimpleRAG:
    """Simple RAG application using EMBEd."""
    
    def __init__(
        self,
        embed_url: str = "http://localhost:8000",
        llm_provider: str = "lmstudio",
        llm_url: str = None,
        llm_model: str = None,
        llm_api_key: str = None
    ):
        """
        Initialize RAG application.
        
        Args:
            embed_url: EMBEd server URL
            llm_provider: LLM provider (lmstudio, openai, anthropic)
            llm_url: LLM API URL (for lmstudio)
            llm_model: LLM model name
            llm_api_key: API key (for openai/anthropic)
        """
        self.embed_client = OpenEmbedClient(embed_url)
        self.llm_provider = llm_provider
        
        # Setup LLM client
        if llm_provider == "lmstudio":
            llm_url = llm_url or "http://localhost:1234/v1"
            self.llm_client = OpenAI(base_url=llm_url, api_key="lm-studio")
            self.llm_model = llm_model or "local-model"
            
        elif llm_provider == "openai":
            self.llm_client = OpenAI(api_key=llm_api_key)
            self.llm_model = llm_model or "gpt-4"
            
        elif llm_provider == "anthropic":
            try:
                from anthropic import Anthropic
                self.llm_client = Anthropic(api_key=llm_api_key)
                self.llm_model = llm_model or "claude-3-5-sonnet-20241022"
            except ImportError:
                raise ImportError("Install anthropic: pip install anthropic")
        else:
            raise ValueError(f"Unknown provider: {llm_provider}")
    
    def create_vector_store(self, store_name: str, description: str = ""):
        """Create a new vector store."""
        print(f"\n📦 Creating vector store: {store_name}")
        result = self.embed_client.create_store(store_name, description)
        print(f"✅ Store created: {result['name']}")
        return result
    
    def add_documents(self, store_name: str, file_paths: list):
        """Add documents to vector store."""
        print(f"\n📄 Adding {len(file_paths)} documents to {store_name}...")
        
        results = []
        for file_path in file_paths:
            if not os.path.exists(file_path):
                print(f"⚠️  File not found: {file_path}")
                continue
                
            result = self.embed_client.upload_file(store_name, file_path)
            results.append(result)
            print(f"✅ Added: {os.path.basename(file_path)}")
        
        print(f"\n✅ Added {len(results)} documents successfully")
        return results
    
    def query(self, store_name: str, question: str, n_results: int = 3):
        """
        Query the RAG system.
        
        Args:
            store_name: Vector store name
            question: User question
            n_results: Number of documents to retrieve
            
        Returns:
            dict: Answer and retrieved documents
        """
        print(f"\n🔍 Query: {question}")
        print(f"   Store: {store_name}")
        
        # Retrieve relevant documents
        print(f"\n📚 Retrieving top {n_results} documents...")
        search_results = self.embed_client.search_by_text(
            store_name,
            question,
            n_results=n_results
        )
        
        if not search_results.get("results"):
            print("❌ No documents found")
            return {"answer": "No relevant documents found.", "documents": []}
        
        # Display retrieved documents
        documents = []
        for i, result in enumerate(search_results["results"], 1):
            metadata = result.get("metadata", {})
            distance = result.get("distance", 0)
            relevance = (1 - distance) * 100
            
            doc_info = {
                "filename": metadata.get("filename", "unknown"),
                "modality": metadata.get("modality", "unknown"),
                "relevance": relevance
            }
            documents.append(doc_info)
            
            print(f"   {i}. {doc_info['modality']}: {doc_info['filename']} ({relevance:.1f}%)")
        
        # Build context from documents
        context_parts = []
        for i, result in enumerate(search_results["results"], 1):
            metadata = result.get("metadata", {})
            filename = metadata.get("filename", "unknown")
            modality = metadata.get("modality", "unknown")
            
            # For text files, include content if available
            if modality == "text" and "text_content" in metadata:
                content = metadata["text_content"][:500]  # Limit to 500 chars
                context_parts.append(f"[{i}] {filename}:\n{content}")
            else:
                context_parts.append(f"[{i}] {filename} ({modality})")
        
        context = "\n\n".join(context_parts)
        
        # Generate answer
        print(f"\n🤖 Generating answer with {self.llm_provider}...")
        answer = self._generate_answer(question, context)
        
        print(f"\n📝 ANSWER:")
        print("-" * 80)
        print(answer)
        print("-" * 80)
        
        return {
            "answer": answer,
            "documents": documents,
            "context": context
        }
    
    def _generate_answer(self, question: str, context: str) -> str:
        """Generate answer using LLM."""
        prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {question}

Answer:"""
        
        try:
            if self.llm_provider in ["lmstudio", "openai"]:
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that answers questions based on the provided context."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                return response.choices[0].message.content
                
            elif self.llm_provider == "anthropic":
                response = self.llm_client.messages.create(
                    model=self.llm_model,
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
                
        except Exception as e:
            return f"Error generating answer: {str(e)}"


def main():
    """Interactive setup and demo."""
    print("="*80)
    print("🚀 EMBEd RAG - Get Started")
    print("="*80)
    
    # Step 1: Configure EMBEd
    print("\n📍 Step 1: EMBEd Server Configuration")
    embed_url = input("EMBEd URL [http://localhost:8000]: ").strip() or "http://localhost:8000"
    
    # Step 2: Configure LLM
    print("\n🤖 Step 2: LLM Provider Configuration")
    print("Available providers:")
    print("  1. LM Studio (local)")
    print("  2. OpenAI (cloud)")
    print("  3. Anthropic (cloud)")
    
    provider_choice = input("Choose provider [1]: ").strip() or "1"
    
    if provider_choice == "1":
        llm_provider = "lmstudio"
        llm_url = input("LM Studio URL [http://localhost:1234/v1]: ").strip() or "http://localhost:1234/v1"
        llm_model = input("Model name [local-model]: ").strip() or "local-model"
        llm_api_key = None
    elif provider_choice == "2":
        llm_provider = "openai"
        llm_url = None
        llm_model = input("Model name [gpt-4]: ").strip() or "gpt-4"
        llm_api_key = input("OpenAI API key: ").strip()
    elif provider_choice == "3":
        llm_provider = "anthropic"
        llm_url = None
        llm_model = input("Model name [claude-3-5-sonnet-20241022]: ").strip() or "claude-3-5-sonnet-20241022"
        llm_api_key = input("Anthropic API key: ").strip()
    else:
        print("Invalid choice. Using LM Studio.")
        llm_provider = "lmstudio"
        llm_url = "http://localhost:1234/v1"
        llm_model = "local-model"
        llm_api_key = None
    
    # Initialize RAG
    print("\n⚙️  Initializing RAG system...")
    try:
        rag = SimpleRAG(
            embed_url=embed_url,
            llm_provider=llm_provider,
            llm_url=llm_url,
            llm_model=llm_model,
            llm_api_key=llm_api_key
        )
        print("✅ RAG system initialized")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Step 3: Create or use existing store
    print("\n📦 Step 3: Vector Store")
    store_name = input("Vector store name [my_rag_store]: ").strip() or "my_rag_store"
    
    try:
        rag.create_vector_store(store_name, "My RAG knowledge base")
    except Exception as e:
        print(f"⚠️  Store might already exist: {e}")
    
    # Step 4: Add documents
    print("\n📄 Step 4: Add Documents")
    print("Enter file paths (one per line, empty line to finish):")
    
    file_paths = []
    while True:
        path = input("File path: ").strip()
        if not path:
            break
        file_paths.append(path)
    
    if file_paths:
        rag.add_documents(store_name, file_paths)
    else:
        print("⚠️  No documents added. Using existing documents in store.")
    
    # Step 5: Query loop
    print("\n💬 Step 5: Ask Questions")
    print("Type your questions (or 'quit' to exit)")
    
    while True:
        question = input("\n❓ Question: ").strip()
        if question.lower() in ["quit", "exit", "q"]:
            break
        
        if not question:
            continue
        
        try:
            rag.query(store_name, question)
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n👋 Thanks for using EMBEd RAG!")


if __name__ == "__main__":
    main()

