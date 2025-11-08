"""
RAG (Retrieval-Augmented Generation) Example
============================================

Demonstrates how to use OpenEmbed in a RAG application.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from openembed import OpenEmbedClient


class SimpleRAG:
    """
    Simple RAG implementation using OpenEmbed.
    
    This demonstrates the basic pattern:
    1. Retrieve relevant context from OpenEmbed
    2. Build prompt with context
    3. Generate response (integrate with your LLM)
    """
    
    def __init__(self, openembed_url: str = "http://localhost:8000"):
        """Initialize RAG with OpenEmbed client."""
        self.client = OpenEmbedClient(openembed_url)
    
    def retrieve(
        self,
        vector_store: str,
        query: str,
        n_results: int = 5,
        modality_filter: str = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents from OpenEmbed.
        
        Args:
            vector_store: Name of the vector store
            query: User query
            n_results: Number of results to retrieve
            modality_filter: Optional modality filter
        
        Returns:
            List of retrieved documents with metadata
        """
        results = self.client.search(
            vector_store=vector_store,
            query=query,
            n_results=n_results,
            modality_filter=modality_filter
        )
        return results
    
    def build_context(self, results: List[Dict[str, Any]]) -> str:
        """
        Build context string from retrieved results.
        
        Args:
            results: Retrieved documents
        
        Returns:
            Formatted context string
        """
        context_parts = []
        for i, result in enumerate(results, 1):
            filename = result['metadata']['filename']
            modality = result['modality']
            similarity = result['similarity']
            
            context_parts.append(
                f"Source {i} ({modality}, {similarity:.1%} relevance):\n"
                f"File: {filename}\n"
                f"ID: {result['metadata']['file_id']}"
            )
        
        return "\n\n".join(context_parts)
    
    def query(
        self,
        vector_store: str,
        question: str,
        n_context: int = 5,
        modality_filter: str = None
    ) -> Dict[str, Any]:
        """
        Complete RAG query: retrieve + generate.
        
        Args:
            vector_store: Name of vector store
            question: User question
            n_context: Number of context documents
            modality_filter: Optional modality filter
        
        Returns:
            Dictionary with answer and sources
        """
        # Step 1: Retrieve relevant context
        results = self.retrieve(vector_store, question, n_context, modality_filter)
        
        # Step 2: Build context
        context = self.build_context(results)
        
        # Step 3: Build prompt
        prompt = f"""Based on the following context, answer the user's question.

Context:
{context}

Question: {question}

Answer:"""
        
        # Step 4: Generate response
        # In production, you would call your LLM here:
        # response = your_llm.generate(prompt)
        
        answer = f"[Generated answer would appear here]\n\nRetrieved {len(results)} relevant sources."
        
        return {
            "answer": answer,
            "sources": results,
            "num_sources": len(results),
            "prompt": prompt
        }


class MultiModalRAG(SimpleRAG):
    """
    Multi-modal RAG that retrieves from multiple modalities.
    """
    
    def retrieve_multimodal(
        self,
        vector_store: str,
        query: str,
        modalities: List[str] = None,
        n_per_modality: int = 2
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve from multiple modalities.
        
        Args:
            vector_store: Name of vector store
            query: User query
            modalities: List of modalities (default: text, image, audio)
            n_per_modality: Results per modality
        
        Returns:
            Dictionary mapping modality to results
        """
        if modalities is None:
            modalities = ['text', 'image', 'audio']
        
        results = {}
        for modality in modalities:
            try:
                modal_results = self.client.search(
                    vector_store=vector_store,
                    query=query,
                    n_results=n_per_modality,
                    modality_filter=modality
                )
                results[modality] = modal_results
            except Exception as e:
                print(f"Warning: Could not retrieve {modality}: {e}")
                results[modality] = []
        
        return results
    
    def query_multimodal(
        self,
        vector_store: str,
        question: str,
        modalities: List[str] = None,
        n_per_modality: int = 2
    ) -> Dict[str, Any]:
        """
        Multi-modal RAG query.
        
        Args:
            vector_store: Name of vector store
            question: User question
            modalities: List of modalities to search
            n_per_modality: Results per modality
        
        Returns:
            Dictionary with answer and multi-modal sources
        """
        # Retrieve from multiple modalities
        multimodal_results = self.retrieve_multimodal(
            vector_store, question, modalities, n_per_modality
        )
        
        # Flatten and sort by similarity
        all_results = []
        for modality, results in multimodal_results.items():
            all_results.extend(results)
        all_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Build context from top results
        context = self.build_context(all_results[:10])
        
        # Build prompt
        prompt = f"""Based on the following multi-modal context, answer the question.

Context (from text, images, audio, etc.):
{context}

Question: {question}

Answer:"""
        
        answer = f"[Generated answer using {len(all_results)} multi-modal sources]"
        
        return {
            "answer": answer,
            "sources_by_modality": multimodal_results,
            "total_sources": len(all_results),
            "prompt": prompt
        }


# ============================================================================
# Usage Examples
# ============================================================================

def example_simple_rag():
    """Example: Simple RAG query."""
    print("=" * 80)
    print("Example 1: Simple RAG Query")
    print("=" * 80)
    
    rag = SimpleRAG("http://localhost:8000")
    
    result = rag.query(
        vector_store="my_multimodal_store",
        question="What images do we have of sunsets?",
        n_context=5,
        modality_filter="image"
    )
    
    print(f"\nQuestion: {result['num_sources']} sources retrieved")
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nSources:")
    for i, source in enumerate(result['sources'], 1):
        print(f"  {i}. {source['metadata']['filename']} ({source['similarity']:.1%})")


def example_multimodal_rag():
    """Example: Multi-modal RAG query."""
    print("\n" + "=" * 80)
    print("Example 2: Multi-Modal RAG Query")
    print("=" * 80)
    
    rag = MultiModalRAG("http://localhost:8000")
    
    result = rag.query_multimodal(
        vector_store="my_multimodal_store",
        question="beautiful sunset over the ocean",
        modalities=['text', 'image', 'audio'],
        n_per_modality=2
    )
    
    print(f"\nTotal sources: {result['total_sources']}")
    print("\nSources by modality:")
    for modality, sources in result['sources_by_modality'].items():
        print(f"  {modality}: {len(sources)} results")
        for source in sources:
            print(f"    - {source['metadata']['filename']} ({source['similarity']:.1%})")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("OpenEmbed RAG Examples")
    print("=" * 80)
    print("\nMake sure OpenEmbed is running at http://localhost:8000\n")
    
    try:
        example_simple_rag()
        example_multimodal_rag()
        
        print("\n" + "=" * 80)
        print("RAG examples completed!")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure OpenEmbed is running and you have data in 'my_multimodal_store'")

