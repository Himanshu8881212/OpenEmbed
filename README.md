# EMBEd (OpenEmbed)

**Open-source multi-modal embedding service for RAG applications**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**EMBEd** is an open-source **Embedding-as-a-Service** platform that generates and manages embeddings for RAG (Retrieval Augmented Generation) applications. Create vector stores with text-only or multi-modal content, and let EMBEd handle all the embedding generation using Meta's ImageBind model.

## 🎯 What is EMBEd?

EMBEd is a **managed embedding service** that:
- 📦 **Creates vector stores** for your RAG applications
- 🤖 **Generates embeddings** using ImageBind (1024-dimensional)
- 💾 **Stores embeddings** in ChromaDB with persistence
- 🔍 **Provides search API** for retrieval in RAG workflows
- 🎨 **Supports 7 modalities** - Text, Image, Video, Audio, Depth, Thermal, IMU

**Perfect for:**
- ✅ Text-only RAG applications (like ChatGPT with your documents)
- ✅ Multi-modal RAG (search across text, images, videos, audio)
- ✅ Cross-modal search (find images using text descriptions)
- ✅ Content organization and similarity search

## ✨ Key Features

- 🎯 **Text-Only RAG** - Upload documents, get embeddings, use in your RAG app
- 🌈 **Multi-Modal RAG** - Mix text, images, videos, audio in same vector store
- 🔍 **Cross-Modal Search** - Find images using text, or text using audio
- 🚀 **Production Ready** - FastAPI backend + React frontend
- 💾 **Persistent Storage** - ChromaDB vector database
- 📦 **Python SDK** - Easy integration with your applications
- 🔌 **RESTful API** - Standard HTTP endpoints
- 🎨 **Modern UI** - Clean, professional interface
- 🐳 **Docker Ready** - One-command deployment

## 🚀 Quick Start

### 🐳 Docker Installation (Recommended)

**Prerequisites**: Docker Desktop ([Download](https://www.docker.com/products/docker-desktop))

```bash
# Clone repository
git clone https://github.com/Himanshu8881212/EMBEd.git
cd EMBEd

# Start with Docker Compose
docker-compose up -d

# Wait ~30 seconds for model to load, then access:
# http://localhost:8000
```

**That's it!** 🎉

**Useful Commands**:
```bash
# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild after code changes
docker-compose down -v
docker rmi embed-embed
docker-compose build
docker-compose up -d
```

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

**Recommended Workflow:**
1. Upload documents via Web UI (http://localhost:8000)
2. Query from Python using the SDK

```python
from openembed import OpenEmbedClient

# Initialize client
client = OpenEmbedClient("http://localhost:8000")

# Search your embedded documents (uploaded via Web UI)
results = client.search("my_store", "beautiful sunset images")
for r in results:
    print(f"{r['metadata']['filename']}: {r['similarity']:.1%}")
```

**Advanced:** Programmatic upload (if you prefer)
```python
# Upload single file
client.upload("my_store", "image.jpg", "image")

# Batch upload with auto-detection
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

## 🤔 How RAG Works with EMBEd

### **EMBEd as Embedding-as-a-Service**

EMBEd handles all embedding generation for you using **Meta's ImageBind** model:

```
Your RAG Application Flow:
┌─────────────────────────────────────────────────────────────┐
│ 1. INDEXING (One-time setup)                                │
│    Your Docs → EMBEd API → ImageBind → ChromaDB             │
│                           (1024-dim embeddings)              │
├─────────────────────────────────────────────────────────────┤
│ 2. RETRIEVAL (Every query)                                  │
│    User Query → EMBEd API → ImageBind → Search ChromaDB     │
│                            (query embedding)                 │
├─────────────────────────────────────────────────────────────┤
│ 3. GENERATION (Your LLM)                                    │
│    Retrieved Context + Query → OpenAI/Claude → Answer       │
└─────────────────────────────────────────────────────────────┘
```

### **Key Points:**

✅ **EMBEd generates all embeddings** - You don't need to manage ImageBind
✅ **Consistent embeddings** - Same model for indexing and retrieval
✅ **Works with any LLM** - Use OpenAI, Claude, Llama, etc. for generation
✅ **Text-only or multi-modal** - Your choice based on use case

### **Important: Model Consistency**

**EMBEd uses ImageBind for ALL embeddings:**
- **Embedding Model**: Meta ImageBind
- **Dimensions**: 1024
- **Normalization**: L2 normalized
- **Similarity**: Cosine similarity

**For RAG applications:**
- ✅ **Use EMBEd's search API** - EMBEd generates query embeddings automatically
- ✅ **Any LLM for generation** - OpenAI, Claude, Llama, etc.
- ❌ **Don't mix embedding models** - All embeddings must be from ImageBind

```python
# ✅ CORRECT: Use EMBEd's search API
results = embed_client.search("my_store", "user query")
# EMBEd generates ImageBind embedding for the query

# ❌ WRONG: Don't use different embedding models
openai_embedding = openai.Embedding.create(input="query")  # Different model!
# This won't work - OpenAI embeddings are incompatible with ImageBind
```

## 💡 Use Cases

### 1. Text-Only RAG (Like ChatGPT with Your Documents)

**Step 1: Upload Documents via Web UI**
1. Open http://localhost:8000
2. Create vector store "knowledge_base"
3. Upload your documents (company_policy.pdf, product_docs.pdf, meeting_notes.txt)
4. EMBEd automatically generates and stores embeddings ✨

**Step 2: Query in Your Application**
```python
from openembed import OpenEmbedClient
from openai import OpenAI

# Initialize clients
embed_client = OpenEmbedClient("http://localhost:8000")
openai_client = OpenAI()

# Retrieve relevant context from EMBEd
user_question = "What is our vacation policy?"
results = embed_client.search("knowledge_base", user_question, n_results=5)

# Build context from search results
context = "\n\n".join([
    f"Source: {r['metadata']['filename']}\n{r['metadata'].get('text_content', '')}"
    for r in results
])

# Generate answer with your LLM
response = openai_client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "Answer based on the provided context."},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {user_question}"}
    ]
)

