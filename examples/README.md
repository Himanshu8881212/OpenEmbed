# EMBEd Examples - Get Started with RAG

Simple example to help you quickly set up RAG using EMBEd.

## 🚀 Quick Start

```bash
cd examples
python get_started.py
```

The script will guide you through:
1. ✅ Configuring EMBEd connection
2. ✅ Choosing your LLM provider (LM Studio, OpenAI, or Anthropic)
3. ✅ Creating a vector store
4. ✅ Adding your documents
5. ✅ Asking questions

## 🔧 Using Programmatically

```python
from get_started import SimpleRAG

# Initialize RAG
rag = SimpleRAG(
    embed_url="http://localhost:8000",
    llm_provider="lmstudio",
    llm_url="http://localhost:1234/v1",
    llm_model="qwen/qwen3-vl-4b"
)

# Create vector store and add documents
rag.create_vector_store("my_store", "My knowledge base")
rag.add_documents("my_store", ["doc1.txt", "doc2.pdf", "image1.jpg"])

# Query
result = rag.query("my_store", "What is this about?")
print(result["answer"])
```

## 🤖 LLM Providers

- **LM Studio** (local, free): https://lmstudio.ai
- **OpenAI** (cloud): https://platform.openai.com
- **Anthropic** (cloud): https://console.anthropic.com

## 📊 Supported File Types

EMBEd supports 7 modalities: Text, Image, Video, Audio, Depth, Thermal, IMU

## 🔗 Resources

- [EMBEd Documentation](../README.md)
- [Python SDK](../sdk/python/README.md)
- [GitHub Repository](https://github.com/Himanshu8881212/EMBEd)
