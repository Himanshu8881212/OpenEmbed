# OpenEmbed

**Production-ready multi-modal embedding warehouse with unified search across 7 modalities**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

OpenEmbed is a professional embedding warehouse that enables you to store, search, and retrieve embeddings across **text, images, videos, audio, depth maps, thermal images, and IMU data** in a unified embedding space using Meta's ImageBind.

## ✨ Key Features

- 🎯 **7 Modality Support** - Text, Image, Video, Audio, Depth, Thermal, IMU
- 🔍 **Cross-Modal Search** - Find images using text, or text using audio
- 🚀 **Production Ready** - FastAPI backend + React frontend
- 💾 **Persistent Storage** - ChromaDB vector database
- 📦 **Python SDK** - Easy integration with your applications
- 🔌 **RESTful API** - Standard HTTP endpoints
- 🎨 **Modern UI** - Clean, professional interface

## 🚀 Quick Start

### 🐳 Docker Installation (Recommended - Easiest!)

**Prerequisites**: Docker Desktop ([Download](https://www.docker.com/products/docker-desktop))

```bash
# Clone repository
git clone https://github.com/Himanshu8881212/EMBEd.git
cd EMBEd

# Start with one command!
docker-compose up -d

# Or use the interactive script
./start.sh        # Linux/Mac
start.bat         # Windows
```

**Access**: http://localhost:8000

**That's it!** 🎉 See [DOCKER_INSTALL.md](DOCKER_INSTALL.md) for detailed instructions.

---

### 💻 Manual Installation (Advanced)

**Prerequisites**:
- Python 3.9+
- Node.js 16+
- 8GB+ RAM
- (Optional) CUDA-capable GPU

```bash
# Clone repository
git clone https://github.com/Himanshu8881212/EMBEd.git
cd EMBEd

# Backend setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
cd ..
```

### Running (Manual)

```bash
# Terminal 1: Start backend
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend
cd frontend
npm start
```

**Access**:
- Web UI: http://localhost:3000
- API Docs: http://localhost:8000/docs
- SDK Examples: `sdk/examples/`

## 📦 Python SDK

```python
from openembed import OpenEmbedClient

# Initialize client
client = OpenEmbedClient("http://localhost:8000")

# Search with text
results = client.search("my_store", "beautiful sunset images")
for r in results:
    print(f"{r['metadata']['filename']}: {r['similarity']:.1%}")

# Upload files
client.upload("my_store", "image.jpg", "image")

# Batch upload
client.upload_batch("my_store", ["file1.jpg", "file2.mp3", "file3.txt"])
```

**Full Documentation**: [sdk/python/README.md](sdk/python/README.md)

## 🎯 Supported Modalities

| Modality | Extensions | Use Cases |
|----------|-----------|-----------|
| **Text** | .txt, .md, .json, .csv | Documents, articles, data |
| **Image** | .jpg, .png, .gif, .webp | Photos, graphics, diagrams |
| **Video** | .mp4, .avi, .mov, .mkv | Videos, animations |
| **Audio** | .wav, .mp3, .flac, .m4a | Music, speech, sounds |
| **Depth** | .png, .jpg, .tiff | Depth maps, 3D data |
| **Thermal** | .png, .jpg, .tiff | Thermal imaging |
| **IMU** | .csv, .json, .txt | Motion sensor data |

## 🔌 API Endpoints

### Search
```bash
# Text search
POST /api/search-by-id
{
  "vector_store": "my_store",
  "text": "sunset images",
  "n_results": 10
}

# File search
POST /api/search
FormData: file, vector_store, n_results
```

### Upload
```bash
# Single file
POST /api/embed
FormData: file, vector_store, modality

# Batch upload
POST /api/embed-folder
FormData: files[], vector_store
```

### Vector Stores
```bash
GET    /api/vector-stores           # List all stores
POST   /api/vector-stores           # Create store
GET    /api/vector-stores/{name}    # Get store info
DELETE /api/vector-stores/{name}    # Delete store
GET    /api/vector-stores/{name}/files  # List files
```

**Full API Documentation**: http://localhost:8000/docs

## 💡 Use Cases

### 1. RAG Applications
```python
# Retrieve relevant context for LLM
results = client.search("knowledge_base", user_question, n_results=5)
context = "\n".join([r['metadata']['filename'] for r in results])
# Feed context to your LLM
```

### 2. Multi-Modal Search
```python
# Find images using text description
images = client.search("product_catalog", "red sneakers", modality_filter="image")

# Find similar audio using reference audio
similar = client.search_by_file("music_library", "reference.mp3")
```

### 3. Content Organization
```python
# Upload entire folder with auto-detection
client.upload_batch("my_archive", list(Path("documents").glob("**/*")))

# Search across all modalities
results = client.search("my_archive", "quarterly report")
```

## 🏗️ Architecture

```
OpenEmbed/
├── app/                    # FastAPI backend
│   ├── api/               # API routes
│   ├── services/          # ImageBind + ChromaDB
│   ├── models/            # Pydantic schemas
│   └── utils/             # Utilities
├── frontend/              # React + TypeScript UI
│   └── src/pages/         # Dashboard, Upload, Search, Stores
├── sdk/                   # Official SDKs
│   ├── python/           # Python SDK
│   └── examples/         # Usage examples
└── demo_files/           # Sample files
```

## ⚙️ Configuration

Key environment variables (`.env` file):

```env
# Device: cpu, cuda, or mps (Apple Silicon)
DEVICE=mps

# Storage
CHROMA_PERSIST_DIR=./chroma_db
UPLOAD_DIR=./uploads

# Limits
MAX_FILE_SIZE=500000000  # 500MB
```

## 🚀 Performance

| Device | Speed | Recommended For |
|--------|-------|----------------|
| **GPU (CUDA)** | 0.5-2s per file | Production |
| **Apple MPS** | 1-3s per file | Development/Production |
| **CPU** | 5-20s per file | Testing only |

**Model**: ImageBind (~4.5GB, auto-downloaded on first run)
**Embedding Size**: 1024 dimensions
**Storage**: ChromaDB with persistent disk storage

## 📚 Documentation

- **Python SDK**: [sdk/python/README.md](sdk/python/README.md)
- **Examples**: [sdk/examples/](sdk/examples/)
- **API Docs**: http://localhost:8000/docs (when running)

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📄 License

MIT License - see LICENSE file

## 🙏 Acknowledgments

Built with:
- [ImageBind](https://github.com/facebookresearch/ImageBind) - Meta's multi-modal embeddings
- [ChromaDB](https://github.com/chroma-core/chroma) - Vector database
- [FastAPI](https://github.com/tiangolo/fastapi) - Modern Python web framework
- [React](https://github.com/facebook/react) + [Material-UI](https://github.com/mui/material-ui) - Frontend

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Himanshu8881212/EMBEd/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Himanshu8881212/EMBEd/discussions)

---

**OpenEmbed** - Unified multi-modal embeddings made simple
