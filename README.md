# EMBEd - Self-Hosted Multi-Modal Embeddings

**Turn your documents, images, videos, and audio into searchable embeddings. Locally.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## What is EMBEd?

EMBEd is a **self-hosted embedding service** that helps you build RAG (Retrieval Augmented Generation) applications. Upload your files through a web interface, search them from Python.

**Think Pinecone or Weaviate, but:**
- ✅ Self-hosted (runs on your machine)
- ✅ Multi-modal (text, images, videos, audio)
- ✅ Open source (MIT license)
- ✅ Free (no API costs)

---

## Quick Start

**Requirements:** Docker Desktop ([download](https://www.docker.com/products/docker-desktop))

```bash
# Clone and start
git clone https://github.com/Himanshu8881212/EMBEd.git
cd EMBEd
docker-compose up -d

# Wait 30 seconds for model to load, then open:
# http://localhost:8000
```

That's it! 🎉

---

## How It Works

### 1. Upload via Web UI
Open http://localhost:8000 and upload your files:
- 📄 Documents (.pdf, .txt, .docx)
- 🖼️ Images (.jpg, .png)
- 🎥 Videos (.mp4, .mov)
- 🔊 Audio (.mp3, .wav)

EMBEd automatically creates embeddings and stores them.

### 2. Query from Python

```python
from openembed import OpenEmbedClient

client = OpenEmbedClient("http://localhost:8000")
results = client.search("my_store", "your search query")

# Use results in your RAG app, chatbot, search engine, etc.
```

### 3. Use with Any LLM

```python
from openai import OpenAI

# Get context from EMBEd
results = client.search("my_docs", "What's our vacation policy?")
context = "\n".join([r['metadata'].get('text_content', '') for r in results])

# Send to LLM
openai = OpenAI()
response = openai.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "Answer using the context provided."},
        {"role": "user", "content": f"Context: {context}\n\nQuestion: What's our vacation policy?"}
    ]
)
```

**Works with:** OpenAI, Claude, Llama, Mistral, or any LLM.

---

## Features

| Feature | Description |
|---------|-------------|
| **7 Modalities** | Text, images, videos, audio, depth maps, thermal, IMU sensors |
| **Cross-Modal Search** | Find images using text, videos using audio, etc. |
| **Persistent Storage** | ChromaDB vector database with disk persistence |
| **Web Interface** | Upload and manage files visually |
| **Python SDK** | Simple client library for integration |
| **Docker Ready** | One-command deployment |
| **Self-Hosted** | Your data stays on your machine |

---

## Use Cases

### 📚 Document Q&A (RAG)
Upload your company docs, policies, manuals → Ask questions in natural language → Get accurate answers with sources.

### 🔍 Semantic Search
Search across all your content (documents, images, videos) using natural language. Finds meaning, not just keywords.

### 🎨 Multi-Modal Search
- Upload product images → Search "red running shoes"
- Upload videos → Search "sunset over ocean"
- Upload audio → Find similar music or spoken content

### 🤖 Chatbot Knowledge Base
Feed your chatbot with relevant context from your documents, making it knowledgeable about your specific domain.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Web UI (localhost:8000)                        │
│  Upload files → Auto-embed → Store in ChromaDB │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  Python SDK                                      │
│  Search embeddings → Get relevant results       │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  Your Application                                │
│  RAG, Chatbot, Search, Analysis, etc.           │
└─────────────────────────────────────────────────┘
```

**Embedding Model:** Meta's ImageBind (1024 dimensions, unified multi-modal space)
**Vector DB:** ChromaDB with persistent storage
**Backend:** FastAPI + Python
**Frontend:** React + TypeScript + Material-UI

---

## Manual Installation

<details>
<summary>Click to expand manual setup instructions</summary>

**Requirements:**
- Python 3.9+
- Node.js 16+
- 8GB+ RAM

```bash
# Backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..

# Run (Terminal 1: Backend)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run (Terminal 2: Frontend)
cd frontend && npm start
```

Access:
- Web UI: http://localhost:3000
- API Docs: http://localhost:8000/docs

</details>

---

## Configuration

Create `.env` file (optional):

```env
# Device (auto, cpu, cuda, mps)
DEVICE=auto

# Storage
CHROMA_PERSIST_DIR=./chroma_db
UPLOAD_DIR=./uploads

# Limits
MAX_FILE_SIZE=500000000  # 500MB
```

---

## API Documentation

Interactive API docs available at: **http://localhost:8000/docs**

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/vector-stores` | GET | List all vector stores |
| `/api/vector-stores` | POST | Create new vector store |
| `/api/embed` | POST | Upload and embed file |
| `/api/search-by-id` | POST | Search by text query |
| `/api/search` | POST | Search by file upload |

---

## Python SDK

**Install:**
```bash
pip install requests
```

**Usage:**
```python
from openembed import OpenEmbedClient

client = OpenEmbedClient("http://localhost:8000")

# Search
results = client.search("my_store", "query text")

# List stores
stores = client.list_stores()

# Get store info
info = client.get_store("my_store")

# Upload (advanced)
client.upload("my_store", "file.pdf", "text")
```

Full SDK docs: [sdk/python/README.md](sdk/python/README.md)

---

## Examples

Check out the [examples](examples/) folder for:
- **get_started.py** - Complete RAG application with LM Studio
- **test_get_started.py** - Automated testing

Run example:
```bash
cd examples
python get_started.py
```

---

## Performance

| Device | Speed | Recommended For |
|--------|-------|-----------------|
| GPU (CUDA) | 0.5-2s/file | Production |
| Apple MPS | 1-3s/file | Development/Production |
| CPU | 5-20s/file | Testing only |

**Model:** ImageBind (~4.5GB, auto-downloaded on first run)
**Storage:** ChromaDB with persistent disk storage

---

## Supported File Formats

| Modality | Formats |
|----------|---------|
| Text | .txt, .md, .pdf, .doc, .docx |
| Image | .jpg, .png, .gif, .webp |
| Video | .mp4, .avi, .mov, .mkv |
| Audio | .wav, .mp3, .flac, .m4a |

---

## Troubleshooting

<details>
<summary>Model download taking too long?</summary>

First run downloads ImageBind model (~4.5GB). This is normal. Subsequent starts are instant.
</details>

<details>
<summary>Out of memory error?</summary>

ImageBind requires ~6GB RAM. Try:
- Close other applications
- Use `DEVICE=cpu` in `.env`
- Increase Docker memory limit
</details>

<details>
<summary>Port 8000 already in use?</summary>

Change port in `docker-compose.yml`:
```yaml
ports:
  - "8080:8000"  # Use 8080 instead
```
</details>

---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## License

MIT License - see [LICENSE](LICENSE) file

---

## Acknowledgments

Built with:
- [ImageBind](https://github.com/facebookresearch/ImageBind) by Meta - Multi-modal embeddings
- [ChromaDB](https://github.com/chroma-core/chroma) - Vector database
- [FastAPI](https://github.com/tiangolo/fastapi) - Backend framework
- [React](https://github.com/facebook/react) + [Material-UI](https://github.com/mui/material-ui) - Frontend

---

## Support

- 🐛 **Issues:** [GitHub Issues](https://github.com/Himanshu8881212/EMBEd/issues)
- 💬 **Discussions:** [GitHub Discussions](https://github.com/Himanshu8881212/EMBEd/discussions)
- ⭐ **Star us on GitHub** if you find this useful!

---

**Made with ❤️ for the open-source community**
