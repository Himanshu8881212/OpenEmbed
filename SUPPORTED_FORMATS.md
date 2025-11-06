# Supported File Formats - openEmbed

openEmbed supports **6 modalities** with comprehensive file format support and **automatic modality detection**.

## 📋 Quick Reference

| Modality | Icon | Formats | Total |
|----------|------|---------|-------|
| **Text** | 📝 | `.txt`, `.json`, `.md`, `.pdf`, `.doc`, `.docx`, `.rtf`, `.odt` | 8 |
| **Image** | 🖼️ | `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tiff`, `.tif`, `.webp`, `.svg` | 9 |
| **Video** | 🎥 | `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.flv`, `.wmv`, `.m4v`, `.mpg`, `.mpeg` | 10 |
| **Audio** | 🔊 | `.wav`, `.mp3`, `.flac`, `.m4a`, `.aac`, `.ogg`, `.wma`, `.opus` | 8 |
| **Depth** | 📊 | `.png`*, `.npy`, `.npz`, `.exr`, `.pfm` | 5 |
| **Thermal** | 🌡️ | `.jpg`*, `.jpeg`*, `.png`*, `.tiff`, `.tif` | 5 |

**Total: 45 supported file formats**

> **⚠️ Important Notes on Format Priority**:
> - Common image formats (`.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.webp`, `.svg`) are **automatically routed to the IMAGE modality**
> - Formats marked with * (`.jpg`, `.jpeg`, `.png`) are **shared between modalities**:
>   - **Auto-detection** always routes these to IMAGE (highest priority)
>   - **Explicit modality** parameter allows routing to DEPTH or THERMAL
> - For **depth maps**: Use specialized formats (`.npy`, `.npz`, `.exr`, `.pfm`) for auto-detection, OR explicitly specify `modality=depth` for `.png` files
> - For **thermal images**: Use `.tiff`/`.tif` for auto-detection, OR explicitly specify `modality=thermal` for `.jpg`/`.jpeg`/`.png` files
> - When in doubt, **explicitly specify the modality parameter** to ensure correct model routing

---

## 🔍 Automatic Modality Detection

openEmbed can **automatically detect** the modality from the file extension. No need to manually specify the modality type!

### How It Works

1. **Upload any supported file** - The system examines the file extension
2. **Automatic routing** - File is routed to the appropriate model
3. **Embedding generation** - The correct model generates the embedding
4. **Storage with metadata** - Embedding is stored with modality tag

### Example

```python
# Upload a .png file → Automatically detected as IMAGE
# Upload a .mp4 file → Automatically detected as VIDEO
# Upload a .pdf file → Automatically detected as TEXT
```

---

## 📝 Text Modality

**Supported Formats:**
- `.txt` - Plain text files
- `.md` - Markdown documents
- `.pdf` - PDF documents (text extraction)
- `.doc` - Microsoft Word (legacy)
- `.docx` - Microsoft Word (modern)
- `.rtf` - Rich Text Format
- `.odt` - OpenDocument Text

**Use Cases:**
- Document search and retrieval
- Semantic text similarity
- Cross-modal text-to-image search
- Knowledge base indexing

---

## 🖼️ Image Modality

**Supported Formats:**
- `.jpg`, `.jpeg` - JPEG images
- `.png` - PNG images
- `.bmp` - Bitmap images
- `.gif` - GIF images
- `.tiff`, `.tif` - TIFF images
- `.webp` - WebP images
- `.svg` - SVG vector graphics

**Use Cases:**
- Visual search
- Image similarity
- Cross-modal image-to-text search
- Product catalog search

---

## 🎥 Video Modality

**Supported Formats:**
- `.mp4` - MPEG-4 video
- `.avi` - Audio Video Interleave
- `.mov` - QuickTime movie
- `.mkv` - Matroska video
- `.webm` - WebM video
- `.flv` - Flash video
- `.wmv` - Windows Media Video
- `.m4v` - iTunes video
- `.mpg`, `.mpeg` - MPEG video

**Use Cases:**
- Video content search
- Scene similarity
- Video recommendation
- Content moderation

---

## 🔊 Audio Modality

**Supported Formats:**
- `.wav` - Waveform audio
- `.mp3` - MPEG audio
- `.flac` - Free Lossless Audio Codec
- `.m4a` - MPEG-4 audio
- `.aac` - Advanced Audio Coding
- `.ogg` - Ogg Vorbis
- `.wma` - Windows Media Audio
- `.opus` - Opus audio

