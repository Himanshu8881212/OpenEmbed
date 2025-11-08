"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.core.logger import app_logger as logger
from app.api.routes import router
from app.services import imagebind_service, chroma_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Initialize services on startup and cleanup on shutdown.
    """
    # Startup
    logger.info("Starting OpenEmbed application...")

    # Create necessary directories
    settings.create_directories()
    os.makedirs("logs", exist_ok=True)

    # Initialize ChromaDB
    logger.info("Initializing ChromaDB...")
    if not chroma_service.initialize():
        logger.error("Failed to initialize ChromaDB")
    else:
        logger.info("ChromaDB initialized successfully")

    # Initialize embedding service
    logger.info("Initializing embedding service (this may take a while on first run)...")
    if not imagebind_service.initialize():
        logger.error("Failed to initialize embedding service")
    else:
        logger.info("Embedding service initialized successfully")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title="OpenEmbed - Multi-Modal Embedding Application",
    description="A professional application for generating embeddings from multiple modalities including text, image, video, audio, depth, thermal, and IMU data",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api", tags=["API"])


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "message": "OpenEmbed API - Multi-Modal Embedding Application",
        "version": "1.0.0",
        "docs": "/docs",
        "api_prefix": "/api",
        "modalities": ["text", "image", "video", "audio", "depth", "thermal", "imu"]
    }


@app.get("/docs-redirect")
async def docs_redirect():
    """Redirect to API documentation."""
    return {"message": "Visit /docs for API documentation"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
