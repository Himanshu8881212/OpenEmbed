"""
Tests for SQLite database service.
"""
import pytest
import os
from pathlib import Path
from app.services.database_service import DatabaseService


@pytest.fixture
def test_db():
    """Create a test database instance."""
    # Use a test database file
    test_db_path = Path("./test_analytics.db")
    
    # Remove if exists
    if test_db_path.exists():
        test_db_path.unlink()
    
    # Create test database service
    db = DatabaseService()
    db.db_path = test_db_path
    db.initialize()
    
    yield db
    
    # Cleanup
    if test_db_path.exists():
        test_db_path.unlink()


class TestDatabaseInitialization:
    """Test database initialization."""
    
    def test_initialize_database(self, test_db):
        """Test database initialization creates tables."""
        assert test_db._initialized is True
        assert test_db.db_path.exists()
        
        # Check tables exist
        with test_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                ORDER BY name
            """)
            tables = [row['name'] for row in cursor.fetchall()]
            
            assert 'vector_stores' in tables
            assert 'file_uploads' in tables
            assert 'search_analytics' in tables


class TestVectorStoreOperations:
    """Test vector store CRUD operations."""
    
    def test_create_vector_store(self, test_db):
        """Test creating a vector store record."""
        success = test_db.create_vector_store(
            name="test_store",
            description="Test store",
            metadata={"key": "value"}
        )
        assert success is True
        
        # Verify it was created
        store = test_db.get_vector_store("test_store")
        assert store is not None
        assert store['name'] == "test_store"
        assert store['description'] == "Test store"
    
    def test_create_duplicate_store(self, test_db):
        """Test creating duplicate store fails gracefully."""
        test_db.create_vector_store(name="test_store")
        success = test_db.create_vector_store(name="test_store")
        assert success is False
    
    def test_list_vector_stores(self, test_db):
        """Test listing vector stores."""
        test_db.create_vector_store(name="store1")
        test_db.create_vector_store(name="store2")
        
        stores = test_db.list_vector_stores()
        assert len(stores) == 2
        assert any(s['name'] == 'store1' for s in stores)
        assert any(s['name'] == 'store2' for s in stores)
    
    def test_delete_vector_store(self, test_db):
        """Test deleting a vector store."""
        test_db.create_vector_store(name="test_store")
        success = test_db.delete_vector_store("test_store")
        assert success is True
        
        # Verify it was deleted
        store = test_db.get_vector_store("test_store")
        assert store is None


class TestFileUploadOperations:
    """Test file upload tracking."""
    
    def test_record_file_upload(self, test_db):
        """Test recording a file upload."""
        # Create store first
        test_db.create_vector_store(name="test_store")
        
        success = test_db.record_file_upload(
            file_id="file123",
            embedding_id="emb123",
            filename="test.txt",
            modality="text",
            size_bytes=1024,
            vector_store="test_store"
        )
        assert success is True
    
    def test_get_store_file_count(self, test_db):
        """Test getting file count for a store."""
        test_db.create_vector_store(name="test_store")
        
        # Add some files
        test_db.record_file_upload("file1", "emb1", "test1.txt", "text", 100, "test_store")
        test_db.record_file_upload("file2", "emb2", "test2.txt", "text", 200, "test_store")
        test_db.record_file_upload("file3", "emb3", "test3.jpg", "image", 300, "test_store")
        
        count = test_db.get_store_file_count("test_store")
        assert count == 3
    
    def test_get_store_size(self, test_db):
        """Test getting total size for a store."""
        test_db.create_vector_store(name="test_store")
        
        test_db.record_file_upload("file1", "emb1", "test1.txt", "text", 100, "test_store")
        test_db.record_file_upload("file2", "emb2", "test2.txt", "text", 200, "test_store")
        
        size = test_db.get_store_size("test_store")
        assert size == 300
    
    def test_get_store_modality_counts(self, test_db):
        """Test getting modality counts for a store."""
        test_db.create_vector_store(name="test_store")
        
        test_db.record_file_upload("file1", "emb1", "test1.txt", "text", 100, "test_store")
        test_db.record_file_upload("file2", "emb2", "test2.txt", "text", 200, "test_store")
        test_db.record_file_upload("file3", "emb3", "test3.jpg", "image", 300, "test_store")
        test_db.record_file_upload("file4", "emb4", "test4.mp4", "video", 400, "test_store")
        
        counts = test_db.get_store_modality_counts("test_store")
        assert counts['text'] == 2
        assert counts['image'] == 1
        assert counts['video'] == 1
    
    def test_cascade_delete(self, test_db):
        """Test that deleting a store deletes its files."""
        test_db.create_vector_store(name="test_store")
        test_db.record_file_upload("file1", "emb1", "test1.txt", "text", 100, "test_store")
        
        # Delete store
        test_db.delete_vector_store("test_store")
        
        # Files should be deleted too
        files = test_db.get_files_by_store("test_store")
        assert len(files) == 0


class TestSearchAnalytics:
    """Test search analytics tracking."""
    
    def test_record_search(self, test_db):
        """Test recording a search."""
        test_db.create_vector_store(name="test_store")
        
        success = test_db.record_search(
            vector_store="test_store",
            query_modality="text",
            query_text="test query",
            results_count=5
        )
        assert success is True
    
    def test_get_search_stats(self, test_db):
        """Test getting search statistics."""
        test_db.create_vector_store(name="test_store")
        
        # Record some searches
        test_db.record_search("test_store", "text", "query1", 5)
        test_db.record_search("test_store", "text", "query2", 3)
        test_db.record_search("test_store", "image", None, 7)
        
        stats = test_db.get_search_stats(vector_store="test_store", days=7)
        
        assert stats['total_searches'] == 3
        assert stats['by_modality']['text'] == 2
        assert stats['by_modality']['image'] == 1
        assert stats['avg_results_per_search'] == 5.0  # (5+3+7)/3


class TestSystemAnalytics:
    """Test system-wide analytics."""
    
    def test_get_system_stats(self, test_db):
        """Test getting system-wide statistics."""
        # Create stores and add files
        test_db.create_vector_store(name="store1")
        test_db.create_vector_store(name="store2")
        
        test_db.record_file_upload("file1", "emb1", "test1.txt", "text", 100, "store1")
        test_db.record_file_upload("file2", "emb2", "test2.jpg", "image", 200, "store1")
        test_db.record_file_upload("file3", "emb3", "test3.txt", "text", 300, "store2")
        
        stats = test_db.get_system_stats()
        
        assert stats['total_stores'] == 2
        assert stats['total_files'] == 3
        assert stats['total_size_bytes'] == 600
        assert stats['modalities']['text'] == 2
        assert stats['modalities']['image'] == 1

