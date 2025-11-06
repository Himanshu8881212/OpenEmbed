"""
File handling utilities for upload, validation, and processing.
"""
import os
import uuid
from pathlib import Path
from typing import Optional, Tuple
import shutil
from fastapi import UploadFile
from loguru import logger

from app.core.config import settings
from app.models.schemas import ModalityType


class FileHandler:
    """Handle file upload and validation operations."""

    def __init__(self):
        """Initialize file handler."""
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def validate_file_extension(self, filename: str, modality: ModalityType) -> bool:
        """
        Validate file extension against allowed formats for the modality.

        Args:
            filename: Name of the file
            modality: Type of modality

        Returns:
            bool: True if valid, False otherwise
        """
        file_ext = Path(filename).suffix.lower()

        allowed_formats = {
            ModalityType.VIDEO: settings.allowed_video_formats,
            ModalityType.AUDIO: settings.allowed_audio_formats,
            ModalityType.IMAGE: settings.allowed_image_formats,
            ModalityType.DEPTH: settings.allowed_depth_formats,
            ModalityType.THERMAL: settings.allowed_thermal_formats,
            ModalityType.TEXT: ['.txt']
        }

        allowed = allowed_formats.get(modality, [])
        is_valid = file_ext in allowed

        if not is_valid:
            logger.warning(f"Invalid file extension {file_ext} for modality {modality}")

        return is_valid

    async def save_upload_file(
        self,
        upload_file: UploadFile,
        modality: ModalityType
    ) -> Optional[Tuple[str, Path]]:
        """
        Save uploaded file to disk.

        Args:
            upload_file: FastAPI upload file object
            modality: Type of modality

        Returns:
            Tuple of (file_id, file_path) or None if failed
        """
        try:
            # Validate file extension
            if not self.validate_file_extension(upload_file.filename, modality):
                logger.error(f"Invalid file extension for {upload_file.filename}")
                return None

            # Generate unique file ID
            file_id = str(uuid.uuid4())
            file_ext = Path(upload_file.filename).suffix

            # Create modality-specific subdirectory
            modality_dir = self.upload_dir / modality.value
            modality_dir.mkdir(parents=True, exist_ok=True)

            # Save file
            file_path = modality_dir / f"{file_id}{file_ext}"

            with open(file_path, 'wb') as f:
                shutil.copyfileobj(upload_file.file, f)

            file_size = file_path.stat().st_size

            # Validate file size
            if file_size > settings.max_file_size:
                logger.error(f"File {upload_file.filename} exceeds max size")
                file_path.unlink()
                return None

            logger.info(f"Saved file {upload_file.filename} as {file_id} ({file_size} bytes)")
            return file_id, file_path

        except Exception as e:
            logger.error(f"Failed to save upload file: {e}")
            return None

    def get_file_path(self, file_id: str, modality: ModalityType) -> Optional[Path]:
        """
        Get file path from file ID.

        Args:
            file_id: Unique file identifier
            modality: Type of modality

        Returns:
            Path object or None if not found
        """
        try:
            modality_dir = self.upload_dir / modality.value

            # Search for file with matching ID
            for file_path in modality_dir.glob(f"{file_id}.*"):
                if file_path.is_file():
                    return file_path

            logger.warning(f"File not found: {file_id} in {modality.value}")
            return None

        except Exception as e:
            logger.error(f"Error getting file path: {e}")
            return None

    def delete_file(self, file_id: str, modality: ModalityType) -> bool:
        """
        Delete a file.

        Args:
            file_id: Unique file identifier
            modality: Type of modality

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            file_path = self.get_file_path(file_id, modality)
            if file_path and file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {file_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False

    def cleanup_old_files(self, days: int = 7) -> int:
        """
        Clean up files older than specified days.

        Args:
            days: Number of days threshold

        Returns:
            int: Number of files deleted
        """
        import time
        deleted_count = 0

        try:
            current_time = time.time()
            threshold = days * 24 * 60 * 60  # Convert days to seconds

            for modality_dir in self.upload_dir.iterdir():
                if modality_dir.is_dir():
                    for file_path in modality_dir.iterdir():
                        if file_path.is_file():
                            file_age = current_time - file_path.stat().st_mtime
                            if file_age > threshold:
                                file_path.unlink()
                                deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} old files")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return deleted_count


# Global file handler instance
file_handler = FileHandler()
