# OpenEmbed SDK

Official SDKs and integration examples for **OpenEmbed** - Multi-Modal Embedding Warehouse

## Available SDKs

### Python SDK

**Location**: `sdk/python/`

**Installation**:
```bash
# Option 1: Copy the SDK file
cp sdk/python/openembed.py your_project/

# Option 2: Install from source
cd sdk/python
pip install -e .
```

**Quick Start**:
```python
from openembed import OpenEmbedClient

client = OpenEmbedClient("http://localhost:8000")
results = client.search("my_store", "find similar images")
```

**Documentation**: See [sdk/python/README.md](python/README.md)

---

## Examples

### Basic Usage

**Location**: `sdk/examples/basic_usage.py`

Demonstrates:
- Text search
- File upload
- Listing stores
- Getting files
- Error handling
- Health checks

**Run**:
```bash
python sdk/examples/basic_usage.py
```

### RAG Integration

**Location**: `sdk/examples/rag_example.py`

Demonstrates:
- Simple RAG pipeline
- Multi-modal RAG
- Context building
- Prompt generation

**Run**:
```bash
python sdk/examples/rag_example.py
```

---

## API Endpoints

### Search

**Text Search**:
```bash
POST /api/search-by-id
{
  "vector_store": "my_store",
  "text": "query text",
  "n_results": 10
}
```

**File Search**:
```bash
POST /api/search
FormData: file, vector_store, n_results
```

### Upload

**Single File**:
```bash
POST /api/embed
FormData: file, vector_store, modality
```

**Batch Upload**:
```bash
POST /api/embed-folder
FormData: files[], vector_store
```

### Vector Stores

**List Stores**:
```bash
GET /api/vector-stores
```

**Create Store**:
```bash
POST /api/vector-stores
{
  "name": "my_store",
  "description": "optional"
}
```

**Get Store Files**:
```bash
GET /api/vector-stores/{name}/files
```

### Files

**Download File**:
```bash
GET /api/uploads/{modality}/{file_id}
```

---

## Supported Modalities

| Modality | Extensions | Use Cases |
|----------|-----------|-----------|
| **text** | .txt, .md, .json, .csv | Documents, articles, data |
| **image** | .jpg, .png, .gif, .webp | Photos, graphics, diagrams |
| **video** | .mp4, .avi, .mov, .mkv | Videos, animations |
| **audio** | .wav, .mp3, .flac, .m4a | Music, speech, sounds |
| **depth** | .png, .jpg, .tiff | Depth maps, 3D data |
| **thermal** | .png, .jpg, .tiff | Thermal imaging |
| **imu** | .csv, .json, .txt | Motion sensor data |

---

## Integration Patterns

### 1. Simple Search

```python
from openembed import OpenEmbedClient

client = OpenEmbedClient("http://localhost:8000")
results = client.search("my_store", "sunset images", n_results=10)

for result in results:
    print(f"{result['metadata']['filename']}: {result['similarity']:.1%}")
```

### 2. RAG Application

```python
def rag_query(question: str):
    # Retrieve context
    results = client.search("knowledge_base", question, n_results=5)
    
    # Build context
    context = "\n".join([r['metadata']['filename'] for r in results])
    
    # Generate with LLM
    prompt = f"Context: {context}\n\nQuestion: {question}\n\nAnswer:"
    # answer = your_llm.generate(prompt)
    
    return {"answer": answer, "sources": results}
```

### 3. Multi-Modal Search

```python
# Search across modalities
text_results = client.search("store", "sunset", modality_filter="text")
image_results = client.search("store", "sunset", modality_filter="image")
audio_results = client.search("store", "sunset", modality_filter="audio")

# Combine results
all_results = text_results + image_results + audio_results
all_results.sort(key=lambda x: x['similarity'], reverse=True)
```

### 4. Batch Upload

```python
from pathlib import Path

# Upload entire folder
files = list(Path("data").glob("**/*"))
file_paths = [str(f) for f in files if f.is_file()]

result = client.upload_batch("my_store", file_paths)
print(f"Uploaded {result['successful']} files")
```

---

## Error Handling

```python
from openembed import OpenEmbedClient, OpenEmbedError

client = OpenEmbedClient("http://localhost:8000")

try:
    results = client.search("my_store", "query")
except OpenEmbedError as e:
    print(f"Error: {e}")
    # Handle error appropriately
```

---

## Best Practices

### 1. Connection Management

```python
# Reuse client instance
client = OpenEmbedClient("http://localhost:8000", timeout=60)

# Use throughout your application
def search_handler(query):
    return client.search("my_store", query)
```

### 2. Batch Operations

```python
# Upload files in batches for better performance
batch_size = 100
for i in range(0, len(files), batch_size):
    batch = files[i:i+batch_size]
    client.upload_batch("my_store", batch)
```

### 3. Modality Filtering

```python
# Filter by modality for better results
image_results = client.search(
    "my_store",
    "sunset",
    modality_filter="image",
    n_results=10
)
```

### 4. Error Recovery

```python
import time

def search_with_retry(query, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.search("my_store", query)
        except OpenEmbedError as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
```

---

## Performance Tips

1. **Batch uploads** - Use `upload_batch()` for multiple files
2. **Reuse connections** - Create one client instance
3. **Filter by modality** - Narrow search scope when possible
4. **Adjust n_results** - Request only what you need
5. **Use timeouts** - Set appropriate timeout values

---

## Support

- **Documentation**: See individual SDK README files
- **Examples**: Check `sdk/examples/` directory
- **Issues**: https://github.com/Himanshu8881212/EMBEd/issues
- **API Docs**: http://localhost:8000/docs (when running)

---

## License

MIT License - see LICENSE file for details

