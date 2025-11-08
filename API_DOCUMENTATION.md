# OpenEmbed API Documentation

## Overview

OpenEmbed is a production-ready multi-modal embedding warehouse that provides REST APIs for storing, searching, and retrieving embeddings across 7 modalities: **Text, Image, Video, Audio, Depth, Thermal, and IMU**.

**Base URL**: `http://localhost:8000/api`

---

## Authentication

Currently, the API does not require authentication. For production deployments, consider adding API key authentication.

---

## Core Endpoints for RAG Applications

### 1. **Search by Text Query** (Most Common for RAG)

**Endpoint**: `POST /search-by-id`

**Description**: Search for similar embeddings using a text query. This is the primary endpoint for RAG applications.

**Request Body**:
```json
{
  "vector_store": "my_multimodal_store",
  "text": "beautiful sunset over the ocean",
  "n_results": 10,
  "include_metadata": true,
  "filter_modality": "image"  // Optional: filter by modality
}
```

**Response**:
```json
{
  "results": [
    {
      "id": "embedding-id-123",
      "similarity": 0.87,
      "distance": 0.13,
      "modality": "image",
      "rank": 1,
      "file_path": "/api/uploads/image/file-id-456",
      "metadata": {
        "file_id": "file-id-456",
        "filename": "sunset.jpg",
        "modality": "image",
        "timestamp": "2025-11-08T13:37:15.123456"
      }
    }
  ],
  "query_time_ms": 45.2,
  "total_results": 1
}
```

**cURL Example**:
```bash
curl -X POST "http://localhost:8000/api/search-by-id" \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store": "my_multimodal_store",
    "text": "beautiful sunset over the ocean",
    "n_results": 5,
    "include_metadata": true
  }'
```

---

### 2. **Search by File Upload**

**Endpoint**: `POST /search`

**Description**: Search using an uploaded file (image, audio, video, etc.)

**Request** (multipart/form-data):
- `file`: File to search with
- `vector_store`: Name of the vector store
- `modality`: Modality of the file (optional, auto-detected)
- `n_results`: Number of results (default: 10)
- `filter_modality`: Filter results by modality (optional)

**cURL Example**:
```bash
curl -X POST "http://localhost:8000/api/search" \
  -F "file=@/path/to/image.jpg" \
  -F "vector_store=my_multimodal_store" \
  -F "n_results=5"
```

---

### 3. **Upload and Embed Files**

**Endpoint**: `POST /embed`

**Description**: Upload a file and generate its embedding

**Request** (multipart/form-data):
- `file`: File to embed
- `vector_store`: Name of the vector store
- `modality`: Modality (text, image, video, audio, depth, thermal, imu)

**Response**:
```json
{
  "embedding_id": "abc-123-def",
  "file_id": "file-456-xyz",
  "modality": "image",
  "vector_store": "my_multimodal_store",
  "filename": "example.jpg"
}
```

**cURL Example**:
```bash
curl -X POST "http://localhost:8000/api/embed" \
  -F "file=@/path/to/document.pdf" \
  -F "vector_store=my_multimodal_store" \
  -F "modality=text"
```

---

### 4. **Batch Upload (Folder Upload)**

**Endpoint**: `POST /embed-folder`

**Description**: Upload multiple files at once with auto-detected modalities

**Request** (multipart/form-data):
- `files`: Multiple files
- `vector_store`: Name of the vector store

**cURL Example**:
```bash
curl -X POST "http://localhost:8000/api/embed-folder" \
  -F "files=@/path/to/file1.jpg" \
  -F "files=@/path/to/file2.mp3" \
  -F "files=@/path/to/file3.txt" \
  -F "vector_store=my_multimodal_store"
```

---

### 5. **List Vector Stores**

**Endpoint**: `GET /vector-stores`

**Response**:
```json
{
  "stores": [
    {
      "name": "my_multimodal_store",
      "description": null,
      "count": 3,
      "modality": null,
      "created_at": "2025-11-08T13:37:14.123456",
      "size_bytes": 108992,
      "metadata": {
        "modality_counts": {
          "text": 1,
          "image": 1,
          "audio": 1
        }
      }
    }
  ],
  "total": 1
}
```

---

### 6. **Get Vector Store Files**

**Endpoint**: `GET /vector-stores/{name}/files`

**Response**:
```json
{
  "files": [
    {
      "id": "embedding-id-123",
      "filename": "sample_text.txt",
      "modality": "text",
      "timestamp": "2025-11-08T13:37:15.123456",
      "metadata": {
        "file_id": "file-id-456",
        "modality": "text"
      }
    }
  ]
}
```

---

### 7. **Download Files**

**Endpoint**: `GET /uploads/{modality}/{file_id}`

**Description**: Download or view uploaded files

**Example**:
```
http://localhost:8000/api/uploads/image/file-id-456
```

---

## Supported Modalities

| Modality | File Extensions |
|----------|----------------|
| **Text** | `.txt`, `.md`, `.json`, `.csv` |
| **Image** | `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.webp` |
| **Video** | `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm` |
| **Audio** | `.wav`, `.mp3`, `.flac`, `.m4a`, `.ogg` |
| **Depth** | `.png`, `.jpg`, `.jpeg`, `.tiff` |
| **Thermal** | `.png`, `.jpg`, `.jpeg`, `.tiff` |
| **IMU** | `.csv`, `.json`, `.txt` |

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200 OK`: Success
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

**Error Response Format**:
```json
{
  "detail": "Error message here"
}
```

---

## Rate Limiting

Currently, there are no rate limits. For production, consider implementing rate limiting based on your requirements.

---

## Next Steps

1. See `PYTHON_SDK_EXAMPLE.py` for a complete Python SDK implementation
2. See `RAG_INTEGRATION_EXAMPLE.py` for RAG application integration examples
3. Check the OpenAPI documentation at `http://localhost:8000/docs` for interactive API testing

