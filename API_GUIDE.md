# API Usage Guide

Complete guide for using the EMBEd REST API.

## Base URL

```
http://localhost:8000/api
```

## Authentication

Currently, the API does not require authentication. For production use, implement authentication as needed.

## Common Headers

```
Content-Type: application/json
```

## API Endpoints

### 1. Health Check

Check application health and status.

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "models_loaded": true,
  "vector_store_connected": true,
  "timestamp": "2025-01-06T12:00:00.000000"
}
```

**Example**:
```bash
curl http://localhost:8000/api/health
```

---

### 2. Create Vector Store

Create a new vector store for storing embeddings.

**Endpoint**: `POST /vector-stores`

**Request Body**:
```json
{
  "name": "my_store",
  "description": "Optional description",
  "metadata": {
    "project": "example",
    "version": "1.0"
  }
}
```

**Response**:
```json
{
  "name": "my_store",
  "description": "Optional description",
  "count": 0,
  "created_at": "2025-01-06T12:00:00.000000",
  "metadata": {
    "project": "example",
    "version": "1.0",
    "created_at": "2025-01-06T12:00:00.000000"
  }
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/vector-stores \
  -H "Content-Type: application/json" \
  -d '{
    "name": "image_embeddings",
    "description": "Store for image embeddings"
  }'
```

**Validation**:
- Name must be alphanumeric with hyphens/underscores
- Name must be unique
- Name length: 1-100 characters

---

### 3. List Vector Stores

Get all vector stores.

**Endpoint**: `GET /vector-stores`

**Response**:
```json
{
  "stores": [
    {
      "name": "my_store",
      "description": "Optional description",
      "count": 150,
      "created_at": "2025-01-06T12:00:00.000000",
      "metadata": {}
    }
  ],
  "total": 1
}
```

**Example**:
```bash
curl http://localhost:8000/api/vector-stores
```

---

### 4. Get Vector Store

Get information about a specific vector store.

**Endpoint**: `GET /vector-stores/{name}`

**Response**:
```json
{
  "name": "my_store",
  "description": "Optional description",
  "count": 150,
  "created_at": "2025-01-06T12:00:00.000000",
  "metadata": {}
}
```

**Example**:
```bash
curl http://localhost:8000/api/vector-stores/my_store
```

---

### 5. Delete Vector Store

Delete a vector store and all its embeddings.

**Endpoint**: `DELETE /vector-stores/{name}`

**Response**:
```json
{
  "success": true,
  "message": "Vector store 'my_store' deleted successfully"
}
```

**Example**:
```bash
curl -X DELETE http://localhost:8000/api/vector-stores/my_store
```

---

### 6. Upload File

Upload a file for embedding generation.

**Endpoint**: `POST /upload`

**Request**: Multipart form data

**Parameters**:
- `file`: File to upload (binary)
- `modality`: One of: text, image, video, audio, depth, thermal

**Response**:
```json
{
  "success": true,
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "example.jpg",
  "modality": "image",
  "size": 1024000,
  "message": "File uploaded successfully"
}
```

**Example**:
```bash
# Upload image
curl -X POST http://localhost:8000/api/upload \
  -F "file=@image.jpg" \
  -F "modality=image"

# Upload video
curl -X POST http://localhost:8000/api/upload \
  -F "file=@video.mp4" \
  -F "modality=video"

# Upload audio
curl -X POST http://localhost:8000/api/upload \
  -F "file=@audio.wav" \
  -F "modality=audio"