**Use Cases:**
- Audio search
- Music similarity
- Speech recognition
- Sound effect matching

---

## 📊 Depth Map Modality

**Supported Formats:**
- `.png` - PNG depth maps (requires explicit `modality=depth` parameter)
- `.npy` - NumPy array files
- `.npz` - Compressed NumPy arrays
- `.exr` - OpenEXR format
- `.pfm` - Portable Float Map

**Use Cases:**
- 3D scene understanding
- Depth-based search
- Spatial reasoning
- AR/VR applications

---

## 🌡️ Thermal Imaging Modality

**Supported Formats:**
- `.jpg`, `.jpeg` - JPEG thermal images (requires explicit `modality=thermal` parameter)
- `.png` - PNG thermal images (requires explicit `modality=thermal` parameter)
- `.tiff`, `.tif` - TIFF thermal images

> **Note**: For thermal images in `.jpg`, `.jpeg`, or `.png` format, you **must** explicitly specify `modality=thermal` when uploading, as these formats default to the IMAGE modality for auto-detection.

**Use Cases:**
- Thermal pattern recognition
- Heat signature analysis
- Industrial inspection
- Medical imaging

---

## 🚀 API Endpoints

### 1. Get Supported Formats

```bash
GET /supported-formats
```

Returns all supported formats for each modality.

**Response:**
```json
{
  "success": true,
  "formats": {
    "text": [".txt", ".md", ".pdf", ...],
    "image": [".jpg", ".png", ...],
    ...
  },
  "total_formats": 44
}
```

### 2. Auto-Detection Upload (Single File)

```bash
POST /embed-auto
```

**Parameters:**
- `file` - File to upload (modality auto-detected)
- `vector_store` - Name of vector store
- `create_new` - Create vector store if it doesn't exist (optional)
- `modality` - Override auto-detection (optional)

**Example:**
```bash
curl -X POST http://localhost:8000/embed-auto \
  -F "file=@document.pdf" \
  -F "vector_store=my_store" \
  -F "create_new=true"
```

### 3. Batch Upload (Multiple Files, Mixed Modalities)

```bash
POST /embed-batch
```

**Parameters:**
- `files` - Multiple files (can be different modalities)
- `vector_store` - Name of vector store
- `create_new` - Create vector store if it doesn't exist (optional)

**Example:**
```bash
curl -X POST http://localhost:8000/embed-batch \
  -F "files=@image.png" \
  -F "files=@document.pdf" \
  -F "files=@video.mp4" \
  -F "vector_store=my_store" \
  -F "create_new=true"
```

**Response:**
```json
{
  "success": true,
  "total_files": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {
      "filename": "image.png",
      "modality": "image",
      "embedding_id": "...",
      "embedding_shape": 768,
      "embedding_preview": [...]
    },
    ...
  ]
}
```

---

## 💡 Usage Examples

### Example 1: Mixed Modality Upload

Upload an image, a PDF, and a video in one request:

```python
import requests

files = [
    ('files', ('photo.jpg', open('photo.jpg', 'rb'))),
    ('files', ('report.pdf', open('report.pdf', 'rb'))),
    ('files', ('demo.mp4', open('demo.mp4', 'rb')))
]

response = requests.post(
    'http://localhost:8000/embed-batch',
    files=files,
    data={'vector_store': 'my_collection', 'create_new': 'true'}
)

print(response.json())
```

### Example 2: Auto-Detection with Override

Let the system auto-detect, or override if needed:

```python
# Auto-detect (recommended)
response = requests.post(
    'http://localhost:8000/embed-auto',
    files={'file': open('image.png', 'rb')},
    data={'vector_store': 'my_store'}
)

# Explicit override
response = requests.post(
    'http://localhost:8000/embed-auto',
    files={'file': open('image.png', 'rb')},
    data={'vector_store': 'my_store', 'modality': 'image'}
)
```

---

## ⚙️ Configuration

You can customize supported formats via environment variables:

```bash
# .env file
ALLOWED_TEXT_FORMATS=.txt,.md,.pdf,.docx
ALLOWED_IMAGE_FORMATS=.jpg,.png,.webp
ALLOWED_VIDEO_FORMATS=.mp4,.mov,.avi
ALLOWED_AUDIO_FORMATS=.wav,.mp3,.flac
ALLOWED_DEPTH_FORMATS=.png,.npy,.exr
ALLOWED_THERMAL_FORMATS=.jpg,.png,.tiff
```

