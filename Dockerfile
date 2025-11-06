# Multi-modal Embedding Application with LanguageBind
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies including video codec libraries
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    cmake \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    ffmpeg \
    libavcodec-dev \
    libavfilter-dev \
    libavformat-dev \
    libavutil-dev \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEVICE=cpu

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with OFFICIAL LanguageBind versions
# CRITICAL: PyTorch 1.13.1 + transformers 4.30.2 are REQUIRED for LanguageBind
RUN pip install --upgrade pip && \
    pip install torch==1.13.1 torchvision==0.14.1 torchaudio==0.13.1 --index-url https://download.pytorch.org/whl/cpu

# Install all other dependencies from requirements.txt
# This includes transformers==4.30.2, tokenizers==0.13.3, numpy==1.23.0 (official versions)
RUN pip install -r requirements.txt

# Build and install decord from source (required for ARM64/aarch64 compatibility)
# Decord is needed for video processing in LanguageBind
RUN git clone --recursive https://github.com/dmlc/decord /tmp/decord && \
    cd /tmp/decord && \
    git checkout v0.6.0 && \
    mkdir build && cd build && \
    cmake .. -DUSE_CUDA=OFF -DCMAKE_BUILD_TYPE=Release && \
    make -j$(nproc) && \
    cd ../python && \
    pip install -e . && \
    cd / && rm -rf /tmp/decord

# Copy application code (including app/languagebind and app/open_clip)
COPY . .

# Create necessary directories
RUN mkdir -p logs cache_dir model_cache chroma_db uploads static templates

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')"

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
