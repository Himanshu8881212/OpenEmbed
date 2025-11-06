# Multi-modal Embedding Application with LanguageBind
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies including video codec libraries
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEVICE=cpu

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with specific versions for LanguageBind
RUN pip install --upgrade pip && \
    pip install torch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu && \
    pip install "numpy<2.0.0" && \
    pip install peft==0.4.0 && \
    pip install einops opencv-python scipy scikit-learn SoundFile ftfy && \
    pip install -r requirements.txt

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
