"""
ImageBind service for multi-modal embedding generation.
Uses Meta's ImageBind model for unified embeddings across 7 modalities:
text, image, video, audio, depth, thermal, and IMU.
"""
import torch
from typing import Optional, Union
from pathlib import Path
import numpy as np
from loguru import logger
import tempfile
from PIL import Image

from app.core.config import settings


def load_and_transform_video_data_pyav(
    video_paths,
    device,
    clip_duration=2,
    clips_per_video=5,
    sample_rate=16000,
):
    """
    Custom video loading function that uses 'pyav' decoder instead of 'decord'.
    This is a drop-in replacement for imagebind.data.load_and_transform_video_data
    that works without decord dependency.

    Args:
        video_paths: List of video file paths
        device: torch device (cpu, cuda, mps)
        clip_duration: Duration of each clip in seconds
        clips_per_video: Number of clips to sample per video
        sample_rate: Audio sample rate (not used for video-only)

    Returns:
        Preprocessed video tensor ready for ImageBind model
    """
    if video_paths is None:
        return None

    # Import required modules
    from torchvision import transforms
    from pytorchvideo.data.encoded_video import EncodedVideo
    from pytorchvideo.transforms import (
        UniformTemporalSubsample,
        ShortSideScale,
    )
    from pytorchvideo.data.clip_sampling import ConstantClipsPerVideoSampler

    # Define normalization transform
    class NormalizeVideo:
        def __init__(self, mean, std):
            # Shape should be [C, 1, 1, 1] to broadcast correctly across [C, T, H, W]
            self.mean = torch.tensor(mean).view(3, 1, 1, 1)
            self.std = torch.tensor(std).view(3, 1, 1, 1)

        def __call__(self, video):
            return (video - self.mean) / self.std

    video_outputs = []
    video_transform = transforms.Compose(
        [
            ShortSideScale(224),
            NormalizeVideo(
                mean=(0.48145466, 0.4578275, 0.40821073),
                std=(0.26862954, 0.26130258, 0.27577711),
            ),
        ]
    )

    clip_sampler = ConstantClipsPerVideoSampler(
        clip_duration=clip_duration, clips_per_video=clips_per_video
    )
    frame_sampler = UniformTemporalSubsample(num_samples=clip_duration)

    for video_path in video_paths:
        # Use 'pyav' decoder instead of 'decord'
        video = EncodedVideo.from_path(
            video_path,
            decoder="pyav",  # Changed from "decord" to "pyav"
            decode_audio=False,
        )

        all_clips_timepoints = get_clip_timepoints(clip_sampler, video.duration)

        all_video = []
        for clip_timepoints in all_clips_timepoints:
            # Read and transform video
            video_data = video.get_clip(clip_timepoints[0], clip_timepoints[1])
            video_data = frame_sampler(video_data["video"])

            # Ensure video has 3 channels (RGB)
            # Video data shape is [C, T, H, W] where C is channels
            if video_data.shape[0] != 3:
                logger.info(f"Video has {video_data.shape[0]} channels, converting to 3 channels (RGB). Shape: {video_data.shape}")
                # Convert grayscale or other formats to RGB by repeating channels
                if video_data.shape[0] == 1:
                    # Grayscale: repeat channel 3 times
                    video_data = video_data.repeat(3, 1, 1, 1)
                elif video_data.shape[0] == 2:
                    # 2-channel video: duplicate first channel to make RGB
                    video_data = torch.cat([video_data, video_data[:1]], dim=0)
                else:
                    # For other channel counts, take first 3 channels or pad with zeros
                    if video_data.shape[0] > 3:
                        video_data = video_data[:3]
                    else:
                        # Pad with zeros to make 3 channels
                        padding = torch.zeros(3 - video_data.shape[0], *video_data.shape[1:])
                        video_data = torch.cat([video_data, padding], dim=0)
                logger.info(f"Converted to {video_data.shape[0]} channels. New shape: {video_data.shape}")

            video_data = video_transform(video_data)
            all_video.append(video_data)

        all_video = torch.stack(all_video, dim=0)
        video_outputs.append(all_video)

    return torch.stack(video_outputs, dim=0).to(device)