---

## 🎯 Best Practices

1. **Use auto-detection** - Let the system detect modality from file extension
2. **Batch similar files** - Upload multiple files of the same type together
3. **Mixed batches** - Upload different modalities in one batch for efficiency
4. **Check responses** - Always verify the detected modality is correct
5. **Handle errors** - Batch uploads return partial success with error details

---

## 🔧 Troubleshooting

### File format not recognized?

Check supported formats:
```bash
curl http://localhost:8000/supported-formats
```

### Wrong modality detected?

Use explicit modality parameter:
```bash
-F "modality=image"
```

### Batch upload partial failure?

Check the `errors` array in the response for details on failed files.

---

## 📊 Performance

- **Lazy Loading**: Models load on-demand, saving memory
- **Batch Processing**: Process multiple files efficiently
- **Parallel Processing**: Different modalities can be processed simultaneously
- **Embedding Preview**: First 10 values returned for verification

---

---

## 🔍 Cross-Modal Search

openEmbed supports **cross-modal retrieval** using LanguageBind's shared embedding space. This means you can:

- 🖼️ **Search with an image** to find similar images, videos, or text descriptions
- 📝 **Search with text** to find relevant images, videos, or audio
- 🎥 **Search with video** to find similar videos or related images
- 🔊 **Search with audio** to find related videos, images, or text
- 📊 **Search with depth maps** to find similar spatial structures
- 🌡️ **Search with thermal images** to find similar heat patterns

### How It Works

LanguageBind creates a **unified embedding space** where all 6 modalities are aligned. This allows semantic search across different modalities:

1. **Upload query file** (any modality)
2. **Generate embedding** using the appropriate model
3. **Search vector store** using cosine similarity
4. **Return ranked results** from any or specific modality

### API Endpoint

```bash
POST /search
```

**Parameters:**
- `file` - Query file (any supported modality)
- `vector_store` - Name of vector store to search
- `modality` - Optional explicit modality (auto-detected if not provided)
- `n_results` - Number of results to return (default: 10)
- `filter_modality` - Optional filter to only return specific modality

**Example 1: Text → Image Search**

```bash
curl -X POST http://localhost:8000/search \
  -F "file=@query.txt" \
  -F "vector_store=my_store" \
  -F "n_results=5" \
  -F "filter_modality=image"
```

**Example 2: Image → All Modalities**

```bash
curl -X POST http://localhost:8000/search \
  -F "file=@photo.jpg" \
  -F "vector_store=my_store" \
  -F "n_results=10"
```

**Example 3: Video → Video Search**

```python
import requests

with open('query_video.mp4', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/search',
        files={'file': ('query.mp4', f)},
        data={
            'vector_store': 'video_collection',
            'modality': 'video',
            'n_results': 5,
            'filter_modality': 'video'
        }
    )

results = response.json()
for result in results['results']:
    print(f"Rank {result['rank']}: {result['modality']} - Similarity: {result['similarity']:.4f}")
```

**Response:**

```json
{
  "success": true,
  "query_modality": "text",
  "vector_store": "my_store",
  "n_results": 5,
  "filter_modality": "image",
  "results": [
    {
      "id": "abc-123",
      "similarity": 0.8542,
      "distance": 0.2916,
      "modality": "image",
      "metadata": {
        "modality": "image",
        "added_at": "2024-01-15T10:30:00"
      },
      "rank": 1
    },
    ...
  ]
}
```

### Use Cases

1. **Multi-Modal RAG**: Build RAG systems that can retrieve across text, images, and videos
2. **Visual Search**: Find images using text descriptions or vice versa
3. **Content Discovery**: Discover related content across different media types
4. **Semantic Similarity**: Find semantically similar content regardless of format
5. **Cross-Modal Recommendation**: Recommend videos based on image queries

---

## 🎉 Summary

openEmbed provides:
- ✅ **45 supported file formats** across 6 modalities
- ✅ **Automatic modality detection** from file extensions
- ✅ **Batch upload** with mixed modalities
- ✅ **Cross-modal search** using LanguageBind's shared embedding space
- ✅ **Embedding preview** for verification
- ✅ **Lazy model loading** for memory efficiency
- ✅ **Comprehensive API** for all use cases
- ✅ **RAG-ready** vector storage with ChromaDB

