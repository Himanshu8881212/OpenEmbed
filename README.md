# EMBEd - Self-Hosted Multi-Modal Embeddings

**Turn your documents, images, videos, and audio into searchable embeddings. Runs locally.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Like Pinecone or Weaviate, but self-hosted and multi-modal. Built on Meta's ImageBind.

---

## 🚀 Getting Started

### Step 1: Run the Docker Container

```bash
# Clone the repository
git clone https://github.com/Himanshu8881212/EMBEd.git
cd EMBEd

# Start EMBEd service
docker-compose up -d

# Wait ~30 seconds for model to load
# ✅ Service running at http://localhost:8000
```

### Step 2: Upload Your Files

Open **http://localhost:8000** in your browser:

1. Create a vector store named **"company_docs"**
2. Drag & drop your files (company_policy.pdf, employee_handbook.pdf, etc.)
3. EMBEd automatically generates embeddings ✨

### Step 3: Query from Python

```python
# Install SDK
pip install requests

# Copy the SDK file to your project
# (from sdk/python/openembed.py)
from openembed import OpenEmbedClient

# Connect to EMBEd service
client = OpenEmbedClient("http://localhost:8000")

# Search your documents (use the store name from Step 2)
results = client.search(
    vector_store="company_docs",  # Same name as Step 2
    query="What is our vacation policy?",
    n_results=5
)

# Display results
for result in results:
    print(f"📄 {result['metadata']['filename']}")
    print(f"   Match: {result['similarity']:.1%}")
    print()
```

**Output:**
```
📄 company_policy.pdf
   Match: 87.3%

📄 employee_handbook.pdf
   Match: 72.1%
```

**That's it!** Your documents are now searchable. 🎉

---

## 💡 Use with RAG (Retrieval Augmented Generation)

```python
from openembed import OpenEmbedClient
from openai import OpenAI  # or anthropic, ollama, etc.

# 1. Get relevant documents from EMBEd
embed_client = OpenEmbedClient("http://localhost:8000")
results = embed_client.search(
    vector_store="company_docs",  # Your store from Step 2
    query="What is our vacation policy?",
    n_results=3
)

# 2. Build context from retrieved documents
context = "\n\n".join([
    f"Source: {r['metadata']['filename']}\n"
    f"Relevance: {r['similarity']:.1%}\n"
    f"Content: [Document content would be here]"
    for r in results
])

# 3. Send to your LLM with context
openai = OpenAI()
response = openai.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "Answer based only on the provided context."},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: What is our vacation policy?"}
    ]
)

print(response.choices[0].message.content)
```

**Works with:** OpenAI, Anthropic Claude, Ollama (Llama, Mistral), LM Studio, or any LLM.

---

## 🎯 What Can You Do?

| Use Case | Description |
|----------|-------------|
| **📚 Document Q&A** | Upload your docs → Ask questions in natural language → Get answers with sources |
| **🔍 Semantic Search** | Search by meaning, not keywords. Works across text, images, videos, audio |
| **🎨 Multi-Modal RAG** | Search "red running shoes" → Get matching text, images, and videos |
| **🤖 Chatbot Memory** | Give your chatbot knowledge of your specific documents |
| **📊 Content Analysis** | Find similar documents, images, or videos automatically |

---

## 📦 Python SDK Reference

```python
from openembed import OpenEmbedClient

client = OpenEmbedClient("http://localhost:8000")

# Search (text query)
results = client.search("store_name", "search query", n_results=10)

# Search (by file)
results = client.search("store_name", "/path/to/image.jpg")

# List all vector stores
stores = client.list_stores()
for store in stores:
    print(f"{store['name']}: {store['count']} files")

# Get store details
info = client.get_store("store_name")

# Create new store
client.create_store("new_store", description="My documents")

# Upload files (advanced - prefer Web UI)
client.upload("store_name", "document.pdf", modality="text")
client.upload_batch("store_name", ["file1.jpg", "file2.pdf", "audio.mp3"])
```

Full SDK documentation: [sdk/python/README.md](sdk/python/README.md)

---

## 🛠️ Features

