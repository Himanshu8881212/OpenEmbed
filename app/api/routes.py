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


@router.get("/vector-stores/{name}/files")
async def get_vector_store_files(name: str):
    """Get all files/embeddings in a vector store."""
    try:
        if not chroma_service.collection_exists(name):
            raise HTTPException(
                status_code=404,
                detail=f"Vector store '{name}' not found"
            )

        # Get all items from the collection
        items = chroma_service.get_all_items(name)

        files = []
        for item_id, metadata in zip(items.get('ids', []), items.get('metadatas', [])):
            files.append({
                'id': item_id,
                'filename': metadata.get('filename', 'unknown'),
                'modality': metadata.get('modality', 'unknown'),
                'timestamp': metadata.get('timestamp', datetime.utcnow().isoformat()),
                'metadata': metadata
            })

        return files

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vector store files: {e}")
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


@router.post("/embed")
async def embed_file(
    file: UploadFile = File(...),
    modality: str = Form(...),
    vector_store: str = Form(...),
    create_new: bool = Form(False)
):
    """Upload file and generate embedding in one step."""
    try:
        # Create vector store if requested
        if create_new:
            if not chroma_service.collection_exists(vector_store):
                chroma_service.create_collection(
                    name=vector_store,
                    description=f"Vector store for {modality} embeddings"
                )

        # Check if vector store exists
        if not chroma_service.collection_exists(vector_store):
            raise HTTPException(
                status_code=404,
                detail=f"Vector store '{vector_store}' not found. Set create_new=true to create it."
            )

        # Save file
        modality_type = ModalityType(modality)
        result = await file_handler.save_upload_file(file, modality_type)
        if not result:
            raise HTTPException(
                status_code=400,
                detail="Failed to save file. Check file format and size."
            )

        file_id, file_path = result

        # Generate embedding
        embedding = None
        if modality == 'text':
            # Read text content
            content = file_path.read_text()
            embedding = languagebind_service.generate_text_embedding(content)
        elif modality == 'image':
            embedding = languagebind_service.generate_image_embedding(str(file_path))
        elif modality == 'video':
            embedding = languagebind_service.generate_video_embedding(str(file_path))
        elif modality == 'audio':
            embedding = languagebind_service.generate_audio_embedding(str(file_path))
        elif modality == 'depth':
            embedding = languagebind_service.generate_depth_embedding(str(file_path))
        elif modality == 'thermal':
            embedding = languagebind_service.generate_thermal_embedding(str(file_path))

        if embedding is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate embedding"
            )

        # Store embedding
        metadata = {
            'modality': modality,
            'filename': file.filename,
            'timestamp': datetime.utcnow().isoformat()
        }

        embedding_id = chroma_service.add_embedding(
            collection_name=vector_store,
            embedding=embedding,
            modality=modality,
            metadata=metadata
        )

        if not embedding_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to store embedding"
            )

        return {
            "success": True,
            "message": "File embedded successfully",
            "embedding_id": embedding_id,
            "vector_store": vector_store,
            "modality": modality,
            "filename": file.filename
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error embedding file: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
