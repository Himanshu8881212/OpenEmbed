"""
Application configuration management using Pydantic Settings.
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    app_name: str = Field(default="EMBEd", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=4, env="WORKERS")

    # Model Configuration
    cache_dir: str = Field(default="./cache_dir", env="CACHE_DIR")
    model_cache_dir: str = Field(default="./model_cache", env="MODEL_CACHE_DIR")
    device: str = Field(default="auto", env="DEVICE")  # auto, cpu, cuda, cuda:0, mps

    # ChromaDB
    chroma_persist_dir: str = Field(default="./chroma_db", env="CHROMA_PERSIST_DIR")
    chroma_host: str = Field(default="localhost", env="CHROMA_HOST")
    chroma_port: int = Field(default=8001, env="CHROMA_PORT")

    # Upload Configuration
    max_file_size: int = Field(default=500_000_000, env="MAX_FILE_SIZE")  # 500MB
    upload_dir: str = Field(default="./uploads", env="UPLOAD_DIR")

    # Text formats - documents and plain text
    allowed_text_formats: List[str] = Field(
        default=[".txt", ".md", ".pdf", ".doc", ".docx", ".rtf", ".odt"],
        env="ALLOWED_TEXT_FORMATS"
    )

    # Video formats - common video containers
    allowed_video_formats: List[str] = Field(
        default=[".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".mpg", ".mpeg"],
        env="ALLOWED_VIDEO_FORMATS"
    )

    # Audio formats - common audio formats
    allowed_audio_formats: List[str] = Field(
        default=[".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".opus"],
        env="ALLOWED_AUDIO_FORMATS"
    )

    # Image formats - standard image formats
    allowed_image_formats: List[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp", ".svg"],
        env="ALLOWED_IMAGE_FORMATS"
    )

    # Depth map formats - depth data formats
    # .png is supported but requires explicit modality specification (defaults to image)
    allowed_depth_formats: List[str] = Field(
        default=[".png", ".npy", ".npz", ".exr", ".pfm"],
        env="ALLOWED_DEPTH_FORMATS"
    )

    # Thermal image formats - thermal imaging formats
    # .jpg/.jpeg/.png are supported but require explicit modality specification (default to image)
    allowed_thermal_formats: List[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".tiff", ".tif"],
        env="ALLOWED_THERMAL_FORMATS"
    )

    # Security
    secret_key: str = Field(default="change-me-in-production", env="SECRET_KEY")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"],
        env="CORS_ORIGINS"
    )

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=30, env="RATE_LIMIT_PER_MINUTE")

    class Config:
        env_file = ".env"
        case_sensitive = False

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            if field_name in ['allowed_text_formats', 'allowed_video_formats', 'allowed_audio_formats',
                             'allowed_image_formats', 'allowed_depth_formats',
                             'allowed_thermal_formats', 'cors_origins']:
                return [x.strip() for x in raw_val.split(',')]
            return raw_val

    def create_directories(self):
        """Create necessary directories if they don't exist."""
        directories = [
            self.cache_dir,
            self.model_cache_dir,
            self.chroma_persist_dir,
            self.upload_dir,
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)


# Global settings instance
settings = Settings()
