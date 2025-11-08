"""
Test modality detection functionality.
Ensures all 7 modalities are correctly detected.
"""
import pytest
from app.utils.modality_detector import modality_detector
from app.models.schemas import ModalityType


class TestModalityDetection:
    """Test automatic modality detection from file extensions."""
    
    def test_text_formats(self):
        """Test text file detection"""
        text_files = [
            "document.txt",
            "readme.md",
            "data.pdf",
            "report.doc",
            "report.docx",
            "notes.rtf",
            "document.odt"
        ]
        
        for filename in text_files:
            modality = modality_detector.detect_modality(filename)
            assert modality == ModalityType.TEXT, f"Failed for {filename}"
    
    def test_image_formats(self):
        """Test image file detection"""
        image_files = [
            "photo.jpg",
            "photo.jpeg",
            "graphic.png",
            "bitmap.bmp",
            "animation.gif",
            "image.tiff",
            "image.tif",
            "picture.webp",
            "vector.svg"
        ]
        
        for filename in image_files:
            modality = modality_detector.detect_modality(filename)
            assert modality == ModalityType.IMAGE, f"Failed for {filename}"
    
    def test_video_formats(self):
        """Test video file detection"""
        video_files = [
            "movie.mp4",
            "clip.avi",
            "video.mov",
            "film.mkv",
            "stream.webm",
            "old.flv",
            "windows.wmv",
            "apple.m4v",
            "mpeg.mpg",
            "mpeg.mpeg"
        ]
        
        for filename in video_files:
            modality = modality_detector.detect_modality(filename)
            assert modality == ModalityType.VIDEO, f"Failed for {filename}"
    
    def test_audio_formats(self):
        """Test audio file detection"""
        audio_files = [
            "sound.wav",
            "music.mp3",
            "lossless.flac",
            "audio.m4a",
            "compressed.aac",
            "vorbis.ogg",
            "windows.wma",
            "codec.opus"
        ]
        
        for filename in audio_files:
            modality = modality_detector.detect_modality(filename)
            assert modality == ModalityType.AUDIO, f"Failed for {filename}"
    
    def test_depth_formats(self):
        """Test depth map file detection with explicit modality"""
        # Unique depth formats
        depth_files = [
            "depth.exr",
            "depth.pfm"
        ]

        for filename in depth_files:
            modality = modality_detector.detect_modality(filename)
            # These should auto-detect to depth (unique extensions)
            assert modality == ModalityType.DEPTH, f"Failed for {filename}"

        # PNG can be depth but defaults to image
        # Test with preferred modality
        png_depth = modality_detector.detect_modality("depth.png", preferred_modality=ModalityType.DEPTH)
        assert png_depth == ModalityType.DEPTH
    
    def test_thermal_formats(self):
        """Test thermal image file detection with explicit modality"""
        # Thermal uses same extensions as images, so test with preferred modality
        thermal_files = [
            "thermal.jpg",
            "thermal.jpeg",
            "thermal.png",
            "thermal.tiff",
            "thermal.tif"
        ]
        
        for filename in thermal_files:
            # Without preference, should default to image
            modality = modality_detector.detect_modality(filename)
            assert modality == ModalityType.IMAGE, f"Failed default for {filename}"
            
            # With preference, should use thermal
            modality_thermal = modality_detector.detect_modality(filename, preferred_modality=ModalityType.THERMAL)
            assert modality_thermal == ModalityType.THERMAL, f"Failed preferred for {filename}"
    
    def test_imu_formats(self):
        """Test IMU sensor data file detection"""
        imu_files = [
            "sensor.csv",
            "imu_data.json",
            "accel.npy",
            "gyro.npz",
            "motion.pkl",
            "sensor.h5",
            "data.hdf5"
        ]
        
        for filename in imu_files:
            modality = modality_detector.detect_modality(filename)
            assert modality == ModalityType.IMU, f"Failed for {filename}"


