# Docker Build Instructions

## Overview

This application uses Docker to ensure consistent deployment across different platforms. Special considerations are needed for ARM64/Apple Silicon Macs.

## Prerequisites

- Docker Desktop (with BuildKit enabled)
- 8GB+ RAM allocated to Docker
- 10GB+ free disk space (models are large!)

## Architecture Compatibility

### ARM64/Apple Silicon (M1, M2, M3 Macs)

The Docker build is fully compatible with ARM64/aarch64 architecture. The `decord` video processing library is **automatically built from source** during the Docker build process since pre-built wheels aren't available for ARM64.

### x86_64/AMD64 (Intel Macs, Linux, Windows)

The build works on x86_64 with pre-built wheels for most packages, making it faster.

## Build Instructions

### Clean Build (Recommended)

Always use `--no-cache` to ensure all dependencies are installed correctly:

```bash
# Using docker-compose (recommended)
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Or using docker directly
docker build --no-cache -t embed-embed-app:latest .
docker-compose up -d
```

### Watch Build Progress

```bash
# Watch logs during startup
docker-compose logs -f embed-app

# Expected startup time: 2-5 minutes (first run will download ~3GB of models)
```

## Build Stages

The Dockerfile performs these steps:

1. **System Dependencies** (~30s)
   - Installs build tools (cmake, gcc)
   - Installs FFmpeg and video codecs
   - Required for decord compilation

2. **PyTorch Installation** (~1-2 min)
   - Installs PyTorch 1.13.1 CPU version
   - CRITICAL: Must be 1.13.1 for LanguageBind compatibility

3. **Python Dependencies** (~1-2 min)
   - Installs transformers 4.30.2 and other packages
   - CRITICAL: Must be 4.30.2 for PyTorch 1.13.1 compatibility

4. **Decord Build** (~2-3 min on ARM64, ~30s on x86_64)
   - Clones decord v0.6.0 from source
   - Compiles with CMake (ARM64 only)
   - Installs Python bindings

5. **Application Setup** (~10s)
   - Copies application code
   - Creates directories

## Troubleshooting

### Build Fails on ARM64

**Symptom:** `ERROR: Could not find a version that satisfies the requirement decord==0.6.0`

**Solution:** Already fixed in the Dockerfile! Decord is built from source. Ensure you have:
- Latest Docker Desktop
- BuildKit enabled (default in modern Docker)
- CMake installed in the container (included in Dockerfile)

### Build is Very Slow

**Normal for ARM64:** Building decord from source takes 2-5 minutes depending on CPU cores.

**Speed up:** Use `make -j$(nproc)` (already in Dockerfile) to use all CPU cores.

### Models Don't Download

**Symptom:** Startup hangs or fails with HTTP errors

**Solution:**
1. Check internet connection
2. Models are ~3GB total, first download takes time
3. Models are cached in `./cache_dir` volume

## Verification

After build completes, verify dependencies:

```bash
docker exec -it embed-multimodal python verify_dependencies.py
```

Expected output:
```
✅ torch               Expected: 1.13.1     Actual: 1.13.1+cpu
✅ transformers        Expected: 4.30.2     Actual: 4.30.2
✅ tokenizers          Expected: 0.13.3     Actual: 0.13.3
✅ numpy               Expected: 1.23.0     Actual: 1.23.0
✅ scipy               Expected: 1.10.1     Actual: 1.10.1
✅ opencv-python       Expected: 4.7.0.72   Actual: 4.7.0.72
✅ einops              Expected: 0.6.1      Actual: 0.6.1
✅ decord              Expected: 0.6.0      Actual: 0.6.0
✅ All dependencies verified successfully!
```

## Production Considerations

### For ARM64 Deployment

- Build time will be longer (add 2-3 min for decord compilation)
- Runtime performance is identical to x86_64
- All 6 modalities (text, image, video, audio, depth, thermal) fully supported

### For x86_64 Deployment

- Faster builds (pre-built wheels available)
- Consider GPU support by modifying:
  - Change `DEVICE=cpu` to `DEVICE=cuda:0`
  - Use CUDA-enabled PyTorch base image
  - Add NVIDIA runtime to docker-compose.yml

## Clean Up

```bash
# Stop and remove containers
docker-compose down

# Remove images (force rebuild)
docker rmi embed-embed-app:latest

# Clean up build cache
docker builder prune
```

## Important Notes

⚠️ **DO NOT change PyTorch or transformers versions** without thorough testing. The LanguageBind source code in `app/languagebind/` is tightly coupled to these specific versions.

✅ **Always use `--no-cache`** for production builds to avoid cached layer issues.

🐳 **ARM64 builds work perfectly** - the Dockerfile handles all architecture-specific requirements automatically.
