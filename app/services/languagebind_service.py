"""
LanguageBind service for multi-modal embedding generation.
Supports all 6 modalities: text, image, video, audio, depth, and thermal.
"""
import torch
from typing import Dict, List, Optional, Union
from pathlib import Path
import numpy as np
from loguru import logger

from app.core.config import settings


class LanguageBindService:
    """
    Service class for LanguageBind multi-modal embeddings.
    Handles model initialization and embedding generation for all 6 modalities.
    """

    def __init__(self):
        """Initialize the LanguageBind service."""
        self.device = None
        self.model = None
        self.tokenizer = None
        self.modality_transform = None
        self.clip_type = {
            'video': 'LanguageBind_Video_FT',
            'audio': 'LanguageBind_Audio_FT',
            'thermal': 'LanguageBind_Thermal',
            'image': 'LanguageBind_Image',
            'depth': 'LanguageBind_Depth',
        }
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize LanguageBind models and transformations.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self._initialized:
            logger.info("LanguageBind already initialized")
            return True

        try:
            logger.info("Initializing LanguageBind service...")

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

            # Import LanguageBind modules from app.languagebind
            try:
                from app.languagebind import LanguageBind, to_device, transform_dict, LanguageBindImageTokenizer
                logger.info("Loaded official LanguageBind package")
            except ImportError as e:
                logger.error(f"Failed to import LanguageBind: {e}")
                raise

            self.to_device = to_device

            # Initialize model - this will download all 6 modality models from Hugging Face
            logger.info("Loading LanguageBind models (downloading from Hugging Face)...")
            logger.info("📥 Downloading all 6 modality models:")
            for modality, model_name in self.clip_type.items():
                logger.info(f"  - {modality}: LanguageBind/{model_name}")

            self.model = LanguageBind(
                clip_type=self.clip_type,
                cache_dir=settings.cache_dir
            )
            self.model = self.model.to(self.device)
            self.model.eval()
            logger.info("✅ All 6 modality models loaded successfully!")

            # Initialize tokenizer
            logger.info("Loading tokenizer...")
            pretrained_ckpt = 'LanguageBind/LanguageBind_Image'
            self.tokenizer = LanguageBindImageTokenizer.from_pretrained(
                pretrained_ckpt,
                cache_dir=f'{settings.cache_dir}/tokenizer_cache_dir'
            )
            logger.info("✅ Tokenizer loaded successfully")

            # Initialize modality transforms
            logger.info("Setting up modality transforms...")
            self.modality_transform = {
                c: transform_dict[c](self.model.modality_config[c])
                for c in self.clip_type.keys()
            }
            logger.info("✅ Transforms initialized successfully")

            self._initialized = True
            logger.info("=" * 60)
            logger.info("✅ LanguageBind service initialization complete!")
            logger.info("✅ All 6 modalities ready: text, image, video, audio, depth, thermal")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"Failed to initialize LanguageBind: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._initialized = False
            return False

    def generate_text_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for text input."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            inputs = self.tokenizer(
                [text],
                max_length=77,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                embeddings = self.model({'language': inputs})
                embedding = embeddings['language'][0].cpu().numpy()

            logger.info(f"Generated text embedding with shape {embedding.shape}")
            return embedding

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
            inputs = self.modality_transform['image']([image_path])
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                embeddings = self.model({'image': inputs})
                embedding = embeddings['image'][0].cpu().numpy()

            logger.info(f"Generated image embedding with shape {embedding.shape}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate image embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def generate_video_embedding(self, video_path: Union[str, Path]) -> Optional[np.ndarray]:
        """Generate embedding for video input."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            video_path = str(video_path)
            inputs = self.modality_transform['video']([video_path])
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                embeddings = self.model({'video': inputs})
                embedding = embeddings['video'][0].cpu().numpy()

            logger.info(f"Generated video embedding with shape {embedding.shape}")
            return embedding

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
            inputs = self.modality_transform['audio']([audio_path])
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                embeddings = self.model({'audio': inputs})
                embedding = embeddings['audio'][0].cpu().numpy()

            logger.info(f"Generated audio embedding with shape {embedding.shape}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate audio embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def generate_depth_embedding(self, depth_path: Union[str, Path]) -> Optional[np.ndarray]:
        """Generate embedding for depth map input."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            depth_path = str(depth_path)
            inputs = self.modality_transform['depth']([depth_path])
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                embeddings = self.model({'depth': inputs})
                embedding = embeddings['depth'][0].cpu().numpy()

            logger.info(f"Generated depth embedding with shape {embedding.shape}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate depth embedding: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def generate_thermal_embedding(self, thermal_path: Union[str, Path]) -> Optional[np.ndarray]:
        """Generate embedding for thermal image input."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        try:
            thermal_path = str(thermal_path)
            inputs = self.modality_transform['thermal']([thermal_path])
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                embeddings = self.model({'thermal': inputs})
                embedding = embeddings['thermal'][0].cpu().numpy()

            logger.info(f"Generated thermal embedding with shape {embedding.shape}")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate thermal embedding: {e}")
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
            modality: Type of modality ('text', 'image', 'video', 'audio', 'depth', 'thermal')
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
        else:
            logger.error(f"Unknown modality: {modality}")
            return None

    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized


# Global service instance
languagebind_service = LanguageBindService()
