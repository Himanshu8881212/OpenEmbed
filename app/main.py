"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.core.logger import app_logger as logger
from app.api.routes import router
from app.services import languagebind_service, chroma_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Initialize services on startup and cleanup on shutdown.
    """
    # Startup
    logger.info("Starting openEmbed application...")

    # Create necessary directories
    settings.create_directories()
    os.makedirs("logs", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    os.makedirs("templates", exist_ok=True)

    # Initialize ChromaDB
    logger.info("Initializing ChromaDB...")
    if not chroma_service.initialize():
        logger.error("Failed to initialize ChromaDB")
    else:
        logger.info("ChromaDB initialized successfully")

    # Initialize LanguageBind
    logger.info("Initializing LanguageBind (this may take a while on first run)...")
    if not languagebind_service.initialize():
        logger.error("Failed to initialize LanguageBind")
    else:
        logger.info("LanguageBind initialized successfully")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title="openEmbed - Multi-Modal Embedding Application",
    description="A professional application for generating embeddings from multiple modalities using LanguageBind",
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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Include API routes
app.include_router(router, prefix="/api", tags=["API"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main application page."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": settings.app_name}
    )


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
