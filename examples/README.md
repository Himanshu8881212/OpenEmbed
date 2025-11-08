# EMBEd RAG Application Examples

Complete, production-ready RAG application templates using EMBEd.

## 🎯 Quick Start

### **Switch Between Text-Only and Multi-Modal RAG with One Parameter!**

```bash
# Text-only RAG (like ChatGPT with your documents)
python rag_application.py --mode text --store my_docs --query "What is our vacation policy?"

# Multi-modal RAG (search across text, images, videos)
python rag_application.py --mode multimodal --store my_media --query "Show me red sneakers"
```

**That's it!** The same code works for both text-only and multi-modal RAG.

---

## 📋 Prerequisites

### 1. Install Dependencies

```bash
# Required
pip install requests

# LLM Provider (choose one or both)
pip install openai        # For OpenAI GPT-4
pip install anthropic     # For Anthropic Claude
```

### 2. Set API Keys

```bash
# For OpenAI
export OPENAI_API_KEY="sk-..."

# For Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Start EMBEd Server

```bash
# Using Docker (recommended)
docker-compose up -d

# Or manually
cd /path/to/EMBEd
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 🚀 Usage Examples

### **Example 1: Text-Only RAG (Company Knowledge Base)**

```bash
# Step 1: Create vector store and index documents
python rag_application.py \
  --mode text \
  --store company_kb \
  --create-store \
  --index "documents/*.pdf" "documents/*.txt"

# Step 2: Ask questions
python rag_application.py \
  --mode text \
  --store company_kb \
  --query "What is our vacation policy?"

python rag_application.py \
  --mode text \
  --store company_kb \
  --query "How do I submit expense reports?"
```

**Output:**
```
✅ Initialized EMBEd RAG
   Mode: text
   LLM: openai (gpt-4)
   EMBEd: http://localhost:8000

🔍 Query: What is our vacation policy?
   Store: company_kb
   Mode: text

📚 Retrieving top 5 relevant documents...
✅ Retrieved 5 documents
   1. text: employee_handbook.pdf (95.2%)
   2. text: hr_policies.pdf (87.3%)
   3. text: benefits_guide.pdf (82.1%)

🤖 Generating answer with openai...

================================================================================
📝 ANSWER
================================================================================
Based on the employee handbook, our vacation policy provides:

1. New employees: 10 days per year
2. After 3 years: 15 days per year
3. After 5 years: 20 days per year

Vacation days must be requested at least 2 weeks in advance and approved by
your manager. Unused vacation days can be carried over up to 5 days per year.

================================================================================
📚 Sources: 5 documents
================================================================================
```

---

### **Example 2: Multi-Modal RAG (E-commerce Product Search)**

```bash
# Step 1: Create vector store and index mixed content
python rag_application.py \
  --mode multimodal \
  --store product_catalog \
  --create-store \
  --index \
    "products/descriptions/*.txt" \
    "products/images/*.jpg" \
    "products/videos/*.mp4"

# Step 2: Search across all modalities
python rag_application.py \
  --mode multimodal \
  --store product_catalog \
  --query "red running shoes with good cushioning"

# Step 3: Filter by specific modality
python rag_application.py \
  --mode multimodal \
  --store product_catalog \
  --query "red sneakers" \
  --filter image
```

**Output:**
```
✅ Initialized EMBEd RAG
   Mode: multimodal
   LLM: openai (gpt-4)
   EMBEd: http://localhost:8000

🔍 Query: red running shoes with good cushioning
   Store: product_catalog
   Mode: multimodal

📚 Retrieving top 5 relevant documents...
✅ Retrieved 5 documents
   1. image: nike_air_max_red.jpg (94.5%)
   2. text: nike_air_max_description.txt (91.2%)
   3. video: nike_air_max_demo.mp4 (88.7%)
   4. image: adidas_ultraboost_red.jpg (85.3%)
   5. text: adidas_ultraboost_description.txt (82.1%)

🤖 Generating answer with openai...

================================================================================
📝 ANSWER
================================================================================
Based on the search results, I found several red running shoes with excellent
cushioning:

1. **Nike Air Max** (nike_air_max_red.jpg)
   - Features Air Max cushioning technology
   - Available in vibrant red color
   - See demo video: nike_air_max_demo.mp4

2. **Adidas Ultraboost** (adidas_ultraboost_red.jpg)
   - Boost foam cushioning for maximum comfort
   - Red colorway with white accents
   - Highly rated for long-distance running

Both options provide excellent cushioning and are available in red. The Nike
Air Max offers more traditional cushioning, while the Ultraboost provides
responsive Boost foam technology.

================================================================================
📚 Sources: 5 documents
================================================================================
```

---

### **Example 3: Using as Python Library**

```python
from rag_application import EMBEdRAG

# Initialize RAG (text-only mode)
rag = EMBEdRAG(
    embed_url="http://localhost:8000",
    llm_provider="openai",
    mode="text"  # or "multimodal"
)

# Create vector store
rag.create_vector_store("my_docs", "My document collection")

# Index documents
rag.index_documents("my_docs", [
    "doc1.pdf",
    "doc2.txt",
    "doc3.docx"
])

# Query
result = rag.query(
    store_name="my_docs",
    question="What is the main topic?",
    n_results=5
)

print(result["answer"])
print(f"Sources: {result['n_sources']}")
```

