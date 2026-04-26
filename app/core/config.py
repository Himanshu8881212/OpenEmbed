"""
Application configuration.
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    app_name: str = Field(default="EMBEd", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")

    # Perception Encoder (Meta) — image+text via PE-Core, audio+video+text via PE-AV
    pe_core_model: str = Field(default="PE-Core-L14-336", env="PE_CORE_MODEL")
    pe_av_model: str = Field(default="facebook/pe-av-large", env="PE_AV_MODEL")
    embedding_dimensions: int = Field(default=1024, env="EMBEDDING_DIMENSIONS")

    # PE inference dtype: "float16" (default on MPS/CUDA), "bfloat16", or "float32".
    # Public API still returns float32 lists; this only controls on-device math.
    pe_dtype: str = Field(default="float16", env="PE_DTYPE")
    # If true, defer PE-AV (~8GB) until first audio/video request. Default eager.
    pe_av_lazy: bool = Field(default=False, env="PE_AV_LAZY")
    # If true, wrap PE-Core / PE-AV with torch.compile(mode="reduce-overhead").
    # Big speedup on hot paths but variable-shape inputs (audio duration, batch
    # size) will trigger recompiles. Off by default for predictable latency.
    pe_compile: bool = Field(default=False, env="PE_COMPILE")

    # ChromaDB
    chroma_persist_dir: str = Field(default="./chroma_db", env="CHROMA_PERSIST_DIR")

    # SQLite metadata layer (vaults + files)
    sqlite_path: str = Field(default="./embed.db", env="SQLITE_PATH")

    # Upload
    max_file_size: int = Field(default=100_000_000, env="MAX_FILE_SIZE")  # 100MB
    upload_dir: str = Field(default="./uploads", env="UPLOAD_DIR")

    # Authentication
    admin_api_key: str = Field(default="", env="ADMIN_API_KEY")

    # Chunking — PE-AV text uses ModernBERT (long context), only PE-Core image
    # text is CLIP-style 32-token. Larger chunks improve PE-AV recall and the
    # PE-Core image path silently truncates — net win for retrieval quality.
    chunk_size: int = Field(default=600, env="CHUNK_SIZE")  # ~150 ModernBERT tokens

    # Rate Limiting
    rate_limit_embed: str = Field(default="30/minute", env="RATE_LIMIT_EMBED")
    rate_limit_search: str = Field(default="60/minute", env="RATE_LIMIT_SEARCH")
    rate_limit_stores: str = Field(default="10/minute", env="RATE_LIMIT_STORES")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"],
        env="CORS_ORIGINS"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # tolerate stale env vars from older versions

    def create_directories(self):
        """Create necessary directories."""
        for d in [self.chroma_persist_dir, self.upload_dir]:
            os.makedirs(d, exist_ok=True)


settings = Settings()
