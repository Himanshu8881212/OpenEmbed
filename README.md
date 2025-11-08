# OpenEmbed - Multi-Modal Embedding Application

A professional, production-ready application for generating embeddings from multiple modalities using Meta's ImageBind and storing them in ChromaDB vector store.

## Features

- **7 Modality Support**: Generate embeddings from text, images, videos, audio files, depth maps, thermal images, and IMU data
- **ImageBind Integration**: State-of-the-art multi-modal embeddings using Meta's ImageBind (CVPR 2023)
- **Vector Storage**: Persistent storage using ChromaDB
- **RESTful API**: FastAPI-based backend with comprehensive API endpoints
- **Modern Web UI**: Professional React + Material-UI interface
- **Production Ready**: Logging, error handling, and monitoring
- **Cross-Modal Search**: Search across different modalities in a unified embedding space

## Architecture

```
OpenEmbed/
├── app/
│   ├── api/                 # API routes and endpoints
│   ├── core/                # Configuration and logging
│   ├── models/              # Pydantic schemas
│   ├── services/            # Business logic (ImageBind, ChromaDB)
│   └── utils/               # Utility functions
├── frontend/                # React + TypeScript frontend
│   ├── src/
│   │   ├── components/      # Reusable components
│   │   └── pages/           # Page components
│   └── public/              # Static assets
└── demo_files/              # Sample files for testing
```

## Supported Modalities

1. **Text**: Plain text content (.txt, .md, .json, .pdf, .doc, .docx)
2. **Image**: Images (.jpg, .png, .bmp, .gif, .tiff, .webp, .svg)
3. **Video**: Videos (.mp4, .avi, .mov, .mkv, .webm, .flv, .wmv)
4. **Audio**: Audio files (.wav, .mp3, .flac, .m4a, .aac, .ogg, .opus)
5. **Depth**: Depth maps (.png, .npy, .npz, .exr, .pfm)
6. **Thermal**: Thermal images (.jpg, .png, .tiff)
7. **IMU**: Inertial measurement data (.csv, .json, .npy, .npz, .pkl, .h5)

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
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run the backend**:
   ```bash
   uvicorn app.main:app --reload
   ```

6. **Run the frontend** (in a new terminal):
   ```bash
   cd frontend
   npm install
   npm start
   ```

7. **Access the application**:
   - Web UI: http://localhost:3000
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

## ImageBind Model

The application automatically downloads and caches the ImageBind model on first run:

- **ImageBind Huge**: Unified multi-modal encoder (~4.5GB)
  - Single model for all 7 modalities
  - Shared embedding space (1024 dimensions)
  - Trained on image-paired data across modalities

Models are cached in `~/.cache/torch/hub/checkpoints/`.

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

- **ImageBind**: [facebookresearch/ImageBind](https://github.com/facebookresearch/ImageBind)
- **ChromaDB**: [chroma-core/chroma](https://github.com/chroma-core/chroma)
- **FastAPI**: [tiangolo/fastapi](https://github.com/tiangolo/fastapi)
- **React**: [facebook/react](https://github.com/facebook/react)
- **Material-UI**: [mui/material-ui](https://github.com/mui/material-ui)

## Citation

If you use this application in your research, please cite ImageBind:

```bibtex
@inproceedings{girdhar2023imagebind,
  title={ImageBind: One Embedding Space To Bind Them All},
  author={Girdhar, Rohit and El-Nouby, Alaaeldin and Liu, Zhuang and Singh, Mannat and Alwala, Kalyan Vasudev and Joulin, Armand and Misra, Ishan},
  booktitle={CVPR},
  year={2023}
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
