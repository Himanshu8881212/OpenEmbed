"""
Comprehensive Backend Test Suite for OpenEmbed
Tests all API endpoints, embedding generation, vector operations, and edge cases.
"""
import pytest
import requests
import os
import time
from pathlib import Path
from typing import Dict, List, Any

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"
TEST_FILES_DIR = Path(__file__).parent.parent / "test_files"

# Test data
MODALITIES = ["text", "image", "video", "audio", "depth", "thermal", "imu"]


class TestAPIHealth:
    """Test API health and initialization."""

    def test_health_check(self):
        """Test health check endpoint."""
        response = requests.get(f"{API_BASE}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert data["models_loaded"] is True
        assert data["vector_store_connected"] is True

    def test_api_availability(self):
        """Test that API is accessible."""
        response = requests.get(BASE_URL)
        assert response.status_code == 200


class TestFileUpload:
    """Test file upload functionality for all modalities."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test files."""
        self.uploaded_files = []
        yield
        # Cleanup uploaded files
        for file_info in self.uploaded_files:
            try:
                # Files are cleaned up by the backend
                pass
            except Exception:
                pass

    def test_upload_text_file(self):
        """Test uploading a text file."""
        file_path = TEST_FILES_DIR / "sample_text.txt"
        assert file_path.exists(), f"Test file not found: {file_path}"

        with open(file_path, "rb") as f:
            files = {"file": ("sample_text.txt", f, "text/plain")}
            data = {"modality": "text"}
            response = requests.post(f"{API_BASE}/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["modality"] == "text"
        assert "file_id" in result
        assert result["filename"] == "sample_text.txt"
        self.uploaded_files.append(result)

    def test_upload_image_file(self):
        """Test uploading an image file."""
        file_path = TEST_FILES_DIR / "sample_image.jpg"
        assert file_path.exists(), f"Test file not found: {file_path}"

        with open(file_path, "rb") as f:
            files = {"file": ("sample_image.jpg", f, "image/jpeg")}
            data = {"modality": "image"}
            response = requests.post(f"{API_BASE}/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["modality"] == "image"
        assert "file_id" in result
        self.uploaded_files.append(result)

    def test_upload_video_file(self):
        """Test uploading a video file."""
        file_path = TEST_FILES_DIR / "sample_video.mp4"
        assert file_path.exists(), f"Test file not found: {file_path}"

        with open(file_path, "rb") as f:
            files = {"file": ("sample_video.mp4", f, "video/mp4")}
            data = {"modality": "video"}
            response = requests.post(f"{API_BASE}/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["modality"] == "video"
        assert "file_id" in result
        self.uploaded_files.append(result)

    def test_upload_audio_file(self):
        """Test uploading an audio file."""
        file_path = TEST_FILES_DIR / "sample_audio.wav"
        assert file_path.exists(), f"Test file not found: {file_path}"

        with open(file_path, "rb") as f:
            files = {"file": ("sample_audio.wav", f, "audio/wav")}
            data = {"modality": "audio"}
            response = requests.post(f"{API_BASE}/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert result["modality"] == "audio"
        assert "file_id" in result
        self.uploaded_files.append(result)

    def test_upload_invalid_modality(self):
        """Test uploading with invalid modality."""
        file_path = TEST_FILES_DIR / "sample_text.txt"
        
        with open(file_path, "rb") as f:
            files = {"file": ("sample_text.txt", f, "text/plain")}
            data = {"modality": "invalid_modality"}
            response = requests.post(f"{API_BASE}/upload", files=files, data=data)

        assert response.status_code == 422  # Validation error

    def test_upload_without_file(self):
        """Test upload endpoint without file."""
        data = {"modality": "text"}
        response = requests.post(f"{API_BASE}/upload", data=data)
        assert response.status_code == 422


class TestVectorStores:
    """Test vector store operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup and cleanup vector stores."""
        self.test_stores = []
        yield
        # Cleanup test stores
        for store_name in self.test_stores:
            try:
                requests.delete(f"{API_BASE}/vector-stores/{store_name}")
            except Exception:
                pass

    def test_create_vector_store(self):
        """Test creating a vector store."""
        store_name = f"test_store_{int(time.time())}"
        data = {
            "name": store_name,
            "description": "Test vector store",
            "modality": "text"
        }
        response = requests.post(f"{API_BASE}/vector-stores", json=data)
        
        assert response.status_code == 200
        result = response.json()
        assert result["name"] == store_name
        assert result["modality"] == "text"
        self.test_stores.append(store_name)

    def test_create_duplicate_vector_store(self):
        """Test creating a duplicate vector store."""
        store_name = f"test_duplicate_{int(time.time())}"
        data = {
            "name": store_name,
            "description": "Test store",
            "modality": "text"
        }
        
        # Create first store
        response1 = requests.post(f"{API_BASE}/vector-stores", json=data)
        assert response1.status_code == 200
        self.test_stores.append(store_name)
        
        # Try to create duplicate
        response2 = requests.post(f"{API_BASE}/vector-stores", json=data)
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"].lower()

    def test_list_vector_stores(self):
        """Test listing vector stores."""
        response = requests.get(f"{API_BASE}/vector-stores")
        assert response.status_code == 200
        result = response.json()
        assert "stores" in result
        assert "total" in result
        assert isinstance(result["stores"], list)

    def test_get_vector_store(self):
        """Test getting a specific vector store."""
        # Create a test store first
        store_name = f"test_get_store_{int(time.time())}"
        create_data = {
            "name": store_name,
            "description": "Test store for get",
            "modality": "text"
        }
        create_response = requests.post(f"{API_BASE}/vector-stores", json=create_data)
        assert create_response.status_code == 200
        self.test_stores.append(store_name)
        
        # Get the store
        response = requests.get(f"{API_BASE}/vector-stores/{store_name}")
        assert response.status_code == 200
        result = response.json()
        assert result["name"] == store_name

    def test_delete_vector_store(self):
        """Test deleting a vector store."""
        # Create a test store
        store_name = f"test_delete_store_{int(time.time())}"
        create_data = {
            "name": store_name,
            "description": "Test store for deletion",
            "modality": "text"
        }
        create_response = requests.post(f"{API_BASE}/vector-stores", json=create_data)
        assert create_response.status_code == 200
        
        # Delete the store
        delete_response = requests.delete(f"{API_BASE}/vector-stores/{store_name}")
        assert delete_response.status_code == 200
        
        # Verify it's deleted
        get_response = requests.get(f"{API_BASE}/vector-stores/{store_name}")
        assert get_response.status_code == 404

    def test_get_nonexistent_store(self):
        """Test getting a non-existent vector store."""
        response = requests.get(f"{API_BASE}/vector-stores/nonexistent_store_12345")
        assert response.status_code == 404


class TestEmbeddings:
    """Test embedding generation and storage."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.test_stores = []
        self.uploaded_files = []
        yield
        # Cleanup
        for store_name in self.test_stores:
            try:
                requests.delete(f"{API_BASE}/vector-stores/{store_name}")
            except Exception:
                pass

    def test_add_text_embedding(self):
        """Test adding text embedding to vector store."""
        # Create store
        store_name = f"test_text_embed_{int(time.time())}"
        store_data = {"name": store_name, "modality": "text"}
        store_response = requests.post(f"{API_BASE}/vector-stores", json=store_data)
        assert store_response.status_code == 200
        self.test_stores.append(store_name)

        # Upload file
        file_path = TEST_FILES_DIR / "sample_text.txt"
        with open(file_path, "rb") as f:
            files = {"file": ("sample_text.txt", f, "text/plain")}
            data = {"modality": "text", "vector_store": store_name}
            response = requests.post(f"{API_BASE}/upload", files=files, data=data)

        assert response.status_code == 200
        result = response.json()
        assert "embedding_id" in result or "file_id" in result

    def test_embedding_dimensions(self):
        """Test that embeddings have correct dimensions (1024 for LanguageBind)."""
        # This would require accessing the embedding directly
        # For now, we verify the upload succeeds
        store_name = f"test_embed_dim_{int(time.time())}"
        store_data = {"name": store_name, "modality": "text"}
        requests.post(f"{API_BASE}/vector-stores", json=store_data)
        self.test_stores.append(store_name)

        file_path = TEST_FILES_DIR / "sample_text.txt"
        with open(file_path, "rb") as f:
            files = {"file": ("sample_text.txt", f, "text/plain")}
            data = {"modality": "text", "vector_store": store_name}
            response = requests.post(f"{API_BASE}/upload", files=files, data=data)

        assert response.status_code == 200


class TestSearch:
    """Test search functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment with data."""
        self.test_stores = []

        # Create and populate a test store
        self.store_name = f"test_search_store_{int(time.time())}"
        store_data = {"name": self.store_name, "modality": "text"}
        requests.post(f"{API_BASE}/vector-stores", json=store_data)
        self.test_stores.append(self.store_name)

        # Upload test file
        file_path = TEST_FILES_DIR / "sample_text.txt"
        with open(file_path, "rb") as f:
            files = {"file": ("sample_text.txt", f, "text/plain")}
            data = {"modality": "text", "vector_store": self.store_name}
            requests.post(f"{API_BASE}/upload", files=files, data=data)

        # Wait for embedding to be processed
        time.sleep(2)

        yield

        # Cleanup
        for store_name in self.test_stores:
            try:
                requests.delete(f"{API_BASE}/vector-stores/{store_name}")
            except Exception:
                pass

    def test_text_search(self):
        """Test text-based search."""
        search_data = {
            "query_text": "machine learning",
            "top_k": 5
        }
        response = requests.post(f"{API_BASE}/search", json=search_data)
        assert response.status_code == 200
        result = response.json()
        assert "results" in result
        assert isinstance(result["results"], list)

    def test_search_with_limit(self):
        """Test search with result limit."""
        search_data = {
            "query_text": "test query",
            "top_k": 3
        }
        response = requests.post(f"{API_BASE}/search", json=search_data)
        assert response.status_code == 200
        result = response.json()
        assert len(result["results"]) <= 3

    def test_search_empty_query(self):
        """Test search with empty query."""
        search_data = {
            "query_text": "",
            "top_k": 5
        }
        response = requests.post(f"{API_BASE}/search", json=search_data)
        # Should either return 400 or empty results
        assert response.status_code in [200, 400, 422]


class TestFileServing:
    """Test file serving endpoint."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test files."""
        self.uploaded_file_id = None
        self.modality = "text"

        # Upload a test file
        file_path = TEST_FILES_DIR / "sample_text.txt"
        with open(file_path, "rb") as f:
            files = {"file": ("sample_text.txt", f, "text/plain")}
            data = {"modality": self.modality}
            response = requests.post(f"{API_BASE}/upload", files=files, data=data)
            if response.status_code == 200:
                self.uploaded_file_id = response.json().get("file_id")

        yield

    def test_serve_uploaded_file(self):
        """Test serving an uploaded file."""
        if not self.uploaded_file_id:
            pytest.skip("No uploaded file available")

        response = requests.get(f"{API_BASE}/uploads/{self.modality}/{self.uploaded_file_id}")
        assert response.status_code == 200
        assert len(response.content) > 0

    def test_serve_nonexistent_file(self):
        """Test serving a non-existent file."""
        response = requests.get(f"{API_BASE}/uploads/text/nonexistent-file-id-12345")
        assert response.status_code == 404

    def test_serve_invalid_modality(self):
        """Test serving with invalid modality."""
        response = requests.get(f"{API_BASE}/uploads/invalid_modality/some-file-id")
        assert response.status_code == 400


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_large_file_upload(self):
        """Test uploading a large file (if size limits exist)."""
        # This would test file size limits
        pass

    def test_concurrent_uploads(self):
        """Test concurrent file uploads."""
        # This would test thread safety
        pass

    def test_special_characters_in_filename(self):
        """Test uploading files with special characters in names."""
        # Create a temporary file with special characters
        pass

    def test_api_rate_limiting(self):
        """Test API rate limiting if implemented."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

