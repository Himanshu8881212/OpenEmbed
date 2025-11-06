@echo off
REM EMBEd Application Startup Script for Windows

echo =========================================
echo EMBEd - Multi-Modal Embedding Application
echo =========================================

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if dependencies are installed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
    echo Installing LanguageBind...
    pip install git+https://github.com/PKU-YuanGroup/LanguageBind.git
)

REM Create necessary directories
echo Creating directories...
if not exist "logs\" mkdir logs
if not exist "cache_dir\" mkdir cache_dir
if not exist "model_cache\" mkdir model_cache
if not exist "chroma_db\" mkdir chroma_db
if not exist "uploads\" mkdir uploads
if not exist "static\" mkdir static
if not exist "templates\" mkdir templates

REM Check if .env file exists
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo Please edit .env file with your configuration
)

REM Start the application
echo Starting EMBEd application...
echo Access the web interface at: http://localhost:8000
echo API documentation at: http://localhost:8000/docs
echo =========================================

python -m app.main

pause
