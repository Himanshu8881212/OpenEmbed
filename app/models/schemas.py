"""
Pydantic schemas for request/response validation.
"""
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from enum import Enum
import os


class ModalityType(str, Enum):
    """Supported modalities for Gemini Embedding 2."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


# Supported MIME types for the multimodal pipeline
MIME_TYPES = {
    # Text
    ".txt": "text/plain",
    ".md": "text/plain",
    # Image
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    # Video
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    # Audio
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    # Document
    ".pdf": "application/pdf",
}

# Map extensions to modalities
EXTENSION_TO_MODALITY = {
    ".txt": ModalityType.TEXT, ".md": ModalityType.TEXT,
    ".jpg": ModalityType.IMAGE, ".jpeg": ModalityType.IMAGE,
    ".png": ModalityType.IMAGE, ".gif": ModalityType.IMAGE,
    ".webp": ModalityType.IMAGE,
    ".mp4": ModalityType.VIDEO, ".mov": ModalityType.VIDEO,
    ".webm": ModalityType.VIDEO, ".mkv": ModalityType.VIDEO,
    ".mp3": ModalityType.AUDIO, ".wav": ModalityType.AUDIO,
    ".flac": ModalityType.AUDIO, ".m4a": ModalityType.AUDIO,
    ".ogg": ModalityType.AUDIO, ".oga": ModalityType.AUDIO,
    ".pdf": ModalityType.DOCUMENT,
}


def detect_modality(filename: str) -> Tuple[Optional[ModalityType], Optional[str]]:
    """Detect modality and MIME type from filename extension."""
    ext = os.path.splitext(filename)[1].lower()
    return EXTENSION_TO_MODALITY.get(ext), MIME_TYPES.get(ext)


class VectorStoreCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class SearchResult(BaseModel):
    id: str
    similarity: float
    distance: float
    metadata: Dict[str, Any] = {}
    document: str = ""
