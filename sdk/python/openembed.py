"""
OpenEmbed Python SDK
====================

Official Python client for OpenEmbed - Multi-Modal Embedding Warehouse

Installation:
    pip install requests

Basic Usage:
    >>> from openembed import OpenEmbedClient
    >>> client = OpenEmbedClient("http://localhost:8000")
    >>> results = client.search("my_store", "find similar images")
    >>> print(f"Found {len(results)} results")

Author: OpenEmbed Team
License: MIT
"""

import requests
from typing import List, Dict, Optional, Any, Union
from pathlib import Path
import json


class OpenEmbedError(Exception):
    """Base exception for OpenEmbed SDK."""
    pass


class OpenEmbedClient:
    """
    Official Python client for OpenEmbed API.
    
    Provides methods for:
    - Searching embeddings (text and file-based)
    - Uploading and embedding files
    - Managing vector stores
    - Downloading files
    
    Example:
        >>> client = OpenEmbedClient("http://localhost:8000")
        >>> results = client.search("my_store", "sunset images")
        >>> for r in results:
        ...     print(f"{r['filename']}: {r['similarity']:.1%}")
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        """
        Initialize OpenEmbed client.
        
        Args:
            base_url: Base URL of OpenEmbed API (default: http://localhost:8000)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api"
        self.timeout = timeout
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with error handling."""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        kwargs.setdefault('timeout', self.timeout)
        
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise OpenEmbedError(f"API request failed: {e}")
    
    # ========================================================================
    # Search Methods
    # ========================================================================
    
    def search(
        self,
        vector_store: str,
        query: Union[str, Path],
        n_results: int = 10,
        modality_filter: Optional[str] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings (unified interface).
        
        Automatically detects if query is text or file path.
        
        Args:
            vector_store: Name of vector store to search
            query: Text query or path to file
            n_results: Number of results to return (default: 10)
            modality_filter: Filter by modality (text, image, audio, etc.)
            include_metadata: Include metadata in results (default: True)
        
        Returns:
            List of search results with similarity scores
        
        Example:
            >>> # Text search
            >>> results = client.search("my_store", "sunset images")
            >>> 
            >>> # File search
            >>> results = client.search("my_store", Path("image.jpg"))
        """
        # Check if query is a file path
        if isinstance(query, (str, Path)):
            path = Path(query)
            if path.exists() and path.is_file():
                return self.search_by_file(vector_store, path, n_results, modality_filter)
        
        # Otherwise treat as text query
        return self.search_by_text(vector_store, str(query), n_results, modality_filter, include_metadata)
    
    def search_by_text(
        self,
        vector_store: str,
        text: str,
        n_results: int = 10,
        modality_filter: Optional[str] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search using text query.

        Args:
            vector_store: Name of vector store
            text: Text query
            n_results: Number of results (default: 10)
            modality_filter: Filter by modality
            include_metadata: Include metadata (default: True)

        Returns:
            List of search results
        """
        payload = {
            "vector_store_name": vector_store,
            "query_modality": "text",
            "query_text": text,
            "n_results": n_results,
            "include_metadata": include_metadata
        }
        if modality_filter:
            payload["filter_modality"] = modality_filter

        response = self._request("POST", "/search-by-id", json=payload)
        return response.get('results', [])
    
    def search_by_file(
        self,
        vector_store: str,
        file_path: Union[str, Path],
        n_results: int = 10,
        modality_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using uploaded file.
        
        Args:
            vector_store: Name of vector store
            file_path: Path to file
            n_results: Number of results (default: 10)
            modality_filter: Filter by modality
        
        Returns:
            List of search results
        """
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {'vector_store': vector_store, 'n_results': n_results}
            if modality_filter:
                data['filter_modality'] = modality_filter
            
            response = self._request("POST", "search", files=files, data=data)
            return response.get('results', [])
    
    # ========================================================================
    # Upload Methods
    # ========================================================================
    
    def upload(
        self,
        vector_store: str,
        file_path: Union[str, Path],
        modality: str
    ) -> Dict[str, Any]:
        """
        Upload and embed a file.
        
        Args:
            vector_store: Name of vector store
            file_path: Path to file
            modality: Modality (text, image, video, audio, depth, thermal, imu)
        
        Returns:
            Upload result with embedding_id and file_id
        
        Example:
            >>> result = client.upload("my_store", "image.jpg", "image")
            >>> print(f"Uploaded: {result['filename']}")
        """
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {'vector_store': vector_store, 'modality': modality}
            return self._request("POST", "embed", files=files, data=data)
    
    def upload_batch(
        self,
        vector_store: str,
        file_paths: List[Union[str, Path]]
    ) -> Dict[str, Any]:
        """
        Upload multiple files with auto-detected modalities.
        
        Args:
            vector_store: Name of vector store
            file_paths: List of file paths
        
        Returns:
            Batch upload results
        
        Example:
            >>> files = ["image1.jpg", "audio.mp3", "text.txt"]
            >>> result = client.upload_batch("my_store", files)
            >>> print(f"Uploaded {result['successful']} files")
        """
        files = [('files', open(f, 'rb')) for f in file_paths]
        data = {'vector_store': vector_store}
        
        try:
            return self._request("POST", "embed-folder", files=files, data=data)
        finally:
            for _, f in files:
                f.close()
    
    # ========================================================================
    # Vector Store Methods
    # ========================================================================
    
    def list_stores(self) -> List[Dict[str, Any]]:
        """
        List all vector stores.
        
        Returns:
            List of vector stores with metadata
        
        Example:
            >>> stores = client.list_stores()
            >>> for store in stores:
            ...     print(f"{store['name']}: {store['count']} files")
        """
        response = self._request("GET", "vector-stores")
        return response.get('stores', [])
    
    def create_store(
        self,
        name: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new vector store.
        
        Args:
            name: Store name
            description: Optional description
        
        Returns:
            Created store information
        """
        payload = {"name": name}
        if description:
            payload["description"] = description
        return self._request("POST", "vector-stores", json=payload)
    
    def get_store(self, name: str) -> Dict[str, Any]:
        """Get vector store information."""
        return self._request("GET", f"vector-stores/{name}")
    
    def delete_store(self, name: str) -> Dict[str, Any]:
        """Delete a vector store."""
        return self._request("DELETE", f"vector-stores/{name}")
    
    def get_files(self, vector_store: str) -> List[Dict[str, Any]]:
        """
        Get all files in a vector store.
        
        Args:
            vector_store: Name of vector store
        
        Returns:
            List of files with metadata
        """
        response = self._request("GET", f"vector-stores/{vector_store}/files")
        return response.get('files', [])
    
    # ========================================================================
    # File Methods
    # ========================================================================
    
    def download(
        self,
        modality: str,
        file_id: str,
        output_path: Union[str, Path]
    ) -> None:
        """
        Download a file.
        
        Args:
            modality: File modality
            file_id: File ID
            output_path: Path to save file
        
        Example:
            >>> client.download("image", "file-123", "output.jpg")
        """
        url = f"{self.api_url}/uploads/{modality}/{file_id}"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
    
    def health(self) -> Dict[str, Any]:
        """Check API health status."""
        return self._request("GET", "health")


__all__ = ['OpenEmbedClient', 'OpenEmbedError']

