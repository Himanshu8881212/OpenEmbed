"""
API routes for the EMBEd application.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional, List
from datetime import datetime

from app.models.schemas import (
    VectorStoreCreate,
    VectorStoreInfo,
    VectorStoreList,
    EmbeddingRequest,
    EmbeddingResponse,
    FileUploadResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    HealthResponse,
    ErrorResponse,
    ModalityType,
    VectorStoreOperation
)
from app.services import languagebind_service, chroma_service
from app.utils import file_handler
from app.core.logger import app_logger as logger

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        models_loaded=languagebind_service.is_initialized(),
        vector_store_connected=chroma_service.is_initialized(),
        timestamp=datetime.utcnow()
    )


@router.post("/vector-stores", response_model=VectorStoreInfo)
async def create_vector_store(request: VectorStoreCreate):
    """Create a new vector store (collection)."""
    try:
        # Check if collection already exists
        if chroma_service.collection_exists(request.name):
            raise HTTPException(
                status_code=400,
                detail=f"Vector store '{request.name}' already exists"
            )

        # Create collection
        success = chroma_service.create_collection(
            name=request.name,
            description=request.description,
            metadata=request.metadata
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to create vector store"
            )

        # Get collection info
        info = chroma_service.get_collection_info(request.name)
        if not info:
            raise HTTPException(
                status_code=500,
                detail="Created vector store but failed to retrieve info"
            )

        return VectorStoreInfo(
            name=info['name'],
            description=info['metadata'].get('description'),
            count=info['count'],
            created_at=datetime.fromisoformat(info['metadata'].get('created_at', datetime.utcnow().isoformat())),
            metadata=info['metadata']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vector store: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector-stores", response_model=VectorStoreList)
async def list_vector_stores():
    """List all vector stores."""
    try:
        collections = chroma_service.list_collections()

        stores = []
        for col in collections:
            stores.append(VectorStoreInfo(
                name=col['name'],
                description=col['metadata'].get('description'),
                count=col['count'],
                created_at=datetime.fromisoformat(col['metadata'].get('created_at', datetime.utcnow().isoformat())),
                metadata=col['metadata']
            ))

        return VectorStoreList(stores=stores, total=len(stores))

    except Exception as e:
        logger.error(f"Error listing vector stores: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vector-stores/{name}", response_model=VectorStoreInfo)
async def get_vector_store(name: str):
    """Get information about a specific vector store."""
    try:
        info = chroma_service.get_collection_info(name)
        if not info:
            raise HTTPException(
                status_code=404,
                detail=f"Vector store '{name}' not found"
            )

        return VectorStoreInfo(
            name=info['name'],
            description=info['metadata'].get('description'),
            count=info['count'],
            created_at=datetime.fromisoformat(info['metadata'].get('created_at', datetime.utcnow().isoformat())),
            metadata=info['metadata']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vector store: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/vector-stores/{name}")
async def delete_vector_store(name: str):
    """Delete a vector store."""
    try:
        success = chroma_service.delete_collection(name)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Vector store '{name}' not found"
            )

        return {"success": True, "message": f"Vector store '{name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting vector store: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    modality: ModalityType = Form(...)
):
    """Upload a file for embedding generation."""
    try:
        # Save file
        result = await file_handler.save_upload_file(file, modality)
        if not result:
            raise HTTPException(
                status_code=400,
                detail="Failed to save file. Check file format and size."
            )

        file_id, file_path = result

        return FileUploadResponse(
            success=True,
            file_id=file_id,
            filename=file.filename,
            modality=modality,
            size=file_path.stat().st_size,
            message="File uploaded successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embeddings", response_model=EmbeddingResponse)
async def generate_embedding(request: EmbeddingRequest):
    """Generate and store embedding for uploaded file or text."""
    try:
        # Handle vector store operation
        if request.operation == VectorStoreOperation.CREATE:
            # This should be handled by creating the store first
            raise HTTPException(
                status_code=400,
                detail="Please create vector store first using /vector-stores endpoint"
            )

        # Check if vector store exists
        if not chroma_service.collection_exists(request.vector_store_name):
            raise HTTPException(
                status_code=404,
                detail=f"Vector store '{request.vector_store_name}' not found"
            )

        # Generate embedding based on modality
        embedding = None
        file_path = None

        if request.modality == ModalityType.TEXT:
            if not request.text_content:
                raise HTTPException(
                    status_code=400,
                    detail="Text content required for text modality"
                )
            embedding = languagebind_service.generate_embedding(
                modality='text',
                text_content=request.text_content
            )
        else:
            # Get file path
            file_path = file_handler.get_file_path(request.file_id, request.modality)
            if not file_path:
                raise HTTPException(
                    status_code=404,
                    detail=f"File not found: {request.file_id}"
                )

            # Generate embedding
            embedding = languagebind_service.generate_embedding(
                modality=request.modality.value,
                file_path=file_path
            )

        if embedding is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate embedding"
            )

        # Store embedding in ChromaDB
        metadata = request.metadata or {}
        metadata['modality'] = request.modality.value
        if file_path:
            metadata['filename'] = file_path.name

        embedding_id = chroma_service.add_embedding(
            collection_name=request.vector_store_name,
            embedding=embedding,
            modality=request.modality.value,
            metadata=metadata,
            document=request.text_content if request.modality == ModalityType.TEXT else None
        )

        if not embedding_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to store embedding"
            )

        return EmbeddingResponse(
            success=True,
            message="Embedding generated and stored successfully",
            embedding_id=embedding_id,
            vector_store_name=request.vector_store_name,
            modality=request.modality,
            metadata=metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def search_similar(request: SearchRequest):
    """Search for similar embeddings in a vector store."""
    try:
        # Check if vector store exists
        if not chroma_service.collection_exists(request.vector_store_name):
            raise HTTPException(
                status_code=404,
                detail=f"Vector store '{request.vector_store_name}' not found"
            )

        # Generate query embedding
        query_embedding = None

        if request.query_modality == ModalityType.TEXT:
            if not request.query_text:
                raise HTTPException(
                    status_code=400,
                    detail="Query text required for text modality"
                )
            query_embedding = languagebind_service.generate_embedding(
                modality='text',
                text_content=request.query_text
            )
        else:
            # Get file path
            file_path = file_handler.get_file_path(request.query_file_id, request.query_modality)
            if not file_path:
                raise HTTPException(
                    status_code=404,
                    detail=f"Query file not found: {request.query_file_id}"
                )

            # Generate embedding
            query_embedding = languagebind_service.generate_embedding(
                modality=request.query_modality.value,
                file_path=file_path
            )

        if query_embedding is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate query embedding"
            )

        # Search in ChromaDB
        results = chroma_service.search(
            collection_name=request.vector_store_name,
            query_embedding=query_embedding,
            n_results=request.n_results,
            include_metadata=request.include_metadata
        )

        if results is None:
            raise HTTPException(
                status_code=500,
                detail="Search failed"
            )

        # Format results
        search_results = []
        for i, result_id in enumerate(results['ids'][0]):
            search_results.append(SearchResult(
                id=result_id,
                distance=float(results['distances'][0][i]),
                metadata=results['metadatas'][0][i] if request.include_metadata else None
            ))

        return SearchResponse(
            success=True,
            results=search_results,
            query_modality=request.query_modality,
            total_results=len(search_results)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching: {e}")
        raise HTTPException(status_code=500, detail=str(e))
