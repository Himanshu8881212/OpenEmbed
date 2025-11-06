# 🚀 Get Started with EMBEd

Welcome to **EMBEd** - Your professional multi-modal embedding application!

## What is EMBEd?

EMBEd is a production-ready application that generates embeddings from **6 different types of data**:
- 📝 Text
- 🖼️ Images
- 🎬 Videos
- 🎵 Audio
- 🗺️ Depth Maps
- 🌡️ Thermal Images

Using state-of-the-art **LanguageBind** (ICLR 2024) technology, you can:
- Store embeddings in a vector database
- Search across different modalities
- Find similar content using text, images, or any other format
- Build powerful semantic search applications

## 3-Step Quick Start

### Step 1: Run Verification

```bash
python3 verify_setup.py
```

This checks if everything is ready to go!

### Step 2: Start Application

**Linux/macOS:**
```bash
./run.sh
```

**Windows:**
```cmd
run.bat
```

**Docker:**
```bash
docker-compose up -d
```

### Step 3: Open Browser

Go to: **http://localhost:8000**

That's it! 🎉

## What Happens on First Run?

⏰ **First run takes 10-30 minutes** because it downloads AI models (~10GB)

You'll see messages like:
```
Downloading LanguageBind models...
LanguageBind_Image: 100%|████████| 2.5GB/2.5GB
LanguageBind_Video_FT: 100%|████████| 2.8GB/2.8GB
...
```

☕ Grab a coffee! Subsequent runs are instant.

## Your First Multi-Modal Search

### 1. Create a Collection
- Click "Create New Vector Store"
- Name: `my_first_collection`
- Click Create

### 2. Add Some Images
- Select Modality: "Image"
- Upload an image (e.g., sunset.jpg)
- Select: `my_first_collection`
- Click "Generate & Store Embedding"

Repeat with 2-3 more images.

### 3. Search with Text
- Select vector store: `my_first_collection`
- Query modality: "Text"
- Enter: "beautiful sunset"
- Click Search

🎯 See your images ranked by similarity!

### 4. Try Cross-Modal Search
- Upload a video
- Search for it using text: "nature scene"
- Mix images, videos, and audio in the same collection
- Search across all formats!

## What Can You Build?

### 🔍 Image Search Engine
```
Users upload photos → Search with "beach vacation"
→ Find all beach-related photos
```

### 🎬 Video Content Discovery
```
Upload video library → Search "cooking tutorial"
→ Find all cooking videos
```

### 🎵 Music Similarity
```
Upload songs → Search "upbeat electronic"
→ Find similar music
```

### 🤖 Multi-Modal AI
```
Combine text, images, videos, audio
→ Build smart applications
→ Semantic understanding across formats
```

## Project Files Overview

```
📁 EMBEd/
├── 📘 README.md              - Full documentation
├── 🚀 QUICKSTART.md          - 5-minute guide
├── 💻 INSTALL.md             - Installation details
├── 📖 API_GUIDE.md           - API reference
├── 📋 PROJECT_SUMMARY.md     - Technical overview
├── ✅ verify_setup.py        - Verification script
│
├── 🐍 app/                   - Application code
│   ├── api/                  - REST API endpoints
│   ├── core/                 - Configuration & logging
│   ├── models/               - Data models
│   ├── services/             - LanguageBind & ChromaDB
│   └── utils/                - Helper functions
│
├── 🎨 static/                - Web interface
│   ├── css/                  - Styling
│   └── js/                   - Frontend logic
│
├── 📄 templates/             - HTML pages
├── 🐳 Dockerfile             - Docker config
├── ⚙️ requirements.txt       - Dependencies
└── 🚀 run.sh / run.bat       - Startup scripts
```

## Documentation Guide

**Start Here:**
1. 📘 [README.md](README.md) - Overview and features
2. 🚀 [QUICKSTART.md](QUICKSTART.md) - Get running in 5 minutes

**For Installation:**
3. 💻 [INSTALL.md](INSTALL.md) - Detailed setup for each OS

