"""
ChromaDB service for vector storage and retrieval.
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Optional, Any
import numpy as np
from loguru import logger
import uuid
from datetime import datetime

from app.core.config import settings


class ChromaService:
    """
    Service class for ChromaDB vector storage operations.
    Handles creation, storage, and retrieval of embeddings.
    """

    def __init__(self):
        """Initialize ChromaDB service."""
        self.client = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize ChromaDB client.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self._initialized:
            logger.info("ChromaDB already initialized")
            return True

        try:
            logger.info("Initializing ChromaDB service...")

            # Create persistent client
            self.client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            logger.info(f"ChromaDB initialized with persist directory: {settings.chroma_persist_dir}")
            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self._initialized = False
            return False

    def create_collection(
        self,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create a new collection (vector store).

        Args:
            name: Collection name
            description: Optional description
            metadata: Optional metadata

        Returns:
            bool: True if created successfully, False otherwise
        """
        if not self._initialized:
            logger.error("Service not initialized")
            return False

        try:
            # Prepare metadata
            collection_metadata = metadata or {}
            if description:
                collection_metadata['description'] = description
            collection_metadata['created_at'] = datetime.utcnow().isoformat()

            # Create collection
            self.client.create_collection(
                name=name,
                metadata=collection_metadata
            )

            logger.info(f"Created collection: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create collection {name}: {e}")
            return False

    def get_collection(self, name: str, silent: bool = False):
        """
        Get an existing collection.

        Args:
            name: Collection name
            silent: If True, don't log errors when collection doesn't exist (useful for existence checks)

        Returns:
            Collection object or None if not found
        """
        if not self._initialized:
            if not silent:
                logger.error("Service not initialized")
            return None

        try:
            collection = self.client.get_collection(name=name)
            return collection
        except Exception as e:
            # Only log error if not in silent mode (used for existence checks)
            if not silent:
                logger.error(f"Failed to get collection {name}: {e}")
            return None

    def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections.

        Returns:
            List of collection information dictionaries
        """
        if not self._initialized:
            logger.error("Service not initialized")
            return []

        try:
            collections = self.client.list_collections()
            collection_info = []

            for collection in collections:
                info = {
                    'name': collection.name,
                    'count': collection.count(),
                    'metadata': collection.metadata
                }
                collection_info.append(info)

            logger.info(f"Found {len(collection_info)} collections")
            return collection_info

        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection.

        Args:
            name: Collection name

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not self._initialized:
            logger.error("Service not initialized")
            return False

        try:
            self.client.delete_collection(name=name)
            logger.info(f"Deleted collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False

    def add_embedding(
        self,
        collection_name: str,
        embedding: np.ndarray,
        modality: str,
        metadata: Optional[Dict[str, Any]] = None,
        document: Optional[str] = None
    ) -> Optional[str]:
        """
        Add an embedding to a collection.

        Args:
            collection_name: Name of the collection
            embedding: Embedding vector
            modality: Type of modality
            metadata: Optional metadata
            document: Optional document/text content

        Returns:
            str: Embedding ID if successful, None otherwise
        """
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                logger.error(f"Collection {collection_name} not found")
                return None

            # Generate unique ID
            embedding_id = str(uuid.uuid4())

            # Prepare metadata
            meta = metadata or {}
            meta['modality'] = modality
            meta['added_at'] = datetime.utcnow().isoformat()

            # Ensure embedding is the right format
            if isinstance(embedding, np.ndarray):
                embedding_list = embedding.tolist()
            else:
                embedding_list = embedding

            # Add to collection
            collection.add(
                embeddings=[embedding_list],
                metadatas=[meta],
                documents=[document] if document else None,
                ids=[embedding_id]
            )

            logger.info(f"Added embedding {embedding_id} to collection {collection_name}")
            return embedding_id

        except Exception as e:
            logger.error(f"Failed to add embedding to {collection_name}: {e}")
            return None

    def search(
        self,
        collection_name: str,
        query_embedding: np.ndarray,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Search for similar embeddings in a collection.

        Args:
            collection_name: Name of the collection
            query_embedding: Query embedding vector
            n_results: Number of results to return
            where: Optional metadata filter
            include_metadata: Whether to include metadata in results

        Returns:
            Dictionary with search results or None if failed
        """
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                logger.error(f"Collection {collection_name} not found")
                return None

            # Ensure embedding is the right format
            if isinstance(query_embedding, np.ndarray):
                query_list = query_embedding.tolist()
            else:
                query_list = query_embedding

            # Prepare include list
            include = ['distances', 'metadatas'] if include_metadata else ['distances']

            # Query collection
            results = collection.query(
                query_embeddings=[query_list],
                n_results=n_results,
                where=where,
                include=include
            )

            logger.info(f"Search in {collection_name} returned {len(results['ids'][0])} results")
            return results

        except Exception as e:
            logger.error(f"Failed to search in {collection_name}: {e}")
            return None

    def get_collection_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a collection.

        Args:
            name: Collection name

        Returns:
            Dictionary with collection information or None if not found
        """
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            collection = self.get_collection(name)
            if collection is None:
                return None

            info = {
                'name': collection.name,
                'count': collection.count(),
                'metadata': collection.metadata
            }
            return info

        except Exception as e:
            logger.error(f"Failed to get info for collection {name}: {e}")
            return None

    def get_all_items(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Get all items from a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with all items or None if failed
        """
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            collection = self.get_collection(collection_name)
            if collection is None:
                logger.error(f"Collection {collection_name} not found")
                return None

            # Get all items
            results = collection.get(
                include=['metadatas']
            )

            return results

        except Exception as e:
            logger.error(f"Failed to get items from {collection_name}: {e}")
            return None

    def collection_exists(self, name: str) -> bool:
        """
        Check if a collection exists.

        Args:
            name: Collection name

        Returns:
            bool: True if exists, False otherwise
        """
        try:
            # Use silent=True to avoid logging errors when checking existence
            collection = self.get_collection(name, silent=True)
            return collection is not None
        except:
            return False

    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized


# Global service instance
chroma_service = ChromaService()