print(response.choices[0].message.content)
```

**That's it!** Upload once via UI, query from any Python script. True Embedding-as-a-Service! 🎉

### 2. Multi-Modal RAG (Text + Images + Videos)

**Step 1: Upload Mixed Media via Web UI**
1. Open http://localhost:8000
2. Create vector store "product_catalog"
3. Upload product descriptions (.txt), images (.jpg), and demo videos (.mp4)
4. All content is embedded in unified space ✨

**Step 2: Cross-Modal Search**
```python
embed_client = OpenEmbedClient("http://localhost:8000")

# Search with text, get images/videos/text results!
results = embed_client.search(
    "product_catalog",
    "red running shoes with good cushioning",
    n_results=10
)

# Results include text, images, and videos ranked by relevance
for r in results:
    print(f"{r['modality']}: {r['metadata']['filename']} - {r['similarity']:.1%}")
```

### 3. Cross-Modal Search Examples

```python
# Find images using text description
images = embed_client.search(
    "product_catalog",
    "red sneakers",
    modality_filter="image"  # Only return images
)

# Find similar videos using text
videos = embed_client.search(
    "video_library",
    "sunset over ocean",
    modality_filter="video"
)

# Find related content using an image
results = embed_client.search_by_file(
    "content_library",
    "reference_image.jpg"
)
```

### 4. Content Organization & Semantic Search

**Step 1: Organize via Web UI**
1. Open http://localhost:8000
2. Create vector store "my_archive"
3. Drag & drop your entire document folder (PDFs, images, videos, audio)
4. EMBEd auto-detects modalities and embeds everything ✨

**Step 2: Semantic Search**
```python
embed_client = OpenEmbedClient("http://localhost:8000")

# Search across ALL your content (text, images, videos, audio)
results = embed_client.search("my_archive", "quarterly financial report")

# Works across modalities - finds matching PDFs, presentation slides, charts!
for r in results:
    print(f"Found in {r['metadata']['filename']} ({r['modality']})")
```

## 🎯 Why Use EMBEd?

### **Advantages:**

✅ **No Model Management** - We handle ImageBind for you (4.5GB model)
✅ **Multi-Modal Support** - 7 modalities in unified embedding space
✅ **Cross-Modal Search** - Find images with text, videos with audio
✅ **Open Source** - No vendor lock-in, self-hosted
✅ **Production Ready** - Docker deployment, persistent storage
✅ **Easy Integration** - Python SDK + REST API
✅ **Free** - No API costs, run on your infrastructure

### **When to Use EMBEd:**

**Perfect For:**
- 🎯 Multi-modal RAG applications
- 🎯 Cross-modal search (text → images, audio → videos)
- 🎯 Content organization across different media types
- 🎯 Research projects with mixed media
- 🎯 Self-hosted embedding service
- 🎯 Text-only RAG with ImageBind embeddings

**Consider Alternatives If:**
- ❌ You need OpenAI/Cohere embeddings specifically
- ❌ You want to use custom embedding models
- ❌ You only need text embeddings and want smaller models
- ❌ You prefer managed cloud services (Pinecone, Weaviate)

### **Comparison:**

| Feature | EMBEd | Pinecone | Weaviate | OpenAI |
|---------|-------|----------|----------|--------|
| **Multi-Modal** | ✅ 7 types | ❌ Text | ⚠️ Limited | ❌ Text |
| **Self-Hosted** | ✅ Yes | ❌ Cloud | ✅ Yes | ❌ Cloud |
| **Open Source** | ✅ MIT | ❌ No | ✅ BSD | ❌ No |
| **Cost** | ✅ Free | 💰 Paid | ✅ Free | 💰 Paid |
| **Cross-Modal** | ✅ Yes | ❌ No | ❌ No | ❌ No |

## 🏗️ Architecture

**Tech Stack:**
- **Backend**: FastAPI (Python 3.9+)
- **Frontend**: React 18 + TypeScript + Material-UI
- **Vector DB**: ChromaDB (persistent storage)
- **Embedding Model**: Meta ImageBind (1024-dimensional)
- **Analytics**: SQLite for usage tracking
- **Deployment**: Docker + Docker Compose

**Project Structure:**
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