**For Development:**
4. 📖 [API_GUIDE.md](API_GUIDE.md) - Complete API reference
5. 📋 [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Architecture details

## System Requirements

### Minimum (CPU Mode)
- Python 3.10+
- 8GB RAM
- 15GB disk space
- Any modern CPU

**Performance:** Slow but works (5-30s per embedding)

### Recommended (GPU Mode)
- Python 3.10+
- 16GB RAM
- NVIDIA GPU with 8GB+ VRAM
- 20GB disk space

**Performance:** Fast (1-2s per embedding)

## Common Commands

### Check Installation
```bash
python3 verify_setup.py
```

### Start Application
```bash
./run.sh                           # Linux/macOS
run.bat                            # Windows
docker-compose up -d               # Docker
```

### Stop Application
```bash
Ctrl+C                             # Local
docker-compose down                # Docker
```

### View Logs
```bash
tail -f logs/app_*.log            # Local
docker-compose logs -f             # Docker
```

### Health Check
```bash
curl http://localhost:8000/api/health
```

## Access Points

- 🌐 **Web Interface:** http://localhost:8000
- 📚 **API Docs:** http://localhost:8000/docs
- 🔌 **API Base:** http://localhost:8000/api
- ❤️ **Health Check:** http://localhost:8000/api/health

## Need Help?

### Quick Troubleshooting

**Problem:** Port 8000 in use
**Solution:** Edit `.env` and change `PORT=8080`

**Problem:** Out of memory
**Solution:** Set `DEVICE=cpu` in `.env`

**Problem:** Models not downloading
**Solution:** Check internet connection, wait for download to complete

**Problem:** Application won't start
**Solution:** Run `python3 verify_setup.py`

### Get Support

1. Check [INSTALL.md](INSTALL.md) for detailed setup
2. Search existing issues on GitHub
3. Create a new issue with error details

## Next Steps

After getting started:

1. **Explore the Web UI**
   - Create multiple vector stores
   - Try all 6 modalities
   - Experiment with cross-modal search

2. **Try the API**
   - Read [API_GUIDE.md](API_GUIDE.md)
   - Use curl or Python SDK
   - Build your own application

3. **Deploy to Production**
   - Use Docker deployment
   - Configure for your needs
   - Scale as required

## Example Use Cases

### 📸 Photo Library
```
1. Create "family_photos" store
2. Upload all family photos
3. Search: "birthday party"
4. Find all birthday photos instantly
```

### 🎓 Educational Content
```
1. Create "lectures" store
2. Add lecture videos
3. Search: "quantum physics"
4. Find relevant lectures
```

### 🎵 Music Collection
```
1. Create "music_library" store
2. Upload songs
3. Search: "relaxing ambient"
4. Discover similar tracks
```

## Tips for Success

### 🎯 Best Practices
- ✅ Name vector stores descriptively
- ✅ Add metadata to embeddings
- ✅ Start with small collections
- ✅ Use GPU for production
- ✅ Monitor disk space

### ⚡ Performance Tips
- Use GPU when possible
- Batch upload files
- Keep collections organized
- Monitor system resources
- Cache models persist across runs

### 🔒 Security Notes
- Currently no authentication
- For production: add auth layer
- Use HTTPS in production
- Validate all uploads
- Set file size limits

## What Makes EMBEd Special?

✨ **Multi-Modal**: 6 different data types
🚀 **Production-Ready**: Docker, logging, monitoring
🎯 **Easy to Use**: Web UI + REST API
🔬 **State-of-the-Art**: LanguageBind (ICLR 2024)
💾 **Persistent Storage**: ChromaDB vector database
🌐 **Cross-Modal Search**: Find images with text!
📦 **Self-Contained**: Everything included
🐳 **Docker Support**: One-command deployment

## Success!

If you can:
- ✅ Access http://localhost:8000
- ✅ Create a vector store
- ✅ Upload a file
- ✅ Generate an embedding
- ✅ Search and get results

**Congratulations! You're ready to build amazing multi-modal applications!** 🎉

---

**Questions?** Check the docs or create an issue!

**Happy Embedding!** 🚀
