"""
Pydantic models for request/response validation.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime


class ModalityType(str, Enum):
    """Supported modality types."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DEPTH = "depth"
    THERMAL = "thermal"


class VectorStoreOperation(str, Enum):
    """Vector store operation types."""
    CREATE = "create"
    USE_EXISTING = "use_existing"


class VectorStoreCreate(BaseModel):
    """Request model for creating a new vector store."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @validator('name')
    def validate_name(cls, v):
        """Ensure vector store name is alphanumeric with underscores."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Name must contain only alphanumeric characters, hyphens, and underscores')
        return v


class VectorStoreInfo(BaseModel):
    """Response model for vector store information."""
    name: str
    description: Optional[str]
    count: int
    created_at: Optional[datetime]
    metadata: Optional[Dict[str, Any]]


class VectorStoreList(BaseModel):
    """Response model for listing vector stores."""
    stores: List[VectorStoreInfo]
    total: int


class EmbeddingRequest(BaseModel):
    """Request model for generating embeddings."""
    vector_store_name: str = Field(..., min_length=1)
    operation: VectorStoreOperation
    modality: ModalityType
    file_id: str = Field(..., description="Temporary file identifier from upload")
    text_content: Optional[str] = Field(None, description="Text content for text modality")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class EmbeddingResponse(BaseModel):
    """Response model for embedding generation."""
    success: bool
    message: str
    embedding_id: Optional[str] = None
    vector_store_name: str
    modality: ModalityType
    embedding_preview: Optional[List[float]] = Field(None, description="First 10 values of embedding for verification")
    embedding_shape: Optional[int] = Field(None, description="Dimension of the embedding vector")
    metadata: Optional[Dict[str, Any]] = None


class FileUploadResponse(BaseModel):
    """Response model for file upload."""
    success: bool
    file_id: str
    filename: str
    modality: ModalityType
    size: int
    message: str


class SearchRequest(BaseModel):
    """Request model for similarity search."""
    vector_store_name: str
    query_modality: ModalityType
    query_file_id: Optional[str] = None
    query_text: Optional[str] = None
    n_results: int = Field(default=10, ge=1, le=100)
    include_metadata: bool = Field(default=True)

    @validator('query_file_id', always=True)
    def validate_query(cls, v, values):
        """Ensure either file_id or text is provided."""
        if values.get('query_modality') == ModalityType.TEXT:
            if not values.get('query_text'):
                raise ValueError('query_text is required for text modality')
        else:
            if not v:
                raise ValueError('query_file_id is required for non-text modalities')
        return v


class SearchResult(BaseModel):
    """Single search result."""
    id: str
    distance: float
    metadata: Optional[Dict[str, Any]]


class SearchResponse(BaseModel):
    """Response model for similarity search."""
    success: bool
    results: List[SearchResult]
    query_modality: ModalityType
    total_results: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    models_loaded: bool
    vector_store_connected: bool
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