class TestModalityValidation:
    """Test modality validation for files."""
    
    def test_validate_text_file(self):
        """Test text file validation"""
        assert modality_detector.validate_file_for_modality("doc.txt", ModalityType.TEXT)
        assert not modality_detector.validate_file_for_modality("image.jpg", ModalityType.TEXT)
    
    def test_validate_image_file(self):
        """Test image file validation"""
        assert modality_detector.validate_file_for_modality("photo.jpg", ModalityType.IMAGE)
        assert not modality_detector.validate_file_for_modality("video.mp4", ModalityType.IMAGE)
    
    def test_validate_video_file(self):
        """Test video file validation"""
        assert modality_detector.validate_file_for_modality("movie.mp4", ModalityType.VIDEO)
        assert not modality_detector.validate_file_for_modality("audio.mp3", ModalityType.VIDEO)
    
    def test_validate_audio_file(self):
        """Test audio file validation"""
        assert modality_detector.validate_file_for_modality("sound.wav", ModalityType.AUDIO)
        assert not modality_detector.validate_file_for_modality("text.txt", ModalityType.AUDIO)
    
    def test_validate_depth_file(self):
        """Test depth file validation"""
        assert modality_detector.validate_file_for_modality("depth.exr", ModalityType.DEPTH)
        assert modality_detector.validate_file_for_modality("depth.png", ModalityType.DEPTH)  # Shared extension
        assert not modality_detector.validate_file_for_modality("video.mp4", ModalityType.DEPTH)
    
    def test_validate_thermal_file(self):
        """Test thermal file validation"""
        assert modality_detector.validate_file_for_modality("thermal.jpg", ModalityType.THERMAL)
        assert modality_detector.validate_file_for_modality("thermal.png", ModalityType.THERMAL)  # Shared extension
        assert not modality_detector.validate_file_for_modality("audio.wav", ModalityType.THERMAL)
    
    def test_validate_imu_file(self):
        """Test IMU file validation"""
        assert modality_detector.validate_file_for_modality("sensor.csv", ModalityType.IMU)
        assert modality_detector.validate_file_for_modality("imu.json", ModalityType.IMU)
        assert not modality_detector.validate_file_for_modality("image.jpg", ModalityType.IMU)


class TestSupportedFormats:
    """Test supported format queries."""
    
    def test_get_text_formats(self):
        """Test getting text formats"""
        formats = modality_detector.get_supported_formats(ModalityType.TEXT)
        assert ".txt" in formats
        assert ".md" in formats
        assert ".pdf" in formats
    
    def test_get_image_formats(self):
        """Test getting image formats"""
        formats = modality_detector.get_supported_formats(ModalityType.IMAGE)
        assert ".jpg" in formats
        assert ".png" in formats
        assert ".gif" in formats
    
    def test_get_video_formats(self):
        """Test getting video formats"""
        formats = modality_detector.get_supported_formats(ModalityType.VIDEO)
        assert ".mp4" in formats
        assert ".avi" in formats
        assert ".mov" in formats
    
    def test_get_audio_formats(self):
        """Test getting audio formats"""
        formats = modality_detector.get_supported_formats(ModalityType.AUDIO)
        assert ".wav" in formats
        assert ".mp3" in formats
        assert ".flac" in formats
    
    def test_get_depth_formats(self):
        """Test getting depth formats"""
        formats = modality_detector.get_supported_formats(ModalityType.DEPTH)
        assert ".exr" in formats
        assert ".pfm" in formats
        assert ".png" in formats  # Shared
    
    def test_get_thermal_formats(self):
        """Test getting thermal formats"""
        formats = modality_detector.get_supported_formats(ModalityType.THERMAL)
        assert ".jpg" in formats
        assert ".png" in formats
        assert ".tiff" in formats
    
    def test_get_imu_formats(self):
        """Test getting IMU formats"""
        formats = modality_detector.get_supported_formats(ModalityType.IMU)
        assert ".csv" in formats
        assert ".json" in formats
        assert ".h5" in formats
    
    def test_get_all_formats(self):
        """Test getting all supported formats"""
        all_formats = modality_detector.get_all_supported_formats()
        assert "text" in all_formats
        assert "image" in all_formats
        assert "video" in all_formats
        assert "audio" in all_formats
        assert "depth" in all_formats
        assert "thermal" in all_formats
        assert "imu" in all_formats


class TestFormatSupport:
    """Test format support checking."""
    
    def test_supported_formats(self):
        """Test checking if formats are supported"""
        assert modality_detector.is_format_supported("file.txt")
        assert modality_detector.is_format_supported("image.jpg")
        assert modality_detector.is_format_supported("video.mp4")
        assert modality_detector.is_format_supported("audio.wav")
        assert modality_detector.is_format_supported("depth.npy")
        assert modality_detector.is_format_supported("thermal.tiff")
        assert modality_detector.is_format_supported("sensor.csv")
    
    def test_unsupported_formats(self):
        """Test checking unsupported formats"""
        assert not modality_detector.is_format_supported("file.xyz")
        assert not modality_detector.is_format_supported("unknown.abc")
        assert not modality_detector.is_format_supported("test.123")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

