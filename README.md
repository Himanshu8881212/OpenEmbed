# openEmbed - Multi-Modal Embedding Application

A professional, production-ready application for generating embeddings from multiple modalities (text, image, video, audio, depth maps, and thermal images) using LanguageBind and storing them in ChromaDB vector store.

## Features

- **6 Modality Support**: Generate embeddings from text, images, videos, audio files, depth maps, and thermal images
- **LanguageBind Integration**: State-of-the-art multi-modal embeddings using LanguageBind (ICLR 2024)
- **Vector Storage**: Persistent storage using ChromaDB
- **RESTful API**: FastAPI-based backend with comprehensive API endpoints
- **Modern Web UI**: Intuitive web interface for file uploads and vector store management
- **Production Ready**: Docker support, logging, error handling, and monitoring
- **Similarity Search**: Cross-modal and intra-modal similarity search capabilities

## Architecture

```
openEmbed/
├── app/
│   ├── api/                 # API routes and endpoints
│   ├── core/                # Configuration and logging
│   ├── models/              # Pydantic schemas
│   ├── services/            # Business logic (LanguageBind, ChromaDB)
│   └── utils/               # Utility functions
├── static/                  # Frontend assets (CSS, JS)
├── templates/               # HTML templates
├── tests/                   # Test suite
└── docker/                  # Docker configuration
```

## Supported Modalities

1. **Text**: Plain text content
2. **Image**: JPG, PNG, BMP images
3. **Video**: MP4, AVI, MOV, MKV videos
4. **Audio**: WAV, MP3, FLAC, M4A audio files
5. **Depth**: PNG, NPY depth maps
6. **Thermal**: JPG, PNG thermal images

## Installation

### Prerequisites

- Python 3.10+
- CUDA-capable GPU (recommended) or CPU
- 8GB+ RAM
- 10GB+ storage for models

### Option 1: Local Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd EMBEd
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install git+https://github.com/PKU-YuanGroup/LanguageBind.git
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run the application**:
   ```bash
   python -m app.main
   ```

6. **Access the application**:
   - Web UI: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Option 2: Docker Deployment

1. **Using Docker Compose** (recommended):
   ```bash
   docker-compose up -d
   ```

2. **Using Docker**:
   ```bash
   docker build -t embed-app .
   docker run -p 8000:8000 -v $(pwd)/chroma_db:/app/chroma_db embed-app
   ```

## Usage

### Web Interface

1. **Create a Vector Store**:
   - Click "Create New Vector Store"
   - Enter a name and optional description
   - Click "Create"

2. **Upload and Generate Embeddings**:
   - Select modality (text, image, video, etc.)
   - For files: Upload your file
   - For text: Enter text content
   - Select vector store
   - Click "Generate & Store Embedding"

3. **Search Similar Embeddings**:
   - Select vector store
   - Choose query modality
   - Provide query (file or text)
   - Set number of results
   - Click "Search"

### API Usage

#### Create Vector Store

```bash
curl -X POST "http://localhost:8000/api/vector-stores" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_store",
    "description": "My vector store"
  }'
```

#### Upload File

```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@image.jpg" \
  -F "modality=image"
```

#### Generate Embedding

```bash
curl -X POST "http://localhost:8000/api/embeddings" \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store_name": "my_store",
    "operation": "use_existing",
    "modality": "image",
    "file_id": "<file_id_from_upload>"
  }'
```

#### Search Similar

```bash
curl -X POST "http://localhost:8000/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store_name": "my_store",
    "query_modality": "text",
    "query_text": "a beautiful sunset",
    "n_results": 10
  }'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/vector-stores` | GET | List all vector stores |
| `/api/vector-stores` | POST | Create new vector store |
| `/api/vector-stores/{name}` | GET | Get vector store info |
| `/api/vector-stores/{name}` | DELETE | Delete vector store |
| `/api/upload` | POST | Upload file |
| `/api/embeddings` | POST | Generate and store embedding |
| `/api/search` | POST | Search similar embeddings |

