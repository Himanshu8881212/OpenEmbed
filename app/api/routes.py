"""
API routes for the EMBEd application.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from typing import Optional, List
from datetime import datetime
from pathlib import Path

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
from app.services import imagebind_service, chroma_service
from app.utils import file_handler, modality_detector
from app.core.logger import app_logger as logger

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        models_loaded=imagebind_service.is_initialized(),
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
            # Calculate storage size for this store
            size_bytes = 0
            try:
                items = chroma_service.get_all_items(col['name'])
                if items and 'ids' in items and 'metadatas' in items:
                    file_ids = []
                    modalities = []
                    for metadata in items.get('metadatas', []):
                        if 'file_id' in metadata and 'modality' in metadata:
                            file_ids.append(metadata['file_id'])
                            modalities.append(metadata['modality'])

                    if file_ids:
                        size_bytes = file_handler.calculate_storage_size(file_ids, modalities)
            except Exception as e:
                logger.warning(f"Could not calculate size for store {col['name']}: {e}")

            stores.append(VectorStoreInfo(
                name=col['name'],
                description=col['metadata'].get('description'),
                count=col['count'],
                modality=col['metadata'].get('modality'),
                created_at=datetime.fromisoformat(col['metadata'].get('created_at', datetime.utcnow().isoformat())),
                metadata=col['metadata'],
                size_bytes=size_bytes
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
            modality=info['metadata'].get('modality'),
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

        # Group by file_id to avoid duplicates (since each file has multiple chunks)
        files_dict = {}
        for item_id, metadata in zip(items.get('ids', []), items.get('metadatas', [])):
            file_id = metadata.get('file_id', item_id)
            if file_id not in files_dict:
                files_dict[file_id] = {
                    'id': file_id,
                    'filename': metadata.get('filename', 'unknown'),
                    'modality': metadata.get('modality', 'unknown'),
                    'timestamp': metadata.get('timestamp', datetime.utcnow().isoformat()),
                    'metadata': metadata
                }

        return list(files_dict.values())

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
            embedding = imagebind_service.generate_text_embedding(content)
        elif modality == 'image':
            embedding = imagebind_service.generate_image_embedding(str(file_path))
        elif modality == 'video':
            embedding = imagebind_service.generate_video_embedding(str(file_path))
        elif modality == 'audio':
            embedding = imagebind_service.generate_audio_embedding(str(file_path))
        elif modality == 'depth':
            embedding = imagebind_service.generate_depth_embedding(str(file_path))
        elif modality == 'thermal':
            embedding = imagebind_service.generate_thermal_embedding(str(file_path))
        elif modality == 'imu':
            embedding = imagebind_service.generate_imu_embedding(str(file_path))

        if embedding is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate embedding for modality: {modality}"
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

        # Create embedding preview (first 10 values)
        embedding_preview = embedding[:10].tolist() if len(embedding) >= 10 else embedding.tolist()

        return {
            "success": True,
            "message": "File embedded successfully",
            "embedding_id": embedding_id,
            "vector_store": vector_store,
            "modality": modality,
            "filename": file.filename,
            "embedding_preview": embedding_preview,
            "embedding_shape": len(embedding)
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
            embedding = imagebind_service.generate_embedding(
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
            embedding = imagebind_service.generate_embedding(
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


@router.post("/search-by-id", response_model=SearchResponse)
async def search_similar(request: SearchRequest):
    """Search for similar embeddings in a vector store using existing embedding ID or text."""
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
            query_embedding = imagebind_service.generate_embedding(
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
            query_embedding = imagebind_service.generate_embedding(
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
            distance = float(results['distances'][0][i])
            # Convert distance to similarity (1 - normalized distance)
            # ChromaDB uses L2 distance, so we normalize it
            similarity = 1.0 / (1.0 + distance)

            metadata = results['metadatas'][0][i] if request.include_metadata else None
            modality = metadata.get('modality', 'unknown') if metadata else 'unknown'

            search_results.append(SearchResult(
                id=result_id,
                similarity=similarity,
                distance=distance,
                modality=modality,
                metadata=metadata,
                rank=i + 1
            ))

        return SearchResponse(
            success=True,
            results=search_results,
            query_modality=request.query_modality.value,
            vector_store=request.vector_store_name,
            n_results=len(search_results)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supported-formats")
async def get_supported_formats():
    """
    Get all supported file formats for each modality.

    Returns a dictionary mapping modality names to lists of supported file extensions.
    """
    try:
        formats = modality_detector.get_all_supported_formats()
        return {
            "success": True,
            "formats": formats,
            "total_formats": sum(len(exts) for exts in formats.values())
        }
    except Exception as e:
        logger.error(f"Error getting supported formats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed-auto")
async def embed_file_auto(
    file: UploadFile = File(...),
    vector_store: str = Form(...),
    create_new: bool = Form(False),
    modality: Optional[str] = Form(None)
):
    """
    Upload file and generate embedding with automatic modality detection.

    If modality is not provided, it will be automatically detected from the file extension.
    """
    try:
        # Auto-detect modality if not provided
        if modality is None:
            detected_modality = modality_detector.detect_modality(file.filename)
            if detected_modality is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not detect modality for file '{file.filename}'. "
                           f"Please specify modality explicitly or use a supported file format."
                )
            modality = detected_modality.value
            logger.info(f"Auto-detected modality '{modality}' for file '{file.filename}'")

        # Validate modality
        try:
            modality_type = ModalityType(modality)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid modality '{modality}'. Must be one of: {[m.value for m in ModalityType]}"
            )

        # Validate file extension matches modality
        if not modality_detector.validate_file_for_modality(file.filename, modality_type):
            supported_formats = modality_detector.get_supported_formats(modality_type)
            raise HTTPException(
                status_code=400,
                detail=f"File extension does not match modality '{modality}'. "
                       f"Supported formats: {supported_formats}"
            )

        # Create vector store if requested
        if create_new:
            if not chroma_service.collection_exists(vector_store):
                chroma_service.create_collection(
                    name=vector_store,
                    description=f"Vector store for multi-modal embeddings"
                )

        # Check if vector store exists
        if not chroma_service.collection_exists(vector_store):
            raise HTTPException(
                status_code=404,
                detail=f"Vector store '{vector_store}' not found. Set create_new=true to create it."
            )

        # Save file
        result = await file_handler.save_upload_file(file, modality_type)
        if not result:
            raise HTTPException(
                status_code=400,
                detail="Failed to save file. Check file format and size."
            )

        file_id, file_path = result

        # Generate embedding based on modality
        embedding = None
        if modality == 'text':
            # Read text content
            content = file_path.read_text()
            embedding = imagebind_service.generate_text_embedding(content)
        elif modality == 'image':
            embedding = imagebind_service.generate_image_embedding(str(file_path))
        elif modality == 'video':
            embedding = imagebind_service.generate_video_embedding(str(file_path))
        elif modality == 'audio':
            embedding = imagebind_service.generate_audio_embedding(str(file_path))
        elif modality == 'depth':
            embedding = imagebind_service.generate_depth_embedding(str(file_path))
        elif modality == 'thermal':
            embedding = imagebind_service.generate_thermal_embedding(str(file_path))

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

        # Return response with embedding preview
        return {
            "success": True,
            "embedding_id": embedding_id,
            "file_id": file_id,
            "filename": file.filename,
            "modality": modality,
            "auto_detected": modality is None,
            "vector_store": vector_store,
            "embedding_preview": embedding[:10].tolist() if len(embedding) >= 10 else embedding.tolist(),
            "embedding_shape": len(embedding),
            "message": f"Successfully generated {modality} embedding"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in embed_file_auto: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed-batch")
async def embed_batch_files(
    files: List[UploadFile] = File(...),
    vector_store: str = Form(...),
    create_new: bool = Form(False)
):
    """
    Upload multiple files and generate embeddings with automatic modality detection.

    Supports mixed modalities - e.g., upload .png, .pdf, .mp4 files together and
    each will be routed to the appropriate model automatically.
    """
    try:
        if not files:
            raise HTTPException(
                status_code=400,
                detail="No files provided"
            )

        # Create vector store if requested
        if create_new:
            if not chroma_service.collection_exists(vector_store):
                chroma_service.create_collection(
                    name=vector_store,
                    description=f"Vector store for multi-modal embeddings"
                )

        # Check if vector store exists
        if not chroma_service.collection_exists(vector_store):
            raise HTTPException(
                status_code=404,
                detail=f"Vector store '{vector_store}' not found. Set create_new=true to create it."
            )

        results = []
        errors = []

        for file in files:
            try:
                # Auto-detect modality
                detected_modality = modality_detector.detect_modality(file.filename)
                if detected_modality is None:
                    errors.append({
                        "filename": file.filename,
                        "error": "Could not detect modality - unsupported file format"
                    })
                    continue

                modality = detected_modality.value
                logger.info(f"Processing '{file.filename}' as {modality}")

                # Save file
                result = await file_handler.save_upload_file(file, detected_modality)
                if not result:
                    errors.append({
                        "filename": file.filename,
                        "error": "Failed to save file"
                    })
                    continue

                file_id, file_path = result

                # Generate embedding based on modality
                embedding = None
                if modality == 'text':
                    content = file_path.read_text()
                    embedding = imagebind_service.generate_text_embedding(content)
                elif modality == 'image':
                    embedding = imagebind_service.generate_image_embedding(str(file_path))
                elif modality == 'video':
                    embedding = imagebind_service.generate_video_embedding(str(file_path))
                elif modality == 'audio':
                    embedding = imagebind_service.generate_audio_embedding(str(file_path))
                elif modality == 'depth':
                    embedding = imagebind_service.generate_depth_embedding(str(file_path))
                elif modality == 'thermal':
                    embedding = imagebind_service.generate_thermal_embedding(str(file_path))

                if embedding is None:
                    errors.append({
                        "filename": file.filename,
                        "error": "Failed to generate embedding"
                    })
                    continue

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
                    errors.append({
                        "filename": file.filename,
                        "error": "Failed to store embedding"
                    })
                    continue

                # Success!
                results.append({
                    "success": True,
                    "embedding_id": embedding_id,
                    "file_id": file_id,
                    "filename": file.filename,
                    "modality": modality,
                    "embedding_preview": embedding[:10].tolist() if len(embedding) >= 10 else embedding.tolist(),
                    "embedding_shape": len(embedding)
                })

            except Exception as e:
                logger.error(f"Error processing file '{file.filename}': {e}")
                errors.append({
                    "filename": file.filename,
                    "error": str(e)
                })

        return {
            "success": len(results) > 0,
            "total_files": len(files),
            "successful": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
            "vector_store": vector_store
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in embed_batch_files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def search_vector_store(
    file: UploadFile = File(...),
    vector_store: str = Form(...),
    modality: Optional[str] = Form(None),
    n_results: int = Form(10),
    filter_modality: Optional[str] = Form(None)
):
    """
    Cross-modal search: Upload a query file (text/image/video/audio/depth/thermal)
    and find similar items in the vector store.

    This implements cross-modal retrieval using LanguageBind's shared embedding space.
    For example:
    - Upload an image to find similar images, videos, or text descriptions
    - Upload text to find relevant images, videos, or audio
    - Upload audio to find related videos or images

    Args:
        file: Query file (any supported modality)
        vector_store: Name of the vector store to search
        modality: Optional explicit modality (auto-detected if not provided)
        n_results: Number of results to return (default: 10)
        filter_modality: Optional filter to only return results of specific modality

    Returns:
        SearchResponse with ranked results and similarity scores
    """
    try:
        # Validate vector store exists
        if not chroma_service.collection_exists(vector_store):
            raise HTTPException(
                status_code=404,
                detail=f"Vector store '{vector_store}' not found"
            )

        # Auto-detect or validate modality
        if modality is None:
            detected_modality = modality_detector.detect_modality(file.filename)
            if detected_modality is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not detect modality for file '{file.filename}'. Please specify modality explicitly."
                )
            modality_type = detected_modality
            logger.info(f"Auto-detected modality '{modality_type.value}' for query file '{file.filename}'")
        else:
            try:
                modality_type = ModalityType(modality)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid modality: {modality}. Must be one of: text, image, video, audio, depth, thermal, imu"
                )

            # Validate file extension matches modality
            if not modality_detector.validate_file_for_modality(file.filename, modality_type):
                supported_formats = modality_detector.get_supported_formats(modality_type)
                raise HTTPException(
                    status_code=400,
                    detail=f"File extension does not match modality '{modality}'. Supported formats: {supported_formats}"
                )

        # Save uploaded query file temporarily
        result = await file_handler.save_upload_file(file, modality_type)
        if not result:
            raise HTTPException(
                status_code=400,
                detail="Failed to save query file"
            )

        file_id, file_path = result

        try:
            # Generate embedding for query file
            logger.info(f"Generating query embedding for {modality_type.value} file: {file.filename}")

            if modality_type == ModalityType.TEXT:
                # Read text content
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
                query_embedding = imagebind_service.generate_text_embedding(text_content)
            elif modality_type == ModalityType.IMAGE:
                query_embedding = imagebind_service.generate_image_embedding(str(file_path))
            elif modality_type == ModalityType.VIDEO:
                query_embedding = imagebind_service.generate_video_embedding(str(file_path))
            elif modality_type == ModalityType.AUDIO:
                query_embedding = imagebind_service.generate_audio_embedding(str(file_path))
            elif modality_type == ModalityType.DEPTH:
                query_embedding = imagebind_service.generate_depth_embedding(str(file_path))
            elif modality_type == ModalityType.THERMAL:
                query_embedding = imagebind_service.generate_thermal_embedding(str(file_path))
            elif modality_type == ModalityType.IMU:
                query_embedding = imagebind_service.generate_imu_embedding(str(file_path))
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported modality: {modality_type.value}"
                )

            logger.info(f"Generated query embedding with shape: {query_embedding.shape}")

            # Prepare metadata filter if specified
            where_filter = None
            if filter_modality:
                try:
                    filter_mod = ModalityType(filter_modality)
                    where_filter = {"modality": filter_mod.value}
                    logger.info(f"Filtering results to modality: {filter_mod.value}")
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid filter_modality: {filter_modality}"
                    )

            # Search in vector store
            search_results = chroma_service.search(
                collection_name=vector_store,
                query_embedding=query_embedding,
                n_results=n_results,
                where=where_filter,
                include_metadata=True
            )

            if search_results is None:
                raise HTTPException(
                    status_code=500,
                    detail="Search failed"
                )

            # Format results
            results = []
            ids = search_results['ids'][0]
            distances = search_results['distances'][0]
            metadatas = search_results.get('metadatas', [[]])[0]

            for i, (result_id, distance, metadata) in enumerate(zip(ids, distances, metadatas)):
                # Convert distance to similarity score (cosine similarity)
                # ChromaDB uses L2 distance by default, convert to similarity
                # similarity = 1 / (1 + distance)
                similarity = 1.0 - (distance / 2.0)  # Normalize to [0, 1]

                results.append(SearchResult(
                    id=result_id,
                    similarity=float(similarity),
                    distance=float(distance),
                    modality=metadata.get('modality', 'unknown'),
                    metadata=metadata,
                    rank=i + 1
                ))

            logger.info(f"Search completed: found {len(results)} results")

            return SearchResponse(
                success=True,
                query_modality=modality_type.value,
                vector_store=vector_store,
                n_results=len(results),
                results=results,
                filter_modality=filter_modality
            )

        finally:
            # Clean up temporary query file
            file_handler.delete_file(file_id, modality_type)
            logger.info(f"Cleaned up temporary query file: {file_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search_vector_store: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/uploads/{modality}/{file_id}")
async def serve_uploaded_file(modality: str, file_id: str):
    """Serve uploaded files for viewing/downloading."""
    try:
        # Convert modality string to ModalityType
        try:
            modality_type = ModalityType(modality.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid modality: {modality}"
            )

        # Get file path
        file_path = file_handler.get_file_path(file_id, modality_type)

        if not file_path or not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {file_id}"
            )

        # Determine media type based on file extension
        media_types = {
            '.txt': 'text/plain',
            '.json': 'application/json',
            '.md': 'text/markdown',
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.bmp': 'image/bmp',
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.mkv': 'video/x-matroska',
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.flac': 'audio/flac',
            '.m4a': 'audio/mp4',
        }

        file_ext = file_path.suffix.lower()
        media_type = media_types.get(file_ext, 'application/octet-stream')

        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=file_path.name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file: {e}")
        raise HTTPException(status_code=500, detail=str(e))
