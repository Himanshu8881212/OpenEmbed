# OpenEmbed Python SDK

Official Python client for **OpenEmbed** - Multi-Modal Embedding Warehouse

## Installation

```bash
pip install requests
```

Then copy `openembed.py` to your project or install from source:

```bash
cd sdk/python
pip install -e .
```

## Quick Start

```python
from openembed import OpenEmbedClient

# Initialize client
client = OpenEmbedClient("http://localhost:8000")

# Search with text
results = client.search("my_store", "beautiful sunset images")
for result in results:
    print(f"{result['metadata']['filename']}: {result['similarity']:.1%}")

# Upload a file
client.upload("my_store", "image.jpg", "image")

# List all stores
stores = client.list_stores()
print(f"Total stores: {len(stores)}")
```

## API Reference

### Client Initialization

```python
client = OpenEmbedClient(
    base_url="http://localhost:8000",  # OpenEmbed API URL
    timeout=30                          # Request timeout in seconds
)
```

### Search Methods

#### `search(vector_store, query, n_results=10, modality_filter=None)`

Unified search interface - automatically detects text or file queries.

```python
# Text search
results = client.search("my_store", "sunset images", n_results=5)

# File search
from pathlib import Path
results = client.search("my_store", Path("query_image.jpg"))
```

#### `search_by_text(vector_store, text, n_results=10, modality_filter=None)`

Search using text query.

```python
results = client.search_by_text(
    vector_store="my_store",
    text="beautiful sunset over ocean",
    n_results=10,
    modality_filter="image"  # Optional: filter by modality
)
```

#### `search_by_file(vector_store, file_path, n_results=10, modality_filter=None)`

Search using uploaded file.

```python
results = client.search_by_file(
    vector_store="my_store",
    file_path="query_image.jpg",
    n_results=5
)
```

### Upload Methods

#### `upload(vector_store, file_path, modality)`

Upload and embed a single file.

```python
result = client.upload(
    vector_store="my_store",
    file_path="document.pdf",
    modality="text"
)
print(f"Uploaded: {result['filename']}, ID: {result['embedding_id']}")
```

**Supported Modalities:**
- `text` - Text documents (.txt, .md, .json, .csv)
- `image` - Images (.jpg, .png, .gif, .webp)
- `video` - Videos (.mp4, .avi, .mov, .mkv)
- `audio` - Audio files (.wav, .mp3, .flac, .m4a)
- `depth` - Depth maps (.png, .jpg, .tiff)
- `thermal` - Thermal images (.png, .jpg, .tiff)
- `imu` - IMU data (.csv, .json, .txt)

#### `upload_batch(vector_store, file_paths)`

Upload multiple files with auto-detected modalities.

```python
files = ["image1.jpg", "audio.mp3", "text.txt"]
result = client.upload_batch("my_store", files)
print(f"Uploaded {result['successful']} files")
```

### Vector Store Methods

#### `list_stores()`

List all vector stores.

```python
stores = client.list_stores()
for store in stores:
    print(f"{store['name']}: {store['count']} files, {store['size_bytes']} bytes")
```

#### `create_store(name, description=None)`

Create a new vector store.

```python
store = client.create_store(
    name="my_new_store",
    description="Store for product images"
)
```

#### `get_store(name)`

Get vector store information.

```python
store = client.get_store("my_store")
print(f"Files: {store['count']}, Size: {store['size_bytes']} bytes")
```

#### `delete_store(name)`

Delete a vector store.

```python
client.delete_store("old_store")
```

#### `get_files(vector_store)`

Get all files in a vector store.

```python
files = client.get_files("my_store")
for file in files:
    print(f"{file['filename']} ({file['modality']})")
```

### File Methods

#### `download(modality, file_id, output_path)`

Download a file from the vector store.

```python
client.download(
    modality="image",
    file_id="abc-123-def",
    output_path="downloaded_image.jpg"
)
```

#### `health()`

Check API health status.

```python
status = client.health()
print(f"Status: {status['status']}")
```

## Complete Example

```python
from openembed import OpenEmbedClient
from pathlib import Path

# Initialize
client = OpenEmbedClient("http://localhost:8000")

# Create a new store
store = client.create_store("product_images", "E-commerce product catalog")

# Upload files
files = list(Path("products").glob("*.jpg"))
result = client.upload_batch("product_images", files)
print(f"Uploaded {result['successful']} product images")

# Search for similar products
query = "red sneakers"
results = client.search("product_images", query, n_results=10)

print(f"\nTop 10 results for '{query}':")
for i, result in enumerate(results, 1):
    filename = result['metadata']['filename']
    similarity = result['similarity']
    print(f"{i}. {filename} ({similarity:.1%} match)")
    
    # Download top result
    if i == 1:
        client.download(
            modality=result['modality'],
            file_id=result['metadata']['file_id'],
            output_path=f"top_match_{filename}"
        )
```

## Error Handling

```python
from openembed import OpenEmbedClient, OpenEmbedError

client = OpenEmbedClient("http://localhost:8000")

try:
    results = client.search("my_store", "query text")
except OpenEmbedError as e:
    print(f"Error: {e}")
```

## Advanced Usage

### RAG Integration

```python
def rag_query(question: str, vector_store: str, n_context: int = 5):
    """Simple RAG implementation."""
    # Retrieve relevant context
    results = client.search(vector_store, question, n_results=n_context)
    
    # Build context
    context = "\n\n".join([
        f"Source {i+1} ({r['metadata']['filename']}):\n{r['metadata'].get('content', '')}"
        for i, r in enumerate(results)
    ])
    
    # Generate response (integrate with your LLM)
    prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    # response = your_llm.generate(prompt)
    
    return {
        "answer": "Generated answer here",
        "sources": results
    }

# Use it
result = rag_query("What are the product features?", "product_docs")
print(result["answer"])
```

## License

MIT License - see LICENSE file for details

## Support

- GitHub: https://github.com/Himanshu8881212/EMBEd
- Issues: https://github.com/Himanshu8881212/EMBEd/issues