## Configuration

Configuration is managed through environment variables or `.env` file:

```env
# Application
APP_NAME=EMBEd
DEBUG=False
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# Model Configuration
DEVICE=cuda:0  # or cpu
CACHE_DIR=./cache_dir
MODEL_CACHE_DIR=./model_cache

# ChromaDB
CHROMA_PERSIST_DIR=./chroma_db

# Upload Configuration
MAX_FILE_SIZE=500000000  # 500MB
UPLOAD_DIR=./uploads
```

## LanguageBind Models

The application automatically downloads and caches the following models on first run:

- **LanguageBind_Image**: Image encoder
- **LanguageBind_Video_FT**: Video encoder (fine-tuned)
- **LanguageBind_Audio_FT**: Audio encoder (fine-tuned)
- **LanguageBind_Depth**: Depth map encoder
- **LanguageBind_Thermal**: Thermal image encoder

Models are cached in `cache_dir` (configurable).

## Performance Considerations

### GPU vs CPU

- **GPU (CUDA)**: Recommended for production use
  - Embedding generation: ~0.5-2 seconds per item
  - Concurrent requests supported

- **CPU**: Suitable for development/testing
  - Embedding generation: ~5-20 seconds per item
  - Limited concurrency

### Optimization Tips

1. **Batch Processing**: Upload multiple files and generate embeddings in parallel
2. **Model Caching**: First run downloads models (~10GB). Subsequent runs are faster
3. **Vector Store Indexing**: ChromaDB automatically indexes for fast retrieval
4. **GPU Memory**: ~8GB VRAM recommended for optimal performance

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
# Format code
black app/

# Lint
flake8 app/

# Type checking
mypy app/
```

### Project Structure

```
app/
├── api/
│   └── routes.py          # API endpoints
├── core/
│   ├── config.py          # Configuration
│   └── logger.py          # Logging setup
├── models/
│   └── schemas.py         # Pydantic models
├── services/
│   ├── languagebind_service.py  # LanguageBind integration
│   └── chroma_service.py        # ChromaDB integration
└── utils/
    └── file_handler.py    # File operations
```

## Troubleshooting

### Models Not Loading

- Check internet connection for first-time model download
- Ensure sufficient disk space (~10GB)
- Verify CUDA installation if using GPU

### Out of Memory

- Reduce batch size
- Use CPU instead of GPU
- Increase system RAM/VRAM

### Slow Performance

- Enable GPU acceleration
- Check system resources
- Reduce file sizes
- Optimize concurrent requests

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

This project is licensed under the MIT License.

## Acknowledgments

- **LanguageBind**: [PKU-YuanGroup/LanguageBind](https://github.com/PKU-YuanGroup/LanguageBind)
- **ChromaDB**: [chroma-core/chroma](https://github.com/chroma-core/chroma)
- **FastAPI**: [tiangolo/fastapi](https://github.com/tiangolo/fastapi)

## Citation

If you use this application in your research, please cite LanguageBind:

```bibtex
@inproceedings{languagebind,
  title={LanguageBind: Extending Video-Language Pretraining to N-modality by Language-based Semantic Alignment},
  author={Zhu, Bin and Lin, Bin and Ning, Munan and Yan, Yang and Cui, Jiaxi and Wang, HongFa and Pang, Yatian and Jiang, Wenhao and Zhang, Junwu and Li, Zongwei and others},
  booktitle={International Conference on Learning Representations},
  year={2024}
}
```

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Contact: [your-email@example.com]

## Roadmap

- [ ] Add batch processing API
- [ ] Implement embedding visualization
- [ ] Add authentication and user management
- [ ] Support for more modalities
- [ ] Real-time embedding generation
- [ ] Advanced search filters
- [ ] Export/import vector stores

---

**Built with ❤️ using LanguageBind and ChromaDB**
