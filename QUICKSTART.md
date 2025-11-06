# Quick Start Guide

Get EMBEd up and running in 5 minutes!

## TL;DR

```bash
# Clone and enter directory
git clone <repository-url>
cd EMBEd

# Quick start (Linux/macOS)
./run.sh

# Quick start (Windows)
run.bat

# Access application
# Web UI: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Step-by-Step Quick Start

### 1. Prerequisites Check

Ensure you have:
- ✅ Python 3.10+ installed (`python3 --version`)
- ✅ 10GB+ free disk space
- ✅ Internet connection (for model download)

### 2. Installation

**Linux/macOS**:
```bash
./run.sh
```

**Windows**:
```cmd
run.bat
```

**Docker**:
```bash
docker-compose up -d
```

### 3. First Time Setup

On first run, the application will:
1. Create necessary directories
2. Download LanguageBind models (~10GB) - **this takes 10-30 minutes**
3. Initialize ChromaDB
4. Start the web server

**Be patient during first run!** Subsequent starts are much faster.

### 4. Access the Application

Once you see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Open your browser to: **http://localhost:8000**

## Your First Embedding

### Using the Web UI

1. **Create a Vector Store**:
   - Click "Create New Vector Store"
   - Name it "test_store"
   - Click "Create"

2. **Upload an Image**:
   - Select modality: "Image"
   - Choose an image file
   - Select vector store: "test_store"
   - Click "Generate & Store Embedding"

3. **Search**:
   - Select vector store: "test_store"
   - Query modality: "Text"
   - Enter: "describe your image"
   - Click "Search"

### Using the API

```bash
# 1. Create vector store
curl -X POST http://localhost:8000/api/vector-stores \
  -H "Content-Type: application/json" \
  -d '{"name": "test_store"}'

# 2. Upload file
FILE_ID=$(curl -X POST http://localhost:8000/api/upload \
  -F "file=@your-image.jpg" \
  -F "modality=image" | jq -r '.file_id')

# 3. Generate embedding
curl -X POST http://localhost:8000/api/embeddings \
  -H "Content-Type: application/json" \
  -d "{
    \"vector_store_name\": \"test_store\",
    \"operation\": \"use_existing\",
    \"modality\": \"image\",
    \"file_id\": \"$FILE_ID\"
  }"

# 4. Search
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store_name": "test_store",
    "query_modality": "text",
    "query_text": "your search query",
    "n_results": 5
  }'
```

## Testing All 6 Modalities

### 1. Text Embedding

```bash
curl -X POST http://localhost:8000/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store_name": "test_store",
    "operation": "use_existing",
    "modality": "text",
    "file_id": "text-1",
    "text_content": "A beautiful sunset over the ocean"
  }'
```

### 2. Image Embedding

```bash
# Upload image
curl -X POST http://localhost:8000/api/upload \
  -F "file=@image.jpg" \
  -F "modality=image"
# Then generate embedding (use returned file_id)
```

### 3. Video Embedding

```bash
# Upload video
curl -X POST http://localhost:8000/api/upload \
  -F "file=@video.mp4" \
  -F "modality=video"
# Then generate embedding
```

### 4. Audio Embedding

```bash
# Upload audio
curl -X POST http://localhost:8000/api/upload \
  -F "file=@audio.wav" \
  -F "modality=audio"
# Then generate embedding
```

### 5. Depth Map Embedding

```bash
# Upload depth map
curl -X POST http://localhost:8000/api/upload \
  -F "file=@depth.png" \
  -F "modality=depth"
# Then generate embedding
```

### 6. Thermal Image Embedding

```bash
# Upload thermal image
curl -X POST http://localhost:8000/api/upload \
  -F "file=@thermal.jpg" \
  -F "modality=thermal"
# Then generate embedding
```

## Common Issues & Quick Fixes

### Issue: "Models not loading"

**Fix**: First run downloads ~10GB of models. Wait 10-30 minutes.

Check progress in logs:
```bash
tail -f logs/app_*.log
```

### Issue: "CUDA out of memory"

**Fix**: Switch to CPU mode in `.env`:
```
DEVICE=cpu
```

### Issue: "Port 8000 already in use"

**Fix**: Change port in `.env`:
```
PORT=8080
```

Then access at: http://localhost:8080

### Issue: "Connection refused"

**Fix**: Ensure application is running:
```bash
# Check if running
curl http://localhost:8000/api/health

# If not, start it
./run.sh
```

## Performance Tips

### For Best Performance

1. **Use GPU**: Set in `.env`:
   ```
   DEVICE=cuda:0
   ```

2. **Increase Workers** (for production):
   ```
   WORKERS=4
   ```

3. **Pre-download Models**:
   Models are cached after first run. Keep `cache_dir/` folder.

### Expected Speed

| Operation | GPU | CPU |
|-----------|-----|-----|
| Image embedding | ~1s | ~5-10s |
| Video embedding | ~2s | ~15-30s |
| Audio embedding | ~1s | ~5-10s |
| Text embedding | <1s | ~1-2s |
| Search (1000 items) | <1s | <1s |

## What's Next?

### Learn More

- 📖 [Full Documentation](README.md)
- 🔧 [API Guide](API_GUIDE.md)
- 💻 [Installation Guide](INSTALL.md)

### Try Advanced Features

1. **Multi-modal Search**: Search images using text queries
2. **Cross-modal Retrieval**: Find videos similar to an image
3. **Batch Processing**: Upload multiple files at once
4. **Custom Metadata**: Add metadata to embeddings for filtering

### Example: Multi-Modal Search

```bash
# Add different modalities to same store
curl -X POST http://localhost:8000/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{"vector_store_name": "mixed", "operation": "use_existing", "modality": "text", "file_id": "t1", "text_content": "ocean waves"}'

# Upload and add image
# Upload and add video
# Upload and add audio

# Search across all with text
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store_name": "mixed",
    "query_modality": "text",
    "query_text": "peaceful beach scene",
    "n_results": 10
  }'
```

### Production Deployment

For production use:

1. **Use Docker**:
   ```bash
   docker-compose up -d
   ```

2. **Configure for Production**:
   - Set `DEBUG=False`
   - Change `SECRET_KEY`
   - Configure `CORS_ORIGINS`
   - Set up reverse proxy (nginx/Apache)
   - Enable HTTPS

3. **Monitor**:
   ```bash
   # View logs
   docker-compose logs -f

   # Check health
   curl http://localhost:8000/api/health
   ```

## Getting Help

### Check Status

```bash
# Application health
curl http://localhost:8000/api/health

# List vector stores
curl http://localhost:8000/api/vector-stores

# Check logs
tail -f logs/app_*.log
```

### Resources

- 📝 [GitHub Issues](https://github.com/your-repo/issues)
- 💬 [Discussions](https://github.com/your-repo/discussions)
- 📧 Email: support@example.com

## Quick Reference

### Supported File Formats

| Modality | Extensions |
|----------|-----------|
| Image | .jpg, .jpeg, .png, .bmp |
| Video | .mp4, .avi, .mov, .mkv |
| Audio | .wav, .mp3, .flac, .m4a |
| Depth | .png, .npy |
| Thermal | .jpg, .jpeg, .png |

### Default Ports

- Web UI: 8000
- API: 8000/api

### Default Directories

- Models: `cache_dir/`
- Uploads: `uploads/`
- Vector DB: `chroma_db/`
- Logs: `logs/`

---

**🎉 You're all set! Enjoy using EMBEd!**

For detailed documentation, see [README.md](README.md)
