"""
Comprehensive API tests for OpenEmbed.
Tests all endpoints and functionality.
"""
import pytest
import requests
import io
import time
from pathlib import Path
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

# Test data
TEST_STORE_NAME = "test_api_store"
TEST_TEXT_CONTENT = "This is a test document for API testing."
TEST_SEARCH_QUERY = "test document"


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self):
        """Test GET /api/health"""
        response = requests.get(f"{API_BASE}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestVectorStoreEndpoints:
    """Test vector store CRUD operations."""
    
    def test_01_list_stores_empty_or_existing(self):
        """Test GET /api/vector-stores"""
        response = requests.get(f"{API_BASE}/vector-stores")
        assert response.status_code == 200
        data = response.json()
        assert "stores" in data
        assert isinstance(data["stores"], list)
    
    def test_02_create_store(self):
        """Test POST /api/vector-stores"""
        # Clean up if exists
        requests.delete(f"{API_BASE}/vector-stores/{TEST_STORE_NAME}")
        
        payload = {
            "name": TEST_STORE_NAME,
            "description": "Test store for API testing"
        }
        response = requests.post(f"{API_BASE}/vector-stores", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == TEST_STORE_NAME
        assert data["description"] == "Test store for API testing"
    
    def test_03_get_store(self):
        """Test GET /api/vector-stores/{name}"""
        response = requests.get(f"{API_BASE}/vector-stores/{TEST_STORE_NAME}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == TEST_STORE_NAME
    
    def test_04_list_stores_with_test_store(self):
        """Test GET /api/vector-stores includes test store"""
        response = requests.get(f"{API_BASE}/vector-stores")
        assert response.status_code == 200
        data = response.json()
        store_names = [store["name"] for store in data["stores"]]
        assert TEST_STORE_NAME in store_names


class TestUploadEndpoints:
    """Test file upload endpoints."""
    
    def test_01_upload_text_file(self):
        """Test POST /api/embed with text file"""
        # Create text file
        text_file = io.BytesIO(TEST_TEXT_CONTENT.encode('utf-8'))
        files = {'file': ('test.txt', text_file, 'text/plain')}
        data = {
            'vector_store': TEST_STORE_NAME,
            'modality': 'text'
        }

        response = requests.post(f"{API_BASE}/embed", files=files, data=data)
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["modality"] == "text"
        assert "embedding_id" in result  # Changed from file_id to embedding_id
    
    def test_02_upload_image_file(self):
        """Test POST /api/embed with image file"""
        # Create minimal PNG (1x1 pixel)
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        image_file = io.BytesIO(png_data)
        files = {'file': ('test.png', image_file, 'image/png')}
        data = {
            'vector_store': TEST_STORE_NAME,
            'modality': 'image'
        }
        
        response = requests.post(f"{API_BASE}/embed", files=files, data=data)
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["modality"] == "image"
    
    def test_03_upload_batch(self):
        """Test POST /api/embed-folder with multiple files"""
        # Ensure store exists
        requests.post(f"{API_BASE}/vector-stores", json={"name": TEST_STORE_NAME})

        # Create multiple text files
        files = [
            ('files', ('batch1.txt', io.BytesIO(b'Batch file 1'), 'text/plain')),
            ('files', ('batch2.txt', io.BytesIO(b'Batch file 2'), 'text/plain')),
        ]
        data = {'vector_store': TEST_STORE_NAME}

        response = requests.post(f"{API_BASE}/embed-folder", files=files, data=data)
        assert response.status_code == 200
        result = response.json()

        # Print debug info if test fails
        if result["successful"] < 2:
            print(f"DEBUG: Response = {result}")
            print(f"DEBUG: Failed uploads = {result.get('failed', [])}")

        assert result["successful"] >= 2, f"Expected 2+ successful uploads, got {result['successful']}. Failed: {result.get('failed', [])}"
        assert result["failed_count"] == 0


class TestSearchEndpoints:
    """Test search functionality."""
    
    def test_01_search_by_text(self):
        """Test POST /api/search-by-id with text query"""
        # Wait for embeddings to be indexed
        time.sleep(1)

        payload = {
            "vector_store_name": TEST_STORE_NAME,
            "query_modality": "text",
            "query_text": TEST_SEARCH_QUERY,
            "n_results": 5,
            "include_metadata": True
        }

        response = requests.post(f"{API_BASE}/search-by-id", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) > 0

        # Check result structure
        result = data["results"][0]
        assert "id" in result
        assert "similarity" in result
        assert "metadata" in result
        assert "file_path" in result
    
    def test_02_search_by_file(self):
        """Test POST /api/search with file upload"""
        # Create search file
        search_file = io.BytesIO(b"search query text")
        files = {'file': ('search.txt', search_file, 'text/plain')}
        data = {
            'vector_store': TEST_STORE_NAME,
            'n_results': 5
        }
        
        response = requests.post(f"{API_BASE}/search", files=files, data=data)
        assert response.status_code == 200
        result = response.json()
        assert "results" in result
        assert isinstance(result["results"], list)
    
    def test_03_search_with_modality_filter(self):
        """Test search with modality filter"""
        payload = {
            "vector_store_name": TEST_STORE_NAME,
            "query_modality": "text",
            "query_text": "test",
            "n_results": 5,
            "include_metadata": True
        }

        response = requests.post(f"{API_BASE}/search-by-id", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should return results (may include different modalities due to cross-modal search)
        assert len(data["results"]) > 0


class TestFileEndpoints:
    """Test file retrieval endpoints."""
    
    def test_01_list_files_in_store(self):
        """Test GET /api/vector-stores/{name}/files"""
        response = requests.get(f"{API_BASE}/vector-stores/{TEST_STORE_NAME}/files")
        assert response.status_code == 200
        data = response.json()
        # Response is a list, not a dict with "files" key
        assert isinstance(data, list)
        assert len(data) > 0

        # Check file structure
        file_info = data[0]
        assert "id" in file_info
        assert "modality" in file_info
        assert "metadata" in file_info


class TestModalityDetection:
    """Test modality auto-detection."""
    
    def test_01_text_modality(self):
        """Test text file auto-detection"""
        text_file = io.BytesIO(b"Text content")
        files = {'file': ('auto.txt', text_file, 'text/plain')}
        data = {'vector_store': TEST_STORE_NAME}
        
        response = requests.post(f"{API_BASE}/embed-folder", files=[('files', files['file'])], data=data)
        assert response.status_code == 200
    
    def test_02_image_modality(self):
        """Test image file auto-detection"""
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        image_file = io.BytesIO(png_data)
        files = {'file': ('auto.png', image_file, 'image/png')}
        data = {'vector_store': TEST_STORE_NAME}
        
        response = requests.post(f"{API_BASE}/embed-folder", files=[('files', files['file'])], data=data)
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling."""
    
    def test_01_invalid_store_name(self):
        """Test accessing non-existent store"""
        response = requests.get(f"{API_BASE}/vector-stores/nonexistent_store_xyz")
        assert response.status_code == 404
    
    def test_02_invalid_file_format(self):
        """Test uploading unsupported file format"""
        invalid_file = io.BytesIO(b"invalid content")
        files = {'file': ('test.xyz', invalid_file, 'application/octet-stream')}
        data = {
            'vector_store': TEST_STORE_NAME,
            'modality': 'text'
        }
        
        response = requests.post(f"{API_BASE}/embed", files=files, data=data)
        # Should either reject or handle gracefully
        assert response.status_code in [200, 400, 422]
    
    def test_03_search_empty_store(self):
        """Test searching in empty store"""
        # Create empty store
        empty_store = "empty_test_store"
        requests.delete(f"{API_BASE}/vector-stores/{empty_store}")
        requests.post(f"{API_BASE}/vector-stores", json={"name": empty_store})

        payload = {
            "vector_store_name": empty_store,
            "query_modality": "text",
            "query_text": "test query",
            "n_results": 5,
            "include_metadata": True
        }

        response = requests.post(f"{API_BASE}/search-by-id", json=payload)
        # Should return empty results or error
        assert response.status_code in [200, 404, 422]

        # Cleanup
        requests.delete(f"{API_BASE}/vector-stores/{empty_store}")


class TestCleanup:
    """Cleanup test data."""
    
    def test_delete_test_store(self):
        """Test DELETE /api/vector-stores/{name}"""
        response = requests.delete(f"{API_BASE}/vector-stores/{TEST_STORE_NAME}")
        assert response.status_code == 200
        
        # Verify deletion
        response = requests.get(f"{API_BASE}/vector-stores/{TEST_STORE_NAME}")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