```

**Supported File Formats**:

| Modality | Formats |
|----------|---------|
| image | .jpg, .jpeg, .png, .bmp |
| video | .mp4, .avi, .mov, .mkv |
| audio | .wav, .mp3, .flac, .m4a |
| depth | .png, .npy |
| thermal | .jpg, .jpeg, .png |
| text | .txt |

**Limits**:
- Max file size: 500MB (configurable)

---

### 7. Generate Embedding

Generate and store an embedding from uploaded file or text.

**Endpoint**: `POST /embeddings`

**Request Body (File-based)**:
```json
{
  "vector_store_name": "my_store",
  "operation": "use_existing",
  "modality": "image",
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "source": "user_upload",
    "category": "nature"
  }
}
```

**Request Body (Text-based)**:
```json
{
  "vector_store_name": "my_store",
  "operation": "use_existing",
  "modality": "text",
  "file_id": "text-placeholder",
  "text_content": "A beautiful sunset over the ocean",
  "metadata": {
    "source": "user_input"
  }
}
```

**Response**:
```json
{
  "success": true,
  "message": "Embedding generated and stored successfully",
  "embedding_id": "660e8400-e29b-41d4-a716-446655440000",
  "vector_store_name": "my_store",
  "modality": "image",
  "metadata": {
    "source": "user_upload",
    "category": "nature",
    "modality": "image",
    "filename": "example.jpg"
  }
}
```

**Example**:
```bash
# For file-based modalities
FILE_ID=$(curl -X POST http://localhost:8000/api/upload \
  -F "file=@image.jpg" \
  -F "modality=image" | jq -r '.file_id')

curl -X POST http://localhost:8000/api/embeddings \
  -H "Content-Type: application/json" \
  -d "{
    \"vector_store_name\": \"my_store\",
    \"operation\": \"use_existing\",
    \"modality\": \"image\",
    \"file_id\": \"$FILE_ID\"
  }"

# For text
curl -X POST http://localhost:8000/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store_name": "my_store",
    "operation": "use_existing",
    "modality": "text",
    "file_id": "text-placeholder",
    "text_content": "A beautiful sunset"
  }'
```

---

### 8. Search Similar Embeddings

Search for similar embeddings in a vector store.

**Endpoint**: `POST /search`

**Request Body (Text Query)**:
```json
{
  "vector_store_name": "my_store",
  "query_modality": "text",
  "query_text": "sunset over ocean",
  "n_results": 10,
  "include_metadata": true
}
```

**Request Body (File Query)**:
```json
{
  "vector_store_name": "my_store",
  "query_modality": "image",
  "query_file_id": "550e8400-e29b-41d4-a716-446655440000",
  "n_results": 10,
  "include_metadata": true
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440000",
      "distance": 0.1234,
      "metadata": {
        "modality": "image",
        "filename": "sunset.jpg",
        "added_at": "2025-01-06T12:00:00.000000"
      }
    },
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "distance": 0.2345,
      "metadata": {
        "modality": "video",
        "filename": "beach.mp4",
        "added_at": "2025-01-06T11:00:00.000000"
      }
    }
  ],
  "query_modality": "text",
  "total_results": 2
}
```

**Example**:
```bash
# Text-based search
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store_name": "my_store",
    "query_modality": "text",
    "query_text": "sunset beach",
    "n_results": 5
  }'

# Image-based search
FILE_ID=$(curl -X POST http://localhost:8000/api/upload \
  -F "file=@query.jpg" \
  -F "modality=image" | jq -r '.file_id')

curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d "{
    \"vector_store_name\": \"my_store\",
    \"query_modality\": \"image\",
    \"query_file_id\": \"$FILE_ID\",
    \"n_results\": 10
  }"
```

**Distance Interpretation**:
- Lower distance = more similar
- Distance range: 0 to ~2
- Typical similar items: distance < 0.5

---

## Complete Workflow Examples

### Example 1: Image Similarity Search

```bash
# 1. Create vector store
curl -X POST http://localhost:8000/api/vector-stores \
  -H "Content-Type: application/json" \
  -d '{"name": "image_db", "description": "Image embeddings"}'

# 2. Upload and add images
for img in image1.jpg image2.jpg image3.jpg; do
  FILE_ID=$(curl -X POST http://localhost:8000/api/upload \
    -F "file=@$img" \
    -F "modality=image" | jq -r '.file_id')

  curl -X POST http://localhost:8000/api/embeddings \
    -H "Content-Type: application/json" \
    -d "{
      \"vector_store_name\": \"image_db\",
      \"operation\": \"use_existing\",
      \"modality\": \"image\",
      \"file_id\": \"$FILE_ID\"
    }"
done

