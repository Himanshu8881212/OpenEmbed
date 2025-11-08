"""
OpenEmbed Python SDK
====================

A simple Python SDK for interacting with the OpenEmbed API.
Use this in your RAG applications to connect to OpenEmbed vector stores.

Installation:
    pip install requests

Usage:
    from openembed_sdk import OpenEmbedClient
    
    client = OpenEmbedClient("http://localhost:8000")
    results = client.search_text("my_store", "find similar images")
"""

import requests
from typing import List, Dict, Optional, Any
from pathlib import Path


class OpenEmbedClient:
    """Client for interacting with OpenEmbed API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the OpenEmbed client.
        
        Args:
            base_url: Base URL of the OpenEmbed API (default: http://localhost:8000)
        """
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api"
    
    def search_text(
        self,
        vector_store: str,
        query: str,
        n_results: int = 10,
        filter_modality: Optional[str] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Search for similar embeddings using a text query.
        
        This is the primary method for RAG applications.
        
        Args:
            vector_store: Name of the vector store to search
            query: Text query to search for
            n_results: Number of results to return (default: 10)
            filter_modality: Optional modality filter (text, image, video, audio, etc.)
            include_metadata: Whether to include metadata in results (default: True)
        
        Returns:
            Dictionary containing search results
        
        Example:
            >>> client = OpenEmbedClient()
            >>> results = client.search_text(
            ...     "my_store",
            ...     "beautiful sunset over the ocean",
            ...     n_results=5,
            ...     filter_modality="image"
            ... )
            >>> for result in results['results']:
            ...     print(f"File: {result['metadata']['filename']}, Similarity: {result['similarity']:.2%}")
        """
        url = f"{self.api_url}/search-by-id"
        payload = {
            "vector_store": vector_store,
            "text": query,
            "n_results": n_results,
            "include_metadata": include_metadata
        }
        if filter_modality:
            payload["filter_modality"] = filter_modality
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
    def search_file(
        self,
        vector_store: str,
        file_path: str,
        modality: Optional[str] = None,
        n_results: int = 10,
        filter_modality: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for similar embeddings using a file.
        
        Args:
            vector_store: Name of the vector store to search
            file_path: Path to the file to search with
            modality: Modality of the file (optional, auto-detected)
            n_results: Number of results to return (default: 10)
            filter_modality: Optional modality filter
        
        Returns:
            Dictionary containing search results
        
        Example:
            >>> results = client.search_file(
            ...     "my_store",
            ...     "/path/to/image.jpg",
            ...     n_results=5
            ... )
        """
        url = f"{self.api_url}/search"
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'vector_store': vector_store,
                'n_results': n_results
            }
            if modality:
                data['modality'] = modality
            if filter_modality:
                data['filter_modality'] = filter_modality
            
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            return response.json()
    
    def upload_file(
        self,
        vector_store: str,
        file_path: str,
        modality: str
    ) -> Dict[str, Any]:
        """
        Upload and embed a file.
        
        Args:
            vector_store: Name of the vector store
            file_path: Path to the file to upload
            modality: Modality (text, image, video, audio, depth, thermal, imu)
        
        Returns:
            Dictionary containing embedding information
        
        Example:
            >>> result = client.upload_file(
            ...     "my_store",
            ...     "/path/to/document.pdf",
            ...     "text"
            ... )
            >>> print(f"Uploaded: {result['filename']}, ID: {result['embedding_id']}")
        """
        url = f"{self.api_url}/embed"
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'vector_store': vector_store,
                'modality': modality
            }
            
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            return response.json()
    
    def upload_folder(
        self,
        vector_store: str,
        folder_path: str,
        recursive: bool = True
    ) -> Dict[str, Any]:
        """
        Upload all files from a folder with auto-detected modalities.
        
        Args:
            vector_store: Name of the vector store
            folder_path: Path to the folder
            recursive: Whether to include subdirectories (default: True)
        
        Returns:
            Dictionary containing upload results
        
        Example:
            >>> result = client.upload_folder(
            ...     "my_store",
            ...     "/path/to/folder"
            ... )
            >>> print(f"Uploaded {result['successful']} files")
        """
        url = f"{self.api_url}/embed-folder"
        
        folder = Path(folder_path)
        pattern = '**/*' if recursive else '*'
        files_to_upload = [f for f in folder.glob(pattern) if f.is_file()]
        
        files = [('files', open(f, 'rb')) for f in files_to_upload]
        data = {'vector_store': vector_store}
        
        try:
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            return response.json()
        finally:
            # Close all file handles
            for _, f in files:
                f.close()
    
    def list_stores(self) -> Dict[str, Any]:
        """
        List all vector stores.
        
        Returns:
            Dictionary containing list of stores
        
        Example:
            >>> stores = client.list_stores()
            >>> for store in stores['stores']:
            ...     print(f"{store['name']}: {store['count']} files, {store['size_bytes']} bytes")
        """
        url = f"{self.api_url}/vector-stores"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_store_files(self, vector_store: str) -> Dict[str, Any]:
        """
        Get all files in a vector store.
        
        Args:
            vector_store: Name of the vector store
        
        Returns:
            Dictionary containing list of files
        
        Example:
            >>> files = client.get_store_files("my_store")
            >>> for file in files['files']:
            ...     print(f"{file['filename']} ({file['modality']})")
        """
        url = f"{self.api_url}/vector-stores/{vector_store}/files"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def download_file(
        self,
        modality: str,
        file_id: str,
        output_path: str
    ) -> None:
        """
        Download a file from the vector store.
        
        Args:
            modality: Modality of the file
            file_id: File ID
            output_path: Path to save the downloaded file
        
        Example:
            >>> client.download_file(
            ...     "image",
            ...     "file-id-123",
            ...     "/path/to/save/image.jpg"
            ... )
        """
        url = f"{self.api_url}/uploads/{modality}/{file_id}"
        response = requests.get(url)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
    
    def create_store(
        self,
        name: str,
        description: Optional[str] = None,
        modality: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new vector store.
        
        Args:
            name: Name of the vector store
            description: Optional description
            modality: Optional modality (leave None for multi-modal stores)
        
        Returns:
            Dictionary containing store information
        
        Example:
            >>> store = client.create_store(
            ...     "my_new_store",
            ...     description="Store for product images"
            ... )
        """
        url = f"{self.api_url}/vector-stores"
        payload = {"name": name}
        if description:
            payload["description"] = description
        if modality:
            payload["modality"] = modality
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = OpenEmbedClient("http://localhost:8000")
    
    # Example 1: Search with text query
    print("=== Example 1: Text Search ===")
    results = client.search_text(
        vector_store="my_multimodal_store",
        query="beautiful sunset over the ocean",
        n_results=5,
        filter_modality="image"
    )
    
    print(f"Found {len(results['results'])} results:")
    for result in results['results']:
        print(f"  - {result['metadata']['filename']}: {result['similarity']:.2%} similarity")
    
    # Example 2: Upload a file
    print("\n=== Example 2: Upload File ===")
    # result = client.upload_file(
    #     vector_store="my_multimodal_store",
    #     file_path="/path/to/your/file.jpg",
    #     modality="image"
    # )
    # print(f"Uploaded: {result['filename']}")
    
    # Example 3: List all stores
    print("\n=== Example 3: List Stores ===")
    stores = client.list_stores()
    for store in stores['stores']:
        modalities = store['metadata'].get('modality_counts', {})
        print(f"  - {store['name']}: {store['count']} files, {list(modalities.keys())}")

