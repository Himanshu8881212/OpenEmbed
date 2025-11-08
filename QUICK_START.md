# 🚀 EMBEd - Quick Start Guide

## Installation Methods

### Method 1: Docker (Recommended - 3 Steps!)

**Prerequisites**: Docker Desktop ([Download](https://www.docker.com/products/docker-desktop))

```bash
# 1. Clone
git clone https://github.com/Himanshu8881212/EMBEd.git
cd EMBEd

# 2. Start
docker-compose up -d

# 3. Access
# Open browser: http://localhost:8000
```

**Done!** 🎉

---

### Method 2: Interactive Script

**Linux/Mac**:
```bash
./start.sh
# Choose option 1: Build and start
```

**Windows**:
```cmd
start.bat
REM Choose option 1: Build and start
```

---

### Method 3: Manual Installation

```bash
# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run build
cd ..

# Run
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## First Time Setup

### What Happens on First Run?

1. **Docker builds the image** (~10-15 minutes)
   - Installs Python dependencies
   - Builds React frontend
   - Sets up environment

2. **Application downloads models** (~2-3 minutes)
   - Downloads ImageBind model (~2GB)
   - Initializes ChromaDB
   - Creates SQLite database

3. **Application starts** 🎉
   - Backend API: http://localhost:8000/api
   - Frontend UI: http://localhost:8000
   - API Docs: http://localhost:8000/docs

---

## Common Commands

### Docker Commands

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f

# Restart
docker-compose restart

# Rebuild
docker-compose build --no-cache
docker-compose up -d

# Check status
docker-compose ps
```

### Using Scripts

**Linux/Mac** (`./start.sh`):
- Option 1: Build and start
- Option 2: Start
- Option 3: Stop
- Option 4: Restart
- Option 5: View logs
- Option 6: Check status
- Option 7: Clean up
- Option 8: Exit

**Windows** (`start.bat`): Same options

---

## Accessing the Application

### Frontend (Web UI)
- **URL**: http://localhost:8000
- **Features**:
  - Upload files (text, images, videos, audio, etc.)
  - Create vector stores
  - Search across modalities
  - View analytics

### API Documentation
- **URL**: http://localhost:8000/docs
- **Interactive**: Try API endpoints directly
- **OpenAPI**: Full API specification

### Health Check
- **URL**: http://localhost:8000/api/health
- **Response**:
  ```json
  {
    "status": "healthy",
    "version": "1.0.0",
    "models_loaded": true,
    "vector_store_connected": true
  }
  ```

---

## Usage Examples

### 1. Create a Vector Store

**Via UI**:
1. Go to http://localhost:8000
2. Click "Create Vector Store"
3. Enter name and description
4. Click "Create"

**Via API**:
```bash
curl -X POST http://localhost:8000/api/vector-stores \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_store",
    "description": "My first vector store"
  }'
```

### 2. Upload a File

**Via UI**:
1. Select vector store
2. Click "Upload Files"
3. Drag & drop or select files
4. Click "Upload"

**Via API**:
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@image.jpg" \
  -F "vector_store=my_store" \
  -F "modality=image"
```

### 3. Search

**Via UI**:
1. Go to "Search" tab
2. Select vector store
3. Enter text query or upload file
4. View results

**Via API (Text Search)**:
```bash
curl -X POST http://localhost:8000/api/search-by-id \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store_name": "my_store",
    "query_modality": "text",
    "query_text": "sunset over ocean",
    "n_results": 10
  }'
```

**Via API (File Search)**:
```bash
curl -X POST http://localhost:8000/api/search \
  -F "file=@query.jpg" \
  -F "vector_store=my_store" \
  -F "n_results=10"
```

---

## Troubleshooting

### Application Won't Start

```bash
# Check Docker is running
docker ps

# Check logs
docker-compose logs

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Port 8000 Already in Use

Edit `docker-compose.yml`:
```yaml
ports:
  - "8080:8000"  # Change to any available port
```

### Out of Memory

Increase Docker memory:
- Docker Desktop → Settings → Resources → Memory
- Set to at least 8GB

### Slow First Startup

This is normal! First run downloads ~2GB of models.

Check progress:
```bash
docker-compose logs -f | grep "Loading"
```

---

## Data Persistence

All data is stored in Docker volumes:

- **Vector Database**: `embed-chroma`
- **Uploaded Files**: `embed-uploads`
- **Analytics**: `embed-analytics`
- **Model Cache**: `embed-models`
- **Logs**: `embed-logs`

### Backup Data

```bash
docker run --rm -v embed-chroma:/data -v $(pwd):/backup alpine tar czf /backup/backup.tar.gz /data
```

### Restore Data

```bash
docker run --rm -v embed-chroma:/data -v $(pwd):/backup alpine tar xzf /backup/backup.tar.gz -C /
```

---

## Next Steps

1. **Read Full Documentation**: [README.md](README.md)
2. **Docker Details**: [DOCKER_INSTALL.md](DOCKER_INSTALL.md)
3. **API Reference**: http://localhost:8000/docs
4. **Python SDK**: See `sdk/python/` directory

---

## Support

- **Issues**: https://github.com/Himanshu8881212/EMBEd/issues
- **Documentation**: See README.md
- **API Docs**: http://localhost:8000/docs

---

**Ready to embed! 🚀**

