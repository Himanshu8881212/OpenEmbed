"""
Automatic modality detection from file extensions.
"""
from pathlib import Path
from typing import Optional, List, Dict
from loguru import logger

from app.models.schemas import ModalityType
from app.core.config import settings


class ModalityDetector:
    """Detect modality type from file extension."""
    
    def __init__(self):
        """Initialize modality detector with format mappings."""
        # Build reverse mapping: extension -> list of possible modalities
        # Some extensions like .png can be used for multiple modalities
        self.extension_to_modalities: Dict[str, List[ModalityType]] = {}

        # Text formats (unique)
        for ext in settings.allowed_text_formats:
            ext_lower = ext.lower()
            if ext_lower not in self.extension_to_modalities:
                self.extension_to_modalities[ext_lower] = []
            self.extension_to_modalities[ext_lower].append(ModalityType.TEXT)

        # Video formats (unique)
        for ext in settings.allowed_video_formats:
            ext_lower = ext.lower()
            if ext_lower not in self.extension_to_modalities:
                self.extension_to_modalities[ext_lower] = []
            self.extension_to_modalities[ext_lower].append(ModalityType.VIDEO)

        # Audio formats (unique)
        for ext in settings.allowed_audio_formats:
            ext_lower = ext.lower()
            if ext_lower not in self.extension_to_modalities:
                self.extension_to_modalities[ext_lower] = []
            self.extension_to_modalities[ext_lower].append(ModalityType.AUDIO)

        # Image formats (may overlap with depth/thermal for .png, .jpg, etc.)
        for ext in settings.allowed_image_formats:
            ext_lower = ext.lower()
            if ext_lower not in self.extension_to_modalities:
                self.extension_to_modalities[ext_lower] = []
            self.extension_to_modalities[ext_lower].append(ModalityType.IMAGE)

        # Depth formats (may overlap with image for .png)
        # Add depth as secondary option - image has priority for auto-detection
        for ext in settings.allowed_depth_formats:
            ext_lower = ext.lower()
            if ext_lower not in self.extension_to_modalities:
                self.extension_to_modalities[ext_lower] = []
            # Add depth only if not already in the list
            if ModalityType.DEPTH not in self.extension_to_modalities[ext_lower]:
                self.extension_to_modalities[ext_lower].append(ModalityType.DEPTH)

        # Thermal formats (may overlap with image for .jpg, .png)
        # Add thermal as secondary option - image has priority for auto-detection
        for ext in settings.allowed_thermal_formats:
            ext_lower = ext.lower()
            if ext_lower not in self.extension_to_modalities:
                self.extension_to_modalities[ext_lower] = []
            # Add thermal only if not already in the list
            if ModalityType.THERMAL not in self.extension_to_modalities[ext_lower]:
                self.extension_to_modalities[ext_lower].append(ModalityType.THERMAL)

        # IMU formats (sensor data formats)
        for ext in settings.allowed_imu_formats:
            ext_lower = ext.lower()
            if ext_lower not in self.extension_to_modalities:
                self.extension_to_modalities[ext_lower] = []
            # Add IMU only if not already in the list
            if ModalityType.IMU not in self.extension_to_modalities[ext_lower]:
                self.extension_to_modalities[ext_lower].append(ModalityType.IMU)

        total_mappings = sum(len(modalities) for modalities in self.extension_to_modalities.values())
        logger.info(f"Initialized ModalityDetector with {total_mappings} format mappings across {len(self.extension_to_modalities)} extensions")
    
    def detect_modality(self, filename: str, preferred_modality: Optional[ModalityType] = None) -> Optional[ModalityType]:
        """
        Detect modality from filename extension.

        For ambiguous extensions (e.g., .png can be image, depth, or thermal),
        returns the first match or the preferred modality if specified.

        Args:
            filename: Name of the file
            preferred_modality: If specified and the extension supports it, use this modality

        Returns:
            ModalityType if detected, None otherwise
        """
        file_ext = Path(filename).suffix.lower()

        modalities = self.extension_to_modalities.get(file_ext, [])

        if not modalities:
            logger.warning(f"Could not detect modality for file '{filename}' (extension: {file_ext})")
            return None

        # If preferred modality is specified and supported, use it
        if preferred_modality and preferred_modality in modalities:
            logger.debug(f"Using preferred modality '{preferred_modality.value}' for file '{filename}' (extension: {file_ext})")
            return preferred_modality

        # Otherwise, return the first (highest priority) modality
        modality = modalities[0]

        if len(modalities) > 1:
            logger.debug(
                f"Detected modality '{modality.value}' for file '{filename}' (extension: {file_ext}). "
                f"Note: This extension supports multiple modalities: {[m.value for m in modalities]}"
            )
        else:
            logger.debug(f"Detected modality '{modality.value}' for file '{filename}' (extension: {file_ext})")

        return modality
    
    def get_supported_formats(self, modality: ModalityType) -> List[str]:
        """
        Get list of supported formats for a modality.

        Args:
            modality: Type of modality

        Returns:
            List of supported file extensions
        """
        format_map = {
            ModalityType.TEXT: settings.allowed_text_formats,
            ModalityType.VIDEO: settings.allowed_video_formats,
            ModalityType.AUDIO: settings.allowed_audio_formats,
            ModalityType.IMAGE: settings.allowed_image_formats,
            ModalityType.DEPTH: settings.allowed_depth_formats,
            ModalityType.THERMAL: settings.allowed_thermal_formats,
            ModalityType.IMU: settings.allowed_imu_formats,
        }

        return format_map.get(modality, [])
    
    def get_all_supported_formats(self) -> Dict[str, List[str]]:
        """
        Get all supported formats for all modalities.

        Returns:
            Dictionary mapping modality name to list of supported extensions
        """
        return {
            "text": settings.allowed_text_formats,
            "video": settings.allowed_video_formats,
            "audio": settings.allowed_audio_formats,
            "image": settings.allowed_image_formats,
            "depth": settings.allowed_depth_formats,
            "thermal": settings.allowed_thermal_formats,
            "imu": settings.allowed_imu_formats,
        }
    
    def is_format_supported(self, filename: str) -> bool:
        """
        Check if file format is supported by any modality.

        Args:
            filename: Name of the file

        Returns:
            True if supported, False otherwise
        """
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.extension_to_modalities
    
    def validate_file_for_modality(self, filename: str, modality: ModalityType) -> bool:
        """
        Validate that file extension is supported for the specified modality.

        This checks if the file extension is in the list of allowed formats for the modality,
        not just if it auto-detects to that modality. This allows shared extensions like .png
        to be used with depth/thermal when explicitly specified.

        Args:
            filename: Name of the file
            modality: Expected modality type

        Returns:
            True if valid, False otherwise
        """
        file_ext = Path(filename).suffix.lower()

        # Check if extension is supported for this modality
        modalities_for_ext = self.extension_to_modalities.get(file_ext, [])

        is_valid = modality in modalities_for_ext

        if not is_valid:
            # Get the allowed formats for this modality
            allowed_formats = self.get_supported_formats(modality)
            logger.warning(
                f"File '{filename}' with extension '{file_ext}' is not supported for modality '{modality.value}'. "
                f"Supported formats: {allowed_formats}"
            )

        return is_valid


# Global modality detector instance
modality_detector = ModalityDetector()

