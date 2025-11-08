"""
SQLite database service for analytics and store management.
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from app.core.config import settings
from app.core.logger import app_logger as logger


class DatabaseService:
    """Service for managing SQLite database operations."""
    
    def __init__(self):
        """Initialize database service."""
        self.db_path = Path("./analytics.db")
        self._initialized = False
        
    def initialize(self) -> bool:
        """
        Initialize database and create tables.
        
        Returns:
            bool: True if initialization successful
        """
        if self._initialized:
            logger.info("Database already initialized")
            return True
            
        try:
            logger.info(f"Initializing SQLite database at {self.db_path}")
            
            # Create tables
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Vector stores table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vector_stores (
                        name TEXT PRIMARY KEY,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT
                    )
                """)
                
                # File uploads table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS file_uploads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_id TEXT UNIQUE NOT NULL,
                        embedding_id TEXT UNIQUE,
                        filename TEXT NOT NULL,
                        modality TEXT NOT NULL,
                        size_bytes INTEGER,
                        vector_store TEXT NOT NULL,
                        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (vector_store) REFERENCES vector_stores(name) ON DELETE CASCADE
                    )
                """)
                
                # Search analytics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS search_analytics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vector_store TEXT NOT NULL,
                        query_modality TEXT NOT NULL,
                        query_text TEXT,
                        results_count INTEGER,
                        search_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (vector_store) REFERENCES vector_stores(name) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_uploads_vector_store 
                    ON file_uploads(vector_store)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_file_uploads_modality 
                    ON file_uploads(modality)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_analytics_vector_store 
                    ON search_analytics(vector_store)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_analytics_time 
                    ON search_analytics(search_time)
                """)
                
                conn.commit()
                
            logger.info("✅ Database initialized successfully")
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.

        Yields:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        try:
            yield conn
        finally:
            conn.close()
    
    # ==================== Vector Store Operations ====================
    
    def create_vector_store(self, name: str, description: Optional[str] = None, 
                           metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create a new vector store record.
        
        Args:
            name: Store name
            description: Optional description
            metadata: Optional metadata as JSON string
            
        Returns:
            bool: True if created successfully
        """
        try:
            import json
            metadata_str = json.dumps(metadata) if metadata else None
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO vector_stores (name, description, metadata)
                    VALUES (?, ?, ?)
                """, (name, description, metadata_str))
                conn.commit()
                
            logger.info(f"Created vector store record: {name}")
            return True
            
        except sqlite3.IntegrityError:
            logger.warning(f"Vector store {name} already exists")
            return False
        except Exception as e:
            logger.error(f"Failed to create vector store record: {e}")
            return False
    
    def get_vector_store(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get vector store information.
        
        Args:
            name: Store name
            
        Returns:
            Dict with store info or None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM vector_stores WHERE name = ?
                """, (name,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Failed to get vector store: {e}")
            return None
    
    def list_vector_stores(self) -> List[Dict[str, Any]]:
        """
        List all vector stores.
        
        Returns:
            List of store dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM vector_stores ORDER BY created_at DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to list vector stores: {e}")
            return []
    
    def delete_vector_store(self, name: str) -> bool:
        """
        Delete a vector store record.
        
        Args:
            name: Store name
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM vector_stores WHERE name = ?", (name,))
                conn.commit()
                
            logger.info(f"Deleted vector store record: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vector store: {e}")
            return False
    
    # ==================== File Upload Operations ====================
    
    def record_file_upload(self, file_id: str, embedding_id: str, filename: str, 
                          modality: str, size_bytes: int, vector_store: str) -> bool:
        """
        Record a file upload.
        
        Args:
            file_id: Unique file identifier
            embedding_id: Embedding identifier
            filename: Original filename
            modality: File modality
            size_bytes: File size in bytes
            vector_store: Target vector store
            
        Returns:
            bool: True if recorded successfully
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO file_uploads 
                    (file_id, embedding_id, filename, modality, size_bytes, vector_store)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (file_id, embedding_id, filename, modality, size_bytes, vector_store))
                conn.commit()
                
            logger.debug(f"Recorded file upload: {filename} ({modality})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record file upload: {e}")
            return False

    def get_store_file_count(self, vector_store: str) -> int:
        """
        Get total file count for a vector store.

        Args:
            vector_store: Store name

        Returns:
            int: Number of files
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as count FROM file_uploads
                    WHERE vector_store = ?
                """, (vector_store,))
                row = cursor.fetchone()
                return row['count'] if row else 0

        except Exception as e:
            logger.error(f"Failed to get file count: {e}")
            return 0

    def get_store_size(self, vector_store: str) -> int:
        """
        Get total storage size for a vector store.

        Args:
            vector_store: Store name

        Returns:
            int: Total size in bytes
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT SUM(size_bytes) as total_size FROM file_uploads
                    WHERE vector_store = ?
                """, (vector_store,))
                row = cursor.fetchone()
                return row['total_size'] if row and row['total_size'] else 0

        except Exception as e:
            logger.error(f"Failed to get store size: {e}")
            return 0

    def get_store_modality_counts(self, vector_store: str) -> Dict[str, int]:
        """
        Get modality counts for a vector store.

        Args:
            vector_store: Store name

        Returns:
            Dict mapping modality to count
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT modality, COUNT(*) as count
                    FROM file_uploads
                    WHERE vector_store = ?
                    GROUP BY modality
                """, (vector_store,))
                rows = cursor.fetchall()
                return {row['modality']: row['count'] for row in rows}

        except Exception as e:
            logger.error(f"Failed to get modality counts: {e}")
            return {}

    def get_files_by_store(self, vector_store: str) -> List[Dict[str, Any]]:
        """
        Get all files in a vector store.

        Args:
            vector_store: Store name

        Returns:
            List of file dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM file_uploads
                    WHERE vector_store = ?
                    ORDER BY upload_time DESC
                """, (vector_store,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get files: {e}")
            return []

    # ==================== Search Analytics Operations ====================

    def record_search(self, vector_store: str, query_modality: str,
                     query_text: Optional[str], results_count: int) -> bool:
        """
        Record a search operation.

        Args:
            vector_store: Store name
            query_modality: Modality of the query
            query_text: Query text (if applicable)
            results_count: Number of results returned

        Returns:
            bool: True if recorded successfully
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO search_analytics
                    (vector_store, query_modality, query_text, results_count)
                    VALUES (?, ?, ?, ?)
                """, (vector_store, query_modality, query_text, results_count))
                conn.commit()

            logger.debug(f"Recorded search in {vector_store}")
            return True

        except Exception as e:
            logger.error(f"Failed to record search: {e}")
            return False

    def get_search_stats(self, vector_store: Optional[str] = None,
                        days: int = 7) -> Dict[str, Any]:
        """
        Get search statistics.

        Args:
            vector_store: Optional store name to filter by
            days: Number of days to look back

        Returns:
            Dict with search statistics
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                where_clause = ""
                params = []

                if vector_store:
                    where_clause = "WHERE vector_store = ? AND "
                    params.append(vector_store)
                else:
                    where_clause = "WHERE "

                where_clause += "search_time >= datetime('now', '-' || ? || ' days')"
                params.append(days)

                # Total searches
                cursor.execute(f"""
                    SELECT COUNT(*) as total_searches
                    FROM search_analytics
                    {where_clause}
                """, params)
                total_searches = cursor.fetchone()['total_searches']

                # Searches by modality
                cursor.execute(f"""
                    SELECT query_modality, COUNT(*) as count
                    FROM search_analytics
                    {where_clause}
                    GROUP BY query_modality
                """, params)
                by_modality = {row['query_modality']: row['count']
                              for row in cursor.fetchall()}

                # Average results per search
                cursor.execute(f"""
                    SELECT AVG(results_count) as avg_results
                    FROM search_analytics
                    {where_clause}
                """, params)
                avg_results = cursor.fetchone()['avg_results'] or 0

                return {
                    'total_searches': total_searches,
                    'by_modality': by_modality,
                    'avg_results_per_search': round(avg_results, 2),
                    'period_days': days
                }

        except Exception as e:
            logger.error(f"Failed to get search stats: {e}")
            return {}

    # ==================== System Analytics ====================

    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get overall system statistics.

        Returns:
            Dict with system stats
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Total stores
                cursor.execute("SELECT COUNT(*) as count FROM vector_stores")
                total_stores = cursor.fetchone()['count']

                # Total files
                cursor.execute("SELECT COUNT(*) as count FROM file_uploads")
                total_files = cursor.fetchone()['count']

                # Total size
                cursor.execute("SELECT SUM(size_bytes) as total FROM file_uploads")
                total_size = cursor.fetchone()['total'] or 0

                # Files by modality
                cursor.execute("""
                    SELECT modality, COUNT(*) as count
                    FROM file_uploads
                    GROUP BY modality
                """)
                modality_counts = {row['modality']: row['count']
                                  for row in cursor.fetchall()}

                return {
                    'total_stores': total_stores,
                    'total_files': total_files,
                    'total_size_bytes': total_size,
                    'modalities': modality_counts
                }

        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {
                'total_stores': 0,
                'total_files': 0,
                'total_size_bytes': 0,
                'modalities': {}
            }


# Global instance
database_service = DatabaseService()

