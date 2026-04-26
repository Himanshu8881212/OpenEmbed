"""
Main FastAPI application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os
from pathlib import Path

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logger import app_logger as logger
from app.core.rate_limiter import limiter
from app.api.routes import router
from app.services import perception_service, chroma_service, db_service, reranker_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting EMBEd...")
    settings.create_directories()
    os.makedirs("logs", exist_ok=True)

    if not settings.admin_api_key:
        logger.warning(
            "ADMIN_API_KEY is not set — running in DEV MODE. "
            "Admin endpoints (create/list/delete vaults) and any vault without its own "
            "key are UNAUTHENTICATED. Set ADMIN_API_KEY in .env before deploying."
        )

    # ChromaDB
    if not chroma_service.initialize():
        logger.error("ChromaDB init failed")
    else:
        logger.info("ChromaDB ready")

    # SQLite metadata layer (vaults + files)
    if not db_service.initialize():
        logger.error("SQLite metadata init failed")
    else:
        logger.info("SQLite metadata ready")
        # Backfill chroma-only vaults (created before SQLite tracking existed)
        try:
            chroma_names = [c["name"] for c in chroma_service.list_collections()]
            db_service.backfill_chroma_vaults(chroma_names)
        except Exception as e:
            logger.warning(f"Vault backfill skipped: {e}")

    # Perception Encoder (loads PE-Core + PE-AV; first run downloads ~6GB)
    if not perception_service.initialize():
        logger.error("Perception Encoder init failed")
    else:
        logger.info("Perception Encoder ready")

    # Cross-encoder reranker (BGE-reranker-v2-m3, ~568MB on first run)
    if not reranker_service.initialize():
        logger.warning("Reranker init failed — search will skip rerank step")
    else:
        logger.info("Reranker ready")

    logger.info("Application startup complete")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="EMBEd — Multi-Modal Embeddings",
    description="Self-hosted multi-modal embeddings powered by Meta Perception Encoder",
    version="3.0.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — explicit methods and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

app.include_router(router, prefix="/api")

# Ensure upload dir exists (files are served via auth-gated /api/files/...)
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

# Serve frontend
frontend_build_path = Path(__file__).parent.parent / "frontend" / "build"
if frontend_build_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_build_path / "static")), name="static")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path == "docs" or full_path == "openapi.json":
            return {"error": "Not found"}
        index = frontend_build_path / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"error": "Frontend not built"}
else:
    @app.get("/")
    async def root():
        return {
            "app": "EMBEd",
            "version": "3.0.0",
            "docs": "/docs",
            "api": "/api",
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
