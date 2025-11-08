"""
Pytest configuration and fixtures for OpenEmbed tests.
"""
import pytest
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test configuration
TEST_BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
TEST_FILES_DIR = Path(__file__).parent.parent / "test_files"


@pytest.fixture(scope="session")
def base_url():
    """Base URL for API tests."""
    return TEST_BASE_URL


@pytest.fixture(scope="session")
def test_files_dir():
    """Directory containing test files."""
    return TEST_FILES_DIR


@pytest.fixture(scope="function")
def cleanup_stores():
    """Cleanup vector stores after each test."""
    yield
    # Cleanup code here if needed
    pass


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment before running tests."""
    # Ensure test files directory exists
    TEST_FILES_DIR.mkdir(exist_ok=True)
    
    # Create minimal test files if they don't exist
    test_files = {
        "sample_text.txt": "This is a test text file for machine learning and AI.",
        "test_sunset_ocean.txt": "A beautiful sunset over the ocean with waves.",
    }
    
    for filename, content in test_files.items():
        file_path = TEST_FILES_DIR / filename
        if not file_path.exists():
            file_path.write_text(content)
    
    yield
    
    # Cleanup after all tests
    pass