# 3. Search with text query
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store_name": "image_db",
    "query_modality": "text",
    "query_text": "sunset landscape",
    "n_results": 5
  }'
```

### Example 2: Multi-Modal Search

```bash
# Create store
curl -X POST http://localhost:8000/api/vector-stores \
  -H "Content-Type: application/json" \
  -d '{"name": "multi_modal", "description": "Multi-modal store"}'

# Add image
IMG_ID=$(curl -X POST http://localhost:8000/api/upload \
  -F "file=@image.jpg" \
  -F "modality=image" | jq -r '.file_id')
curl -X POST http://localhost:8000/api/embeddings \
  -H "Content-Type: application/json" \
  -d "{\"vector_store_name\": \"multi_modal\", \"operation\": \"use_existing\", \"modality\": \"image\", \"file_id\": \"$IMG_ID\"}"

# Add video
VID_ID=$(curl -X POST http://localhost:8000/api/upload \
  -F "file=@video.mp4" \
  -F "modality=video" | jq -r '.file_id')
curl -X POST http://localhost:8000/api/embeddings \
  -H "Content-Type: application/json" \
  -d "{\"vector_store_name\": \"multi_modal\", \"operation\": \"use_existing\", \"modality\": \"video\", \"file_id\": \"$VID_ID\"}"

# Add audio
AUD_ID=$(curl -X POST http://localhost:8000/api/upload \
  -F "file=@audio.wav" \
  -F "modality=audio" | jq -r '.file_id')
curl -X POST http://localhost:8000/api/embeddings \
  -H "Content-Type: application/json" \
  -d "{\"vector_store_name\": \"multi_modal\", \"operation\": \"use_existing\", \"modality\": \"audio\", \"file_id\": \"$AUD_ID\"}"

# Search across all modalities with text
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector_store_name": "multi_modal",
    "query_modality": "text",
    "query_text": "nature sounds and visuals",
    "n_results": 10
  }'
```

## Error Handling

### Common Error Responses

**400 Bad Request**:
```json
{
  "detail": "Invalid file extension for image modality"
}
```

**404 Not Found**:
```json
{
  "detail": "Vector store 'my_store' not found"
}
```

**500 Internal Server Error**:
```json
{
  "detail": "Failed to generate embedding"
}
```

### Error Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request (validation error) |
| 404 | Resource not found |
| 500 | Internal server error |

## Rate Limiting

Currently, no rate limiting is implemented. For production use, implement rate limiting based on your requirements.

## Python SDK Example

```python
import requests
import json

class EMBEdClient:
    def __init__(self, base_url="http://localhost:8000/api"):
        self.base_url = base_url

    def create_store(self, name, description=None):
        response = requests.post(
            f"{self.base_url}/vector-stores",
            json={"name": name, "description": description}
        )
        return response.json()

    def upload_file(self, file_path, modality):
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {'modality': modality}
            response = requests.post(
                f"{self.base_url}/upload",
                files=files,
                data=data
            )
        return response.json()

    def generate_embedding(self, store_name, modality, file_id=None, text=None):
        payload = {
            "vector_store_name": store_name,
            "operation": "use_existing",
            "modality": modality,
            "file_id": file_id or "text-placeholder",
            "text_content": text
        }
        response = requests.post(
            f"{self.base_url}/embeddings",
            json=payload
        )
        return response.json()

    def search(self, store_name, query_modality, query_text=None, query_file_id=None, n_results=10):
        payload = {
            "vector_store_name": store_name,
            "query_modality": query_modality,
            "query_text": query_text,
            "query_file_id": query_file_id,
            "n_results": n_results
        }
        response = requests.post(
            f"{self.base_url}/search",
            json=payload
        )
        return response.json()

# Usage
client = EMBEdClient()

# Create store
client.create_store("my_images", "Image collection")

# Upload and embed image
result = client.upload_file("image.jpg", "image")
client.generate_embedding("my_images", "image", file_id=result['file_id'])

# Search
results = client.search("my_images", "text", query_text="sunset")
print(json.dumps(results, indent=2))
```

---

**For more information, see the [main README](README.md)**