- **7 Modalities:** Text, images, videos, audio, depth maps, thermal, IMU sensors
- **Cross-Modal Search:** Find images using text descriptions, or vice versa
- **Persistent Storage:** ChromaDB with disk persistence (your data survives restarts)
- **1024-dim Embeddings:** Meta ImageBind model (unified embedding space)
- **Web Interface:** Beautiful UI for uploading and managing files
- **RESTful API:** Full OpenAPI docs at http://localhost:8000/docs
- **Self-Hosted:** Your data never leaves your machine
- **Production Ready:** FastAPI backend + React frontend

---

## 📁 Supported Files

| Type | Formats |
|------|---------|
| **Documents** | .txt, .md, .pdf, .doc, .docx, .rtf |
| **Images** | .jpg, .png, .gif, .webp, .bmp |
| **Videos** | .mp4, .avi, .mov, .mkv, .webm |
| **Audio** | .mp3, .wav, .flac, .m4a, .ogg |

---

## 🔧 Configuration

EMBEd auto-detects your hardware (CPU/GPU/Apple Silicon). To customize:

```bash
# Create .env file
cat > .env << EOF
DEVICE=auto           # Options: auto, cpu, cuda, mps
CHROMA_PERSIST_DIR=./chroma_db
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=500000000  # 500MB
EOF
```

---

## ⚡ Performance

| Device | Speed | Use For |
|--------|-------|---------|
| **NVIDIA GPU** | 0.5-2s per file | Production |
| **Apple Silicon** | 1-3s per file | Production/Dev |
| **CPU** | 5-20s per file | Testing only |

**Note:** First run downloads ImageBind model (~4.5GB). Subsequent runs are instant.

---

## 🐛 Troubleshooting

<details>
<summary><b>Service won't start?</b></summary>

```bash
# Check logs
docker-compose logs -f

# Restart service
docker-compose down
docker-compose up -d
```
</details>

<details>
<summary><b>Out of memory error?</b></summary>

ImageBind needs ~6GB RAM. Try:
```bash
# Use CPU instead of GPU
echo "DEVICE=cpu" > .env
docker-compose down
docker-compose up -d
```

Or increase Docker's memory limit in Docker Desktop settings.
</details>

<details>
<summary><b>Port 8000 already in use?</b></summary>

Edit `docker-compose.yml`:
```yaml
ports:
  - "8080:8000"  # Change to 8080 or any free port
```
</details>

<details>
<summary><b>Can't connect to http://localhost:8000?</b></summary>

Wait 30-60 seconds for model to load. Check status:
```bash
docker-compose logs -f
# Look for: "Application startup complete"
```
</details>

---

## 🏗️ Manual Installation (Advanced)

<details>
<summary>Click to expand manual setup without Docker</summary>

**Requirements:** Python 3.9+, Node.js 16+, 8GB+ RAM

```bash
# Backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Start backend (Terminal 1)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Start frontend (Terminal 2)
cd frontend && npm start
```

Access:
- Web UI: http://localhost:3000
- API: http://localhost:8000/docs

</details>

---

## 🏛️ Architecture

```
┌──────────────────────────────────────┐
│   Web UI (localhost:8000)            │
│   • Upload files visually            │
│   • Manage vector stores             │
│   • View embeddings                  │
└──────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────┐
│   EMBEd Service                      │
│   • ImageBind (embedding generation) │
│   • ChromaDB (vector storage)        │
│   • FastAPI (REST API)               │
└──────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────┐
│   Your Python Application            │
│   • Query via SDK                    │
│   • Use in RAG/search/chatbot        │
│   • Integrate with any LLM           │
└──────────────────────────────────────┘
```

---

## 🤝 Contributing

Contributions welcome!

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file

Free to use, modify, and distribute.

---

## 🙏 Acknowledgments

Built with:
- **[ImageBind](https://github.com/facebookresearch/ImageBind)** by Meta AI - Multi-modal embeddings
- **[ChromaDB](https://github.com/chroma-core/chroma)** - Vector database
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern Python web framework
- **[React](https://react.dev/)** + **[Material-UI](https://mui.com/)** - Beautiful frontend

---

## 💬 Support & Community

- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/Himanshu8881212/EMBEd/issues)
- 💡 **Feature Requests:** [GitHub Discussions](https://github.com/Himanshu8881212/EMBEd/discussions)
- ⭐ **Star us on GitHub** if you find EMBEd useful!
- 🔗 **Share** with others building RAG applications

---

<p align="center">
  <b>Made with ❤️ for the open-source AI community</b>
</p>
