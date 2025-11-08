# EMBEd RAG Application - Deployment Guide

This guide covers three deployment options for the EMBEd RAG application.

---

## 📋 **Prerequisites**

### **Required:**
- Python 3.9+
- LM Studio (or OpenAI/Anthropic API key)
- 8GB+ RAM (16GB recommended for local deployment)

### **For Docker Deployment:**
- Docker Desktop with 12GB+ memory allocation
- Note: Docker deployment may have memory issues on some systems

---

## 🚀 **Option 1: Local Deployment (RECOMMENDED)**

This is the most reliable option and what we tested successfully.

### **Step 1: Install Dependencies**

```bash
cd /path/to/EMBEd
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install openai  # For LM Studio integration
```

### **Step 2: Start EMBEd Server**

```bash
# Start on default port 8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or use a different port if 8000 is busy
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

**Wait 60-90 seconds** for the ImageBind model to load. You'll see:
```
✅ ImageBind service initialized successfully
✅ Device: mps (or cpu/cuda)
✅ All 7 modalities ready: text, image, video, audio, depth, thermal, IMU
```

### **Step 3: Start LM Studio**

1. Open LM Studio
2. Load model: `qwen/qwen3-vl-4b` (or any other model)
3. Start server on port 1234
4. Verify it's running: `curl http://localhost:1234/v1/models`

### **Step 4: Build Vector Store**

```bash
cd examples
python build_multimodal_store.py
```

This creates a vector store named `multimodal_demo` with sample data.

### **Step 5: Run RAG Application**

```bash
# If EMBEd is on port 8000
python rag_application.py \
  --mode multimodal \
  --store multimodal_demo \
  --llm lmstudio \
  --llm-model 'qwen/qwen3-vl-4b' \
  --query "What is artificial intelligence?"

# If EMBEd is on port 8001
python rag_application.py \
  --embed-url http://localhost:8001 \
  --mode multimodal \
  --store multimodal_demo \
  --llm lmstudio \
  --llm-model 'qwen/qwen3-vl-4b' \
  --query "What is artificial intelligence?"
```

### **Step 6: Run Tests**

```bash
# Update test_rag_lmstudio.py if using port 8001
# Change line 68: http://localhost:8001
# Change line 105: http://localhost:8001

python test_rag_lmstudio.py
```

**Expected Output:**
```
✅ All tests passed!
Total Tests: 5
Successful: 5
Failed: 0
Success Rate: 100.0%
```

---

## 🐳 **Option 2: Docker Deployment**

**⚠️ Warning:** Docker deployment may encounter memory issues (OOM kills) when loading the ImageBind model. If you experience this, use local deployment instead.

### **Step 1: Increase Docker Memory**

1. Open Docker Desktop
2. Go to Settings → Resources
3. Set Memory to **12GB or higher**
4. Click "Apply & Restart"

### **Step 2: Start Docker Container**

```bash
cd /path/to/EMBEd
docker compose up -d
```

### **Step 3: Wait for Model to Load**

```bash
# Wait 2-3 minutes, then check logs
docker compose logs --tail=50

# Look for this message:
# ✅ All 7 modalities ready: text, image, video, audio, depth, thermal, IMU
```

### **Step 4: Verify Health**

```bash
curl http://localhost:8000/api/health | python3 -m json.tool
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "models_loaded": true,
  "vector_store_connected": true
}
```

### **Step 5: Run RAG Application**

Same as local deployment, but EMBEd will be on port 8000:

```bash
cd examples
python rag_application.py \
  --mode multimodal \
  --store multimodal_demo \
  --llm lmstudio \
  --llm-model 'qwen/qwen3-vl-4b' \
  --query "Your question here"
```

### **Troubleshooting Docker**

**Container keeps restarting (exit code 137):**
- This is an Out-Of-Memory (OOM) error
- Increase Docker memory to 16GB
- Or use local deployment instead

**Model loading takes too long:**
- First run downloads 2.4GB model
- Subsequent runs should be faster (model is cached)

**Check container status:**
```bash
docker ps -a | grep embed
docker compose logs --tail=100
```

---

## 🌐 **Option 3: Production Deployment**

For production use with cloud LLMs (OpenAI/Anthropic):

### **With OpenAI:**

```bash
export OPENAI_API_KEY="your-api-key"

python rag_application.py \
  --mode multimodal \
  --store your_store \
  --llm openai \
  --llm-model gpt-4 \
  --query "Your question"
```

### **With Anthropic:**

```bash
export ANTHROPIC_API_KEY="your-api-key"

python rag_application.py \
  --mode multimodal \
  --store your_store \
  --llm anthropic \
  --llm-model claude-3-opus-20240229 \
  --query "Your question"
```

---

## 📊 **Comparison**

| Feature | Local | Docker | Production |
|---------|-------|--------|------------|
| **Reliability** | ✅ Excellent | ⚠️ May have OOM issues | ✅ Excellent |
| **Setup Time** | 5 minutes | 10 minutes | 5 minutes |
| **Memory Usage** | 6-8GB | 12GB+ | 6-8GB |
| **Model Load Time** | 60-90 seconds | 2-3 minutes | 60-90 seconds |
| **Best For** | Development, Testing | Isolated environments | Production apps |

---

## ✅ **Verified Working Configuration**

This configuration was tested and verified to work 100%:

- **EMBEd**: Local server on port 8001
- **LLM**: LM Studio with qwen/qwen3-vl-4b on port 1234
- **Vector Store**: multimodal_demo with 10 sample files
- **Test Results**: 5/5 queries successful (100%)
- **Device**: Apple MPS (Metal Performance Shaders)
- **Memory**: 8GB system RAM

---

## 🎯 **Quick Start (Fastest Path)**

```bash
# 1. Start EMBEd
cd /path/to/EMBEd
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 &

# 2. Wait 90 seconds for model to load
sleep 90

# 3. Start LM Studio (GUI)
# Load qwen/qwen3-vl-4b and start server

# 4. Build vector store
cd examples
python build_multimodal_store.py

# 5. Run test
python test_rag_lmstudio.py

# Expected: ✅ All tests passed!
```

---

## 📝 **Notes**

1. **Port Conflicts**: If port 8000 is busy, use 8001 and update the examples
2. **Model Loading**: First run downloads 2.4GB ImageBind model
3. **LM Studio**: Any model works, but qwen/qwen3-vl-4b is tested
4. **Memory**: Local deployment uses less memory than Docker
5. **Performance**: MPS (Apple Silicon) is faster than CPU

---

## 🆘 **Getting Help**

If you encounter issues:

1. Check EMBEd server logs
2. Check LM Studio is running: `curl http://localhost:1234/v1/models`
3. Verify EMBEd health: `curl http://localhost:8001/api/health`
4. Check memory usage: `docker stats` (for Docker)
5. Try local deployment if Docker fails

---

**Last Updated**: 2025-11-08  
**Tested Configuration**: Local deployment with LM Studio  
**Success Rate**: 100% (5/5 tests passed)

