"""
RAG Application Integration Examples
=====================================

This file demonstrates how to integrate OpenEmbed into your RAG (Retrieval-Augmented Generation) applications.

Examples include:
1. Simple RAG with LangChain
2. Multi-modal RAG (text + images)
3. Custom RAG pipeline
4. Streaming RAG responses

Requirements:
    pip install requests openai langchain
"""

import requests
from typing import List, Dict, Any, Optional
from PYTHON_SDK_EXAMPLE import OpenEmbedClient


# ============================================================================
# Example 1: Simple RAG Pipeline
# ============================================================================

class SimpleRAG:
    """
    Simple RAG implementation using OpenEmbed for retrieval.
    """
    
    def __init__(self, openembed_url: str = "http://localhost:8000", openai_api_key: str = None):
        """
        Initialize the RAG system.
        
        Args:
            openembed_url: URL of the OpenEmbed API
            openai_api_key: OpenAI API key for generation
        """
        self.client = OpenEmbedClient(openembed_url)
        self.openai_api_key = openai_api_key
    
    def retrieve(
        self,
        vector_store: str,
        query: str,
        n_results: int = 5,
        filter_modality: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents from OpenEmbed.
        
        Args:
            vector_store: Name of the vector store
            query: User query
            n_results: Number of results to retrieve
            filter_modality: Optional modality filter
        
        Returns:
            List of retrieved documents
        """
        results = self.client.search_text(
            vector_store=vector_store,
            query=query,
            n_results=n_results,
            filter_modality=filter_modality
        )
        
        return results['results']
    
    def generate(self, query: str, context: List[Dict[str, Any]]) -> str:
        """
        Generate response using retrieved context.
        
        Args:
            query: User query
            context: Retrieved documents
        
        Returns:
            Generated response
        """
        # Build context string from retrieved documents
        context_str = "\n\n".join([
            f"Document {i+1} ({doc['modality']}, {doc['similarity']:.2%} similarity):\n"
            f"Filename: {doc['metadata']['filename']}\n"
            f"File ID: {doc['metadata']['file_id']}"
            for i, doc in enumerate(context)
        ])
        
        # Create prompt
        prompt = f"""Based on the following context, answer the user's question.

Context:
{context_str}

Question: {query}

Answer:"""
        
        # For this example, we'll just return the prompt
        # In production, you would call OpenAI API here
        if self.openai_api_key:
            # Example OpenAI call (commented out)
            # import openai
            # openai.api_key = self.openai_api_key
            # response = openai.ChatCompletion.create(
            #     model="gpt-4",
            #     messages=[{"role": "user", "content": prompt}]
            # )
            # return response.choices[0].message.content
            pass
        
        return f"[Generated response would appear here]\n\nContext used:\n{context_str}"
    
    def query(
        self,
        vector_store: str,
        query: str,
        n_results: int = 5,
        filter_modality: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete RAG pipeline: retrieve + generate.
        
        Args:
            vector_store: Name of the vector store
            query: User query
            n_results: Number of results to retrieve
            filter_modality: Optional modality filter
        
        Returns:
            Dictionary with answer and sources
        """
        # Retrieve relevant documents
        context = self.retrieve(vector_store, query, n_results, filter_modality)
        
        # Generate response
        answer = self.generate(query, context)
        
        return {
            "answer": answer,
            "sources": context,
            "num_sources": len(context)
        }


# ============================================================================
# Example 2: Multi-Modal RAG
# ============================================================================

class MultiModalRAG(SimpleRAG):
    """
    Multi-modal RAG that can handle text, images, audio, and video.
    """
    
    def retrieve_multimodal(
        self,
        vector_store: str,
        query: str,
        modalities: List[str] = None,
        n_results_per_modality: int = 3
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve documents from multiple modalities.
        
        Args:
            vector_store: Name of the vector store
            query: User query
            modalities: List of modalities to search (default: all)
            n_results_per_modality: Number of results per modality
        
        Returns:
            Dictionary mapping modality to results
        """
        if modalities is None:
            modalities = ['text', 'image', 'audio', 'video']
        
        results = {}
        for modality in modalities:
            try:
                modal_results = self.client.search_text(
                    vector_store=vector_store,
                    query=query,
                    n_results=n_results_per_modality,
                    filter_modality=modality
                )
                results[modality] = modal_results['results']
            except Exception as e:
                print(f"Error retrieving {modality}: {e}")
                results[modality] = []
        
        return results
    
    def query_multimodal(
        self,
        vector_store: str,
        query: str,
        modalities: List[str] = None,
        n_results_per_modality: int = 3
    ) -> Dict[str, Any]:
        """
        Multi-modal RAG query.
        
        Args:
            vector_store: Name of the vector store
            query: User query
            modalities: List of modalities to search
            n_results_per_modality: Number of results per modality
        
        Returns:
            Dictionary with answer and multi-modal sources
        """
        # Retrieve from multiple modalities
        multimodal_results = self.retrieve_multimodal(
            vector_store, query, modalities, n_results_per_modality
        )
        
        # Flatten results for generation
        all_results = []
        for modality, results in multimodal_results.items():
            all_results.extend(results)
        
        # Sort by similarity
        all_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Generate response
        answer = self.generate(query, all_results[:10])  # Top 10 overall
        
        return {
            "answer": answer,
            "sources_by_modality": multimodal_results,
            "total_sources": len(all_results)
        }


# ============================================================================
# Example 3: LangChain Integration
# ============================================================================

class OpenEmbedRetriever:
    """
    Custom LangChain retriever for OpenEmbed.
    """
    
    def __init__(self, client: OpenEmbedClient, vector_store: str, n_results: int = 5):
        self.client = client
        self.vector_store = vector_store
        self.n_results = n_results
    
    def get_relevant_documents(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve relevant documents for LangChain."""
        results = self.client.search_text(
            vector_store=self.vector_store,
            query=query,
            n_results=self.n_results
        )
        return results['results']


# ============================================================================
# Usage Examples
# ============================================================================

if __name__ == "__main__":
    # Initialize RAG system
    rag = SimpleRAG(openembed_url="http://localhost:8000")
    
    print("=" * 80)
    print("Example 1: Simple RAG Query")
    print("=" * 80)
    
    result = rag.query(
        vector_store="my_multimodal_store",
        query="What images do we have of sunsets?",
        n_results=5,
        filter_modality="image"
    )
    
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nUsed {result['num_sources']} sources")
    
    print("\n" + "=" * 80)
    print("Example 2: Multi-Modal RAG Query")
    print("=" * 80)
    
    multimodal_rag = MultiModalRAG(openembed_url="http://localhost:8000")
    
    result = multimodal_rag.query_multimodal(
        vector_store="my_multimodal_store",
        query="beautiful sunset over the ocean",
        modalities=['text', 'image', 'audio'],
        n_results_per_modality=2
    )
    
    print(f"\nTotal sources: {result['total_sources']}")
    for modality, sources in result['sources_by_modality'].items():
        print(f"  - {modality}: {len(sources)} results")
    
    print("\n" + "=" * 80)
    print("Example 3: Retrieve and Download Files")
    print("=" * 80)
    
    client = OpenEmbedClient("http://localhost:8000")
    
    # Search for images
    results = client.search_text(
        vector_store="my_multimodal_store",
        query="sunset",
        filter_modality="image",
        n_results=3
    )
    
    print(f"\nFound {len(results['results'])} images:")
    for result in results['results']:
        print(f"  - {result['metadata']['filename']}: {result['similarity']:.2%} similarity")
        
        # Download the file
        # client.download_file(
        #     modality=result['modality'],
        #     file_id=result['metadata']['file_id'],
        #     output_path=f"/tmp/{result['metadata']['filename']}"
        # )
        # print(f"    Downloaded to /tmp/{result['metadata']['filename']}")