def get_clip_timepoints(clip_sampler, duration):
    """
    Helper function to get clip timepoints from sampler.

    Args:
        clip_sampler: Clip sampler object
        duration: Video duration in seconds

    Returns:
        List of (start_time, end_time) tuples for each clip
    """
    # Read all clips in the video
    all_clips_timepoints = []
    is_last_clip = False
    end = 0.0
    while not is_last_clip:
        start, end, _, _, is_last_clip = clip_sampler(end, duration, annotation=None)
        all_clips_timepoints.append((start, end))

    return all_clips_timepoints


class ImageBindService:
    """
    Service class for ImageBind multi-modal embeddings.
    Handles model initialization and embedding generation for all 6 modalities.
    """

    def __init__(self):
        """Initialize the ImageBind service."""
        self.device = None
        self.model = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize ImageBind service.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self._initialized:
            logger.info("ImageBind already initialized")
            return True

        try:
            logger.info("Initializing ImageBind service...")

            # Set device - support CPU, CUDA GPU, and Apple MPS
            if settings.device == 'auto':
                # Auto-detect best available device
                if torch.cuda.is_available():
                    self.device = torch.device('cuda')
                    logger.info("✅ Auto-detected and using CUDA GPU")
                elif torch.backends.mps.is_available():
                    self.device = torch.device('mps')
                    logger.info("✅ Auto-detected and using Apple MPS (Metal Performance Shaders)")
                else:
                    self.device = torch.device('cpu')
                    logger.warning("⚠️  No GPU detected, using CPU (this will be slower)")
            elif settings.device.startswith('cuda') and torch.cuda.is_available():
                self.device = torch.device(settings.device)
                logger.info(f"✅ Using CUDA GPU: {self.device}")
            elif settings.device == 'mps' and torch.backends.mps.is_available():
                self.device = torch.device('mps')
                logger.info("✅ Using Apple MPS (Metal Performance Shaders)")
            elif settings.device == 'cpu':
                self.device = torch.device('cpu')
                logger.info("✅ Using CPU as requested")
            else:
                # Fallback to CPU if requested device not available
                self.device = torch.device('cpu')
                logger.warning(f"⚠️  Requested device '{settings.device}' not available, falling back to CPU")

            # Import ImageBind modules
            try:
                from imagebind import data as imagebind_data
                from imagebind.models import imagebind_model
                from imagebind.models.imagebind_model import ModalityType

                self.imagebind_data = imagebind_data
                self.ModalityType = ModalityType
                logger.info("✅ Loaded ImageBind package")
            except ImportError as e:
                logger.error(f"Failed to import ImageBind: {e}")
                raise

            # Load ImageBind model
            logger.info("Loading ImageBind model (this may take 2-3 minutes on first run)...")
            logger.info("Downloading model weights if not cached (~2.4GB)...")

            # Set torch to use less memory during model loading
            torch.set_num_threads(2)  # Limit CPU threads

            self.model = imagebind_model.imagebind_huge(pretrained=True)
            self.model.eval()

            logger.info("Moving model to device...")
            self.model.to(self.device)
            logger.info("✅ ImageBind model loaded successfully")

            self._initialized = True
            logger.info("=" * 60)
            logger.info("✅ ImageBind service initialized successfully")
            logger.info(f"✅ Device: {self.device}")
            logger.info("✅ All 7 modalities ready: text, image, video, audio, depth, thermal, IMU")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"Failed to initialize ImageBind: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._initialized = False
            return False

    def _generate_embedding(self, inputs: dict, modality_type) -> Optional[np.ndarray]:
        """
        Internal method to generate embedding from preprocessed inputs.

        Args:
            inputs: Preprocessed inputs dictionary
            modality_type: ImageBind ModalityType enum

        Returns:
            numpy array of embedding or None if failed
        """
        try:
            with torch.no_grad():
                embeddings = self.model(inputs)
                embedding = embeddings[modality_type]
                # Normalize embedding
                embedding = embedding / embedding.norm(dim=-1, keepdim=True)
                embedding = embedding[0].cpu().numpy()

            logger.info(f"Generated embedding with shape {embedding.shape}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def generate_text_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for text input."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            inputs = {
                self.ModalityType.TEXT: self.imagebind_data.load_and_transform_text([text], self.device)
            }
            return self._generate_embedding(inputs, self.ModalityType.TEXT)

        except Exception as e:
            logger.error(f"Failed to generate text embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def generate_image_embedding(self, image_path: Union[str, Path]) -> Optional[np.ndarray]:
        """Generate embedding for image input."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            image_path = str(image_path)
            inputs = {
                self.ModalityType.VISION: self.imagebind_data.load_and_transform_vision_data([image_path], self.device)
            }
            return self._generate_embedding(inputs, self.ModalityType.VISION)

        except Exception as e:
            logger.error(f"Failed to generate image embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def generate_video_embedding(self, video_path: Union[str, Path]) -> Optional[np.ndarray]:
        """
        Generate embedding for video input.
        Uses custom pyav-based video loader instead of decord.
        """
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            video_path = str(video_path)
            logger.info(f"Loading video with pyav decoder: {video_path}")

            # Use our custom video loader that uses 'pyav' instead of 'decord'
            inputs = {
                self.ModalityType.VISION: load_and_transform_video_data_pyav([video_path], self.device)
            }

            logger.info("✅ Video loaded successfully with pyav decoder")
            return self._generate_embedding(inputs, self.ModalityType.VISION)

        except Exception as e:
            logger.error(f"Failed to generate video embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def generate_audio_embedding(self, audio_path: Union[str, Path]) -> Optional[np.ndarray]:
        """Generate embedding for audio input."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            audio_path = str(audio_path)
            inputs = {
                self.ModalityType.AUDIO: self.imagebind_data.load_and_transform_audio_data([audio_path], self.device)
            }
            return self._generate_embedding(inputs, self.ModalityType.AUDIO)

        except Exception as e:
            logger.error(f"Failed to generate audio embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def generate_depth_embedding(self, depth_path: Union[str, Path]) -> Optional[np.ndarray]:
        """Generate embedding for depth map input (single-channel grayscale)."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            from PIL import Image
            from torchvision import transforms

            depth_path = str(depth_path)

            # Custom transform for single-channel depth images
            # Note: ImageBind expects 1-channel depth images, NOT 3-channel
            data_transform = transforms.Compose([
                transforms.Resize(224, interpolation=transforms.InterpolationMode.BICUBIC),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                # Normalize for single channel (use only first value of mean/std)
                transforms.Normalize(
                    mean=(0.48145466,),
                    std=(0.26862954,),
                ),
            ])

            # Load depth image as grayscale (1-channel)
            with open(depth_path, "rb") as fopen:
                image = Image.open(fopen).convert("L")  # Convert to grayscale

            # Transform and prepare for model
            depth_tensor = data_transform(image).to(self.device)
            depth_tensor = depth_tensor.unsqueeze(0)  # Add batch dimension

            inputs = {
                self.ModalityType.DEPTH: depth_tensor
            }
            return self._generate_embedding(inputs, self.ModalityType.DEPTH)

        except Exception as e:
            logger.error(f"Failed to generate depth embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def generate_thermal_embedding(self, thermal_path: Union[str, Path]) -> Optional[np.ndarray]:
        """Generate embedding for thermal image input (single-channel grayscale)."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            from PIL import Image
            from torchvision import transforms

            thermal_path = str(thermal_path)

            # Custom transform for single-channel thermal images
            # Note: ImageBind expects 1-channel thermal images, NOT 3-channel
            data_transform = transforms.Compose([
                transforms.Resize(224, interpolation=transforms.InterpolationMode.BICUBIC),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                # Normalize for single channel (use only first value of mean/std)
                transforms.Normalize(
                    mean=(0.48145466,),
                    std=(0.26862954,),
                ),
            ])

            # Load thermal image as grayscale (1-channel)
            with open(thermal_path, "rb") as fopen:
                image = Image.open(fopen).convert("L")  # Convert to grayscale

            # Transform and prepare for model
            thermal_tensor = data_transform(image).to(self.device)
            thermal_tensor = thermal_tensor.unsqueeze(0)  # Add batch dimension

            inputs = {
                self.ModalityType.THERMAL: thermal_tensor
            }
            return self._generate_embedding(inputs, self.ModalityType.THERMAL)

        except Exception as e:
            logger.error(f"Failed to generate thermal embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _load_and_transform_imu_data(self, imu_path: str) -> torch.Tensor:
        """
        Load and transform IMU data (accelerometer + gyroscope).
        IMU data format: 6 channels (accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z) over time.
        Expected input: CSV or JSON with columns for accelerometer and gyroscope data.
        """
        import pandas as pd
        import json

        # Load IMU data based on file extension
        if imu_path.endswith('.csv'):
            df = pd.read_csv(imu_path)
            # Expected columns: accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z
            # Or: timestamp, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z
            accel_cols = ['accel_x', 'accel_y', 'accel_z']
            gyro_cols = ['gyro_x', 'gyro_y', 'gyro_z']

            if all(col in df.columns for col in accel_cols + gyro_cols):
                imu_data = df[accel_cols + gyro_cols].values
            else:
                raise ValueError(f"CSV must contain columns: {accel_cols + gyro_cols}")

        elif imu_path.endswith('.json'):
            with open(imu_path, 'r') as f:
                data = json.load(f)

            # Handle different JSON structures
            if 'sensor_data' in data and 'measurements' in data['sensor_data']:
                measurements = data['sensor_data']['measurements']
                imu_data = []
                for m in measurements:
                    accel = m['accelerometer']
                    gyro = m['gyroscope']
                    imu_data.append([accel['x'], accel['y'], accel['z'],
                                   gyro['x'], gyro['y'], gyro['z']])
                imu_data = np.array(imu_data)
            else:
                raise ValueError("JSON must contain sensor_data.measurements structure")

        elif imu_path.endswith('.npy'):
            imu_data = np.load(imu_path)
        elif imu_path.endswith('.npz'):
            data = np.load(imu_path)
            imu_data = data['imu'] if 'imu' in data else data[data.files[0]]
        else:
            raise ValueError(f"Unsupported IMU file format: {imu_path}")

        # Ensure shape is (T, 6) where T is number of timesteps
        if imu_data.shape[1] != 6:
            raise ValueError(f"IMU data must have 6 channels, got {imu_data.shape[1]}")

        # ImageBind requires 2000 timesteps (10 seconds at 200Hz)
        # Reference: https://github.com/facebookresearch/ImageBind/issues/66#issuecomment-1602304380
        target_samples = 2000
        if len(imu_data) > target_samples:
            # Take middle section
            start_idx = (len(imu_data) - target_samples) // 2
            imu_data = imu_data[start_idx:start_idx + target_samples]
        elif len(imu_data) < target_samples:
            # Pad with repeat (as suggested in ImageBind discussions)
            # Repeat the data to fill the required length
            repeats = (target_samples // len(imu_data)) + 1
            imu_data = np.tile(imu_data, (repeats, 1))[:target_samples]

        # Convert to tensor: shape (1, 6, T)
        imu_tensor = torch.from_numpy(imu_data.T).float().unsqueeze(0)
        return imu_tensor.to(self.device)

    def generate_imu_embedding(self, imu_path: Union[str, Path]) -> Optional[np.ndarray]:
        """Generate embedding for IMU (Inertial Measurement Unit) data input."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            imu_path = str(imu_path)
            imu_tensor = self._load_and_transform_imu_data(imu_path)

            inputs = {
                self.ModalityType.IMU: imu_tensor
            }
            return self._generate_embedding(inputs, self.ModalityType.IMU)

        except Exception as e:
            logger.error(f"Failed to generate IMU embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def generate_embedding(
        self,
        modality: str,
        file_path: Optional[Union[str, Path]] = None,
        text_content: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """
        Generate embedding for any modality type.

        Args:
            modality: Type of modality ('text', 'image', 'video', 'audio', 'depth', 'thermal', 'imu')
            file_path: Path to file (not needed for text)
            text_content: Text content (only for text modality)

        Returns:
            numpy array of embedding or None if failed
        """
        modality = modality.lower()

        if modality == 'text':
            if not text_content:
                logger.error("Text content required for text modality")
                return None
            return self.generate_text_embedding(text_content)
        elif modality == 'image':
            return self.generate_image_embedding(file_path)
        elif modality == 'video':
            return self.generate_video_embedding(file_path)
        elif modality == 'audio':
            return self.generate_audio_embedding(file_path)
        elif modality == 'depth':
            return self.generate_depth_embedding(file_path)
        elif modality == 'thermal':
            return self.generate_thermal_embedding(file_path)
        elif modality == 'imu':
            return self.generate_imu_embedding(file_path)
        else:
            logger.error(f"Unknown modality: {modality}")
            return None

    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized


# Global service instance
imagebind_service = ImageBindService()
