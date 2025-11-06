# Installation Guide

This guide provides detailed installation instructions for EMBEd on different platforms.

## Table of Contents

- [System Requirements](#system-requirements)
- [Linux Installation](#linux-installation)
- [macOS Installation](#macos-installation)
- [Windows Installation](#windows-installation)
- [Docker Installation](#docker-installation)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements

- **OS**: Linux (Ubuntu 20.04+), macOS (10.15+), or Windows 10/11
- **CPU**: Multi-core processor (4+ cores recommended)
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 15GB free space (for application and models)
- **Python**: 3.10 or higher

### Recommended Requirements

- **GPU**: NVIDIA GPU with 8GB+ VRAM (for optimal performance)
- **CUDA**: 11.6 or higher (if using GPU)
- **RAM**: 16GB or more
- **Storage**: SSD with 20GB+ free space

## Linux Installation

### Ubuntu/Debian

1. **Update system packages**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install system dependencies**:
   ```bash
   sudo apt install -y python3.10 python3.10-venv python3-pip \
     build-essential git ffmpeg libsm6 libxext6 libxrender-dev
   ```

3. **Install CUDA (if using GPU)**:
   ```bash
   # For Ubuntu 22.04
   wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
   sudo dpkg -i cuda-keyring_1.0-1_all.deb
   sudo apt update
   sudo apt install -y cuda
   ```

4. **Clone repository**:
   ```bash
   git clone <repository-url>
   cd EMBEd
   ```

5. **Run installation script**:
   ```bash
   chmod +x run.sh
   ./run.sh
   ```

### CentOS/RHEL/Fedora

1. **Install system dependencies**:
   ```bash
   sudo dnf install -y python3.10 python3-pip git ffmpeg
   ```

2. **Follow steps 4-5 from Ubuntu installation**

## macOS Installation

### Using Homebrew

1. **Install Homebrew** (if not installed):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Install Python and dependencies**:
   ```bash
   brew install python@3.10 ffmpeg
   ```

3. **Clone repository**:
   ```bash
   git clone <repository-url>
   cd EMBEd
   ```

4. **Run installation script**:
   ```bash
   chmod +x run.sh
   ./run.sh
   ```

### Note for M1/M2 Macs

EMBEd can run on Apple Silicon, but GPU acceleration via CUDA is not available. The application will automatically use CPU mode.

For better performance on M1/M2:
```bash
# Install PyTorch with MPS support
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cpu
```

## Windows Installation

### Prerequisites

1. **Install Python 3.10+**:
   - Download from [python.org](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"

2. **Install Git**:
   - Download from [git-scm.com](https://git-scm.com/download/win)

3. **Install Visual C++ Build Tools**:
   - Download from [Microsoft](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
   - Install "Desktop development with C++"

4. **Install FFmpeg**:
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Add FFmpeg to system PATH

### Installation Steps

1. **Open PowerShell or Command Prompt**

2. **Clone repository**:
   ```powershell
   git clone <repository-url>
   cd EMBEd
   ```

3. **Run installation script**:
   ```powershell
   run.bat
   ```

### CUDA Installation (Optional for GPU)

1. Download and install CUDA Toolkit from [NVIDIA](https://developer.nvidia.com/cuda-downloads)
2. Download and install cuDNN from [NVIDIA](https://developer.nvidia.com/cudnn)
3. Add CUDA to system PATH

## Docker Installation

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- NVIDIA Container Toolkit (for GPU support)

### Installing Docker

#### Linux
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

#### macOS
Download and install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)

#### Windows
Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)

### Installing NVIDIA Container Toolkit (for GPU)

```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### Running with Docker

1. **Clone repository**:
   ```bash
   git clone <repository-url>
   cd EMBEd
   ```

2. **Start with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

3. **View logs**:
   ```bash
   docker-compose logs -f
   ```

4. **Stop application**:
   ```bash
   docker-compose down
   ```

## Verification

### Check Installation

1. **Access web interface**:
   Open browser and navigate to: http://localhost:8000

2. **Check API health**:
   ```bash
   curl http://localhost:8000/api/health
   ```

3. **View API documentation**:
   Navigate to: http://localhost:8000/docs

### Expected Output

Health check should return:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "models_loaded": true,
  "vector_store_connected": true,
  "timestamp": "2025-01-06T12:00:00.000000"
}
```

## Troubleshooting

### Issue: Python not found

**Solution**: Ensure Python 3.10+ is installed and in PATH
```bash
python3 --version  # Should show 3.10 or higher
```

### Issue: CUDA not detected

**Solution**:
1. Verify NVIDIA driver installation:
   ```bash
   nvidia-smi
   ```
2. Check CUDA installation:
   ```bash
   nvcc --version
   ```
3. If missing, reinstall CUDA toolkit

### Issue: Out of memory

**Solution**:
1. Use CPU mode by setting in `.env`:
   ```
   DEVICE=cpu
   ```
2. Reduce concurrent requests
3. Increase system RAM/swap

### Issue: Models not downloading

**Solution**:
1. Check internet connection
2. Verify Hugging Face is accessible
3. Manually download models:
   ```python
   from transformers import AutoModel
   AutoModel.from_pretrained("LanguageBind/LanguageBind_Image")
   ```

### Issue: Port 8000 already in use

**Solution**: Change port in `.env`:
```
PORT=8080
```

### Issue: Permission denied on Linux

**Solution**:
```bash
chmod +x run.sh
sudo chown -R $USER:$USER .
```

## Post-Installation

### Configure Environment

1. Edit `.env` file with your settings
2. Configure CUDA device if using GPU:
   ```
   DEVICE=cuda:0
   ```
3. Set appropriate file size limits:
   ```
   MAX_FILE_SIZE=500000000
   ```

### First Run

On first run, the application will:
1. Download LanguageBind models (~10GB)
2. Initialize ChromaDB
3. Create necessary directories

This may take 10-30 minutes depending on internet speed.

### Performance Tuning

For production deployment:
1. Increase worker count in `.env`:
   ```
   WORKERS=4
   ```
2. Enable production mode:
   ```
   DEBUG=False
   ```
3. Configure logging level:
   ```
   LOG_LEVEL=WARNING
   ```

## Getting Help

If you encounter issues not covered here:
1. Check the [main README](README.md)
2. Search existing GitHub issues
3. Create a new issue with:
   - Your OS and version
   - Python version
   - Full error message
   - Steps to reproduce

---

**Next Steps**: See [README.md](README.md) for usage instructions
