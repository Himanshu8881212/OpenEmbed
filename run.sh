#!/bin/bash

# EMBEd Application Startup Script

echo "========================================="
echo "EMBEd - Multi-Modal Embedding Application"
echo "========================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "Installing LanguageBind..."
    pip install git+https://github.com/PKU-YuanGroup/LanguageBind.git
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p logs cache_dir model_cache chroma_db uploads static templates

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env file with your configuration"
fi

# Start the application
echo "Starting EMBEd application..."
echo "Access the web interface at: http://localhost:8000"
echo "API documentation at: http://localhost:8000/docs"
echo "========================================="

python -m app.main
