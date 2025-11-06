#!/usr/bin/env python3
"""
Verification script for EMBEd installation.
Checks all dependencies, files, and configuration.
"""

import sys
import os
from pathlib import Path
import importlib

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_success(msg):
    print(f"{GREEN}✓{RESET} {msg}")

def print_error(msg):
    print(f"{RED}✗{RESET} {msg}")

def print_warning(msg):
    print(f"{YELLOW}⚠{RESET} {msg}")

def print_info(msg):
    print(f"{BLUE}ℹ{RESET} {msg}")

def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version >= (3, 10):
        print_success(f"Python version: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(f"Python version {version.major}.{version.minor} is too old. Required: 3.10+")
        return False

def check_dependencies():
    """Check required Python packages."""
    required = [
        'fastapi',
        'uvicorn',
        'pydantic',
        'chromadb',
        'torch',
        'torchvision',
        'transformers',
        'loguru',
        'aiofiles',
        'PIL',
        'cv2',
    ]

    print_info("\nChecking Python dependencies...")
    all_ok = True

    for package in required:
        try:
            if package == 'PIL':
                importlib.import_module('PIL')
            elif package == 'cv2':
                importlib.import_module('cv2')
            else:
                importlib.import_module(package)
            print_success(f"{package} installed")
        except ImportError:
            print_error(f"{package} NOT installed")
            all_ok = False

    return all_ok

def check_project_structure():
    """Check if all required files and directories exist."""
    print_info("\nChecking project structure...")

    required_files = [
        'requirements.txt',
        'README.md',
        'QUICKSTART.md',
        'INSTALL.md',
        'API_GUIDE.md',
        'Dockerfile',
        'docker-compose.yml',
        '.env.example',
        '.gitignore',
        'run.sh',
        'run.bat',
        'app/__init__.py',
        'app/main.py',
        'app/core/config.py',
        'app/core/logger.py',
        'app/api/routes.py',
        'app/models/schemas.py',
        'app/services/languagebind_service.py',
        'app/services/chroma_service.py',
        'app/utils/file_handler.py',
        'static/css/style.css',
        'static/js/app.js',
        'templates/index.html',
    ]

    required_dirs = [
        'app',
        'app/api',
        'app/core',
        'app/models',
        'app/services',
        'app/utils',
        'static',
        'static/css',
        'static/js',
        'templates',
        'tests',
    ]

    all_ok = True

    # Check files
    for file_path in required_files:
        if Path(file_path).exists():
            print_success(f"File: {file_path}")
        else:
            print_error(f"File missing: {file_path}")
            all_ok = False

    # Check directories
    for dir_path in required_dirs:
        if Path(dir_path).is_dir():
            print_success(f"Directory: {dir_path}")
        else:
            print_error(f"Directory missing: {dir_path}")
            all_ok = False

    return all_ok

def check_configuration():
    """Check configuration files."""
    print_info("\nChecking configuration...")

    # Check if .env exists
    if Path('.env').exists():
        print_success(".env file exists")
    else:
        print_warning(".env file not found (will be created from .env.example on first run)")

    # Check .env.example
    if Path('.env.example').exists():
        print_success(".env.example exists")
        return True
    else:
        print_error(".env.example missing")
        return False

def check_cuda():
    """Check CUDA availability."""
    print_info("\nChecking CUDA support...")

    try:
        import torch
        if torch.cuda.is_available():
            print_success(f"CUDA available: {torch.cuda.get_device_name(0)}")
            print_info(f"  CUDA version: {torch.version.cuda}")
            print_info(f"  Number of GPUs: {torch.cuda.device_count()}")
            return True
        else:
            print_warning("CUDA not available (will use CPU - slower performance)")
            return False
    except ImportError:
        print_error("PyTorch not installed - cannot check CUDA")
        return False

def check_disk_space():
    """Check available disk space."""
    print_info("\nChecking disk space...")

    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        free_gb = free // (2**30)

        if free_gb >= 15:
            print_success(f"Available disk space: {free_gb} GB")
            return True
        elif free_gb >= 10:
            print_warning(f"Available disk space: {free_gb} GB (minimum 15 GB recommended)")
            return True
        else:
            print_error(f"Available disk space: {free_gb} GB (need at least 10 GB)")
            return False
    except Exception as e:
        print_warning(f"Could not check disk space: {e}")
        return True

def create_directories():
    """Create necessary directories if they don't exist."""
    print_info("\nCreating directories...")

    dirs = ['logs', 'cache_dir', 'model_cache', 'chroma_db', 'uploads']

    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
        print_success(f"Directory ready: {dir_name}")

def check_ports():
    """Check if default port is available."""
    print_info("\nChecking port availability...")

    import socket

    port = 8000
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()

        if result != 0:
            print_success(f"Port {port} is available")
            return True
        else:
            print_warning(f"Port {port} is already in use (configure different port in .env)")
            return True
    except Exception as e:
        print_warning(f"Could not check port: {e}")
        return True

def main():
    """Main verification routine."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}EMBEd Installation Verification{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    results = {
        'Python Version': check_python_version(),
        'Dependencies': check_dependencies(),
        'Project Structure': check_project_structure(),
        'Configuration': check_configuration(),
        'CUDA Support': check_cuda(),
        'Disk Space': check_disk_space(),
        'Port Availability': check_ports(),
    }

    # Create directories
    create_directories()

    # Summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Verification Summary{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    all_passed = all(results.values())

    for check, passed in results.items():
        if passed:
            print_success(f"{check}: PASSED")
        else:
            print_error(f"{check}: FAILED")

    print(f"\n{BLUE}{'='*60}{RESET}\n")

    if all_passed:
        print_success("All checks passed! ✨")
        print_info("\nNext steps:")
        print("  1. Copy .env.example to .env and configure if needed")
        print("  2. Run: ./run.sh (Linux/macOS) or run.bat (Windows)")
        print("  3. Access: http://localhost:8000")
        print("  4. See QUICKSTART.md for usage examples\n")
        return 0
    else:
        print_error("Some checks failed. Please review errors above.")
        print_info("\nTo fix issues:")
        print("  1. Install missing dependencies: pip install -r requirements.txt")
        print("  2. Check Python version: python3 --version")
        print("  3. See INSTALL.md for detailed instructions\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
