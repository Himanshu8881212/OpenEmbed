# ============================================================================
# EMBEd - Multi-Modal Embedding Warehouse
# Multi-stage Dockerfile for Frontend + Backend
# ============================================================================

# ============================================================================
# Stage 1: Build Frontend (React TypeScript)
# ============================================================================
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy frontend source
COPY frontend/ ./

# Build frontend for production
RUN npm run build

# ============================================================================
# Stage 2: Backend Runtime (Python with PyTorch)
# ============================================================================
FROM python:3.9-slim AS backend

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies including decord build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    wget \
    curl \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libsndfile1 \
    cmake \
    libavcodec-dev \
    libavfilter-dev \
    libavformat-dev \
    libavutil-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.docker.txt requirements.txt

# Install Python dependencies
# Note: This will take a while on first build due to PyTorch
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Note: decord build fails with newer FFmpeg (API incompatibility)
# ImageBind will use moviepy as fallback for video processing
# Video embeddings will still work, just slightly slower

# Copy backend application code
COPY app/ ./app/
COPY pytest.ini .

# Copy frontend build from previous stage
COPY --from=frontend-builder /app/frontend/build ./frontend/build

# Create necessary directories
RUN mkdir -p \
    /app/uploads/text \
    /app/uploads/image \
    /app/uploads/video \
    /app/uploads/audio \
    /app/uploads/depth \
    /app/uploads/thermal \
    /app/uploads/imu \
    /app/chroma_db \
    /app/logs \
    /app/cache_dir \
    /app/model_cache \
    /app/.checkpoints

# Copy pre-downloaded ImageBind model (4.5GB) into container
# This eliminates the need to download the model on every container startup
# MUCH FASTER! Model loads in seconds instead of 5-10 minutes
COPY .checkpoints/imagebind_huge.pth /app/.checkpoints/imagebind_huge.pth

# Set permissions
RUN chmod -R 755 /app

# Expose ports
# 8000: Backend API
# 3000: Frontend (served by backend)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default command: Start backend server
# The backend will serve both API and frontend static files
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