---

### **Example 4: Switch from Text to Multi-Modal**

**Before (Text-Only):**
```python
# Text-only RAG
rag = EMBEdRAG(mode="text")
rag.index_documents("my_store", ["doc1.txt", "doc2.txt"])
result = rag.query("my_store", "What is this about?")
```

**After (Multi-Modal):**
```python
# Multi-modal RAG - JUST CHANGE ONE PARAMETER!
rag = EMBEdRAG(mode="multimodal")  # ← Only change this!
rag.index_documents("my_store", [
    "doc1.txt",
    "image1.jpg",
    "video1.mp4"
])
result = rag.query("my_store", "What is this about?")
```

**That's it!** Everything else stays the same.

---

## 🎯 Command-Line Options

```bash
python rag_application.py [OPTIONS]

Required:
  --store NAME              Vector store name

Optional:
  --mode {text,multimodal}  RAG mode (default: text)
  --query "QUESTION"        Question to ask
  --index FILE [FILE ...]   Files to index (supports glob patterns)
  --llm {openai,anthropic}  LLM provider (default: openai)
  --embed-url URL           EMBEd API URL (default: http://localhost:8000)
  --create-store            Create vector store if it doesn't exist

Examples:
  # Create store and index files
  python rag_application.py --mode text --store docs --create-store --index *.pdf

  # Query existing store
  python rag_application.py --mode text --store docs --query "What is this about?"

  # Multi-modal with Anthropic
  python rag_application.py --mode multimodal --store media --llm anthropic --query "Find red items"
```

---

## 📊 Comparison: Text vs Multi-Modal

| Feature | Text Mode | Multi-Modal Mode |
|---------|-----------|------------------|
| **Input Files** | .txt, .pdf, .docx | .txt, .jpg, .mp4, .mp3, etc. |
| **Search** | Text only | Cross-modal (text → images, etc.) |
| **Context** | Text snippets | Text + file references |
| **Use Cases** | Q&A, knowledge base | Product search, media libraries |
| **Code Change** | `mode="text"` | `mode="multimodal"` |

---

## 🔧 Advanced Usage

### Custom System Prompt

```python
rag = EMBEdRAG(mode="text")

result = rag.query(
    store_name="my_docs",
    question="Summarize the key points",
    n_results=10
)

# Or customize in code:
answer = rag.generate_answer(
    query="What are the main topics?",
    context=context,
    system_prompt="You are a technical documentation expert. Provide detailed, accurate answers."
)
```

### Filter by Modality (Multi-Modal Only)

```python
# Only search images
results = rag.retrieve(
    store_name="my_media",
    query="red sneakers",
    modality_filter="image"
)

# Only search videos
results = rag.retrieve(
    store_name="my_media",
    query="product demo",
    modality_filter="video"
)
```

### Batch Indexing

```python
from pathlib import Path

# Index entire directory
files = [str(f) for f in Path("documents").rglob("*") if f.is_file()]
rag.index_documents("my_store", files)
```

---

## 🎓 How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ 1. INDEXING                                                  │
│    Your Files → EMBEd → ImageBind → ChromaDB                │
│                        (1024-dim embeddings)                 │
├─────────────────────────────────────────────────────────────┤
│ 2. RETRIEVAL                                                 │
│    User Query → EMBEd → ImageBind → Search ChromaDB         │
│                        (query embedding)                     │
├─────────────────────────────────────────────────────────────┤
│ 3. GENERATION                                                │
│    Retrieved Context + Query → OpenAI/Claude → Answer       │
└─────────────────────────────────────────────────────────────┘
```

### Key Points

✅ **EMBEd handles all embeddings** - You don't manage ImageBind  
✅ **Same model for indexing and retrieval** - Consistent embeddings  
✅ **Any LLM for generation** - OpenAI, Claude, Llama, etc.  
✅ **One parameter to switch modes** - `mode="text"` or `mode="multimodal"`  

---

## 🐛 Troubleshooting

### "EMBEd server not responding"
```bash
# Check if EMBEd is running
curl http://localhost:8000/api/health

# Start EMBEd
docker-compose up -d
```

### "OpenAI API key not found"
```bash
# Set API key
export OPENAI_API_KEY="sk-..."

# Or use .env file
echo "OPENAI_API_KEY=sk-..." > .env
```

### "Vector store not found"
```bash
# Create store first
python rag_application.py --store my_docs --create-store
```

---

## 📚 Additional Resources

- **EMBEd Documentation**: [../README.md](../README.md)
- **Python SDK**: [../sdk/python/README.md](../sdk/python/README.md)
- **API Documentation**: http://localhost:8000/docs

---

## 🤝 Contributing

Have a cool RAG example? Submit a PR!

---

**Built with ❤️ for the AI community**

