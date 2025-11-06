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
    Uses lazy loading - models are only loaded when first requested.
    """

    def __init__(self):
        """Initialize the LanguageBind service."""
        self.device = None
        self.tokenizer = None
        self.clip_type = {
            'video': 'LanguageBind_Video_FT',
            'audio': 'LanguageBind_Audio_FT',
            'thermal': 'LanguageBind_Thermal',
            'image': 'LanguageBind_Image',
            'depth': 'LanguageBind_Depth',
        }
        # Lazy loading: models loaded on-demand
        self.modality_encoder = {}  # Stores loaded vision encoders
        self.modality_proj = {}  # Stores loaded projection layers
        self.modality_scale = {}  # Stores loaded logit scales
        self.modality_config = {}  # Stores loaded configs
        self.modality_transform = {}  # Stores loaded transforms
        self.full_model = {}  # Stores full models (for text access)
        self._initialized = False
        self._base_initialized = False

    def initialize(self) -> bool:
        """
        Initialize base LanguageBind service (device and imports only).
        Models are loaded lazily when first requested.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self._base_initialized:
            logger.info("LanguageBind base already initialized")
            return True

        try:
            logger.info("Initializing LanguageBind service (lazy loading mode)...")

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
                from app.languagebind import to_device, transform_dict, LanguageBindImageTokenizer
                logger.info("Loaded LanguageBind package")
            except ImportError as e:
                logger.error(f"Failed to import LanguageBind: {e}")
                raise

            self.to_device = to_device
            self.transform_dict = transform_dict

            # Initialize tokenizer (shared across all modalities)
            logger.info("Loading tokenizer...")
            pretrained_ckpt = 'LanguageBind/LanguageBind_Image'
            self.tokenizer = LanguageBindImageTokenizer.from_pretrained(
                pretrained_ckpt,
                cache_dir=f'{settings.cache_dir}/tokenizer_cache_dir'
            )
            logger.info("✅ Tokenizer loaded successfully")

            self._base_initialized = True
            self._initialized = True
            logger.info("=" * 60)
            logger.info("✅ LanguageBind service initialized (lazy loading mode)")
            logger.info("✅ Models will be loaded on-demand when first requested")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"Failed to initialize LanguageBind: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._base_initialized = False
            self._initialized = False
            return False

    def _load_modality_model(self, modality: str) -> bool:
        """
        Load a specific modality model on-demand.

        Args:
            modality: Modality to load (image, video, audio, depth, thermal)

        Returns:
            bool: True if loaded successfully, False otherwise
        """
        if modality in self.modality_encoder:
            logger.debug(f"Model for {modality} already loaded")
            return True

        if not self._base_initialized:
            logger.error("Base service not initialized. Call initialize() first.")
            return False

        try:
            logger.info(f"📥 Loading {modality} model on-demand...")

            # Import model classes
            from app.languagebind import model_dict

            # Get model name
            model_name = self.clip_type[modality]
            pretrained_ckpt = f'LanguageBind/{model_name}'

            # Load model
            model = model_dict[modality].from_pretrained(
                pretrained_ckpt,
                cache_dir=settings.cache_dir,
                attn_implementation="eager"
            )

            # Recursively set _attn_implementation on all configs to avoid KeyError
            def set_attn_implementation(module):
                """Recursively set _attn_implementation on all submodules with config"""
                if hasattr(module, 'config'):
                    module.config._attn_implementation = "eager"
                for child in module.children():
                    set_attn_implementation(child)

            set_attn_implementation(model)

            # For image modality, store full model BEFORE extracting vision_model
            # (text encoder needs access to the full model and text projection)
            if modality == 'image':
                self.full_model['image'] = model.to(self.device)
                self.full_model['image'].eval()
                # Store text projection separately for text embeddings
                self.modality_proj['text'] = model.text_projection.to(self.device)
                self.modality_proj['text'].eval()

            # Store model components
            self.modality_encoder[modality] = model.vision_model.to(self.device)
            self.modality_proj[modality] = model.visual_projection.to(self.device)
            self.modality_scale[modality] = model.logit_scale.to(self.device)
            self.modality_config[modality] = model.config

            # For audio modality, patch embeddings forward to handle non-square dimensions
            if modality == 'audio':
                vision_config = model.config.vision_config
                if vision_config.num_mel_bins != 0 and vision_config.target_length != 0:
                    # Store reference to embeddings
                    embeddings = self.modality_encoder[modality].embeddings

                    # Create a custom forward function that bypasses the dimension check
                    import types

                    def patched_forward(self, pixel_values, interpolate_pos_encoding=False):
                        batch_size, _, height, width = pixel_values.shape
                        # For audio, we expect [batch, 3, 112, 1036]
                        # Skip the square image size check
                        target_dtype = self.patch_embedding.weight.dtype
                        patch_embeds = self.patch_embedding(pixel_values.to(dtype=target_dtype))
                        patch_embeds = patch_embeds.flatten(2).transpose(1, 2)

                        class_embeds = self.class_embedding.expand(batch_size, 1, -1)
                        embeddings_out = torch.cat([class_embeds, patch_embeds], dim=1)
                        embeddings_out = embeddings_out + self.position_embedding(self.position_ids)

                        return embeddings_out

                    # Bind the method to the embeddings instance
                    embeddings.forward = types.MethodType(patched_forward, embeddings)
                    logger.debug(f"Patched audio embeddings forward method to handle non-square images [{vision_config.num_mel_bins}, {vision_config.target_length}]")

            # Initialize transform for this modality
            self.modality_transform[modality] = self.transform_dict[modality](model.config)

            # Set to eval mode
            self.modality_encoder[modality].eval()
            self.modality_proj[modality].eval()

            logger.info(f"✅ {modality.capitalize()} model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load {modality} model: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def generate_text_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding for text input (uses image model's text encoder)."""
        if not self._initialized:
            logger.error("Service not initialized")
            return None

        # Load image model if not already loaded (text uses image model's encoder)
        if not self._load_modality_model('image'):
            logger.error("Failed to load image model for text embedding")
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
                # Use full image model's text encoder
                text_output = self.full_model['image'].text_model(**inputs)
                # Extract pooled output (CLS token representation)
                text_features = text_output[1] if isinstance(text_output, tuple) else text_output.pooler_output
                # Use text projection (not visual projection)
                text_features = self.modality_proj['text'](text_features)
                text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True)
                embedding = text_features[0].cpu().numpy()

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

        # Load image model if not already loaded
        if not self._load_modality_model('image'):
            logger.error("Failed to load image model")
            return None

        try:
            image_path = str(image_path)
            inputs = self.modality_transform['image']([image_path])
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                # Extract pixel_values from inputs dict
                pixel_values = inputs['pixel_values'] if isinstance(inputs, dict) else inputs
                encoder_output = self.modality_encoder['image'](pixel_values)
                # Extract pooled output (CLS token representation)
                image_features = encoder_output[1] if isinstance(encoder_output, tuple) else encoder_output.pooler_output
                image_features = self.modality_proj['image'](image_features)
                image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
                embedding = image_features[0].cpu().numpy()

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

        # Load video model if not already loaded
        if not self._load_modality_model('video'):
            logger.error("Failed to load video model")
            return None

        try:
            video_path = str(video_path)
            inputs = self.modality_transform['video']([video_path])
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                # Extract pixel_values from inputs dict
                pixel_values = inputs['pixel_values'] if isinstance(inputs, dict) else inputs
                encoder_output = self.modality_encoder['video'](pixel_values)
                # Extract pooled output (CLS token representation)
                video_features = encoder_output[1] if isinstance(encoder_output, tuple) else encoder_output.pooler_output
                video_features = self.modality_proj['video'](video_features)
                video_features = video_features / video_features.norm(p=2, dim=-1, keepdim=True)
                embedding = video_features[0].cpu().numpy()

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

        # Load audio model if not already loaded
        if not self._load_modality_model('audio'):
            logger.error("Failed to load audio model")
            return None

        try:
            audio_path = str(audio_path)
            inputs = self.modality_transform['audio']([audio_path])
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                # Extract pixel_values from inputs dict
                pixel_values = inputs['pixel_values'] if isinstance(inputs, dict) else inputs
                encoder_output = self.modality_encoder['audio'](pixel_values)
                # Extract pooled output (CLS token representation)
                audio_features = encoder_output[1] if isinstance(encoder_output, tuple) else encoder_output.pooler_output
                audio_features = self.modality_proj['audio'](audio_features)
                audio_features = audio_features / audio_features.norm(p=2, dim=-1, keepdim=True)
                embedding = audio_features[0].cpu().numpy()

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

        # Load depth model if not already loaded
        if not self._load_modality_model('depth'):
            logger.error("Failed to load depth model")
            return None

        try:
            depth_path = str(depth_path)
            inputs = self.modality_transform['depth']([depth_path])
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                # Extract pixel_values from inputs dict
                pixel_values = inputs['pixel_values'] if isinstance(inputs, dict) else inputs
                encoder_output = self.modality_encoder['depth'](pixel_values)
                # Extract pooled output (CLS token representation)
                depth_features = encoder_output[1] if isinstance(encoder_output, tuple) else encoder_output.pooler_output
                depth_features = self.modality_proj['depth'](depth_features)
                depth_features = depth_features / depth_features.norm(p=2, dim=-1, keepdim=True)
                embedding = depth_features[0].cpu().numpy()

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

        # Load thermal model if not already loaded
        if not self._load_modality_model('thermal'):
            logger.error("Failed to load thermal model")
            return None

        try:
            thermal_path = str(thermal_path)
            inputs = self.modality_transform['thermal']([thermal_path])
            inputs = self.to_device(inputs, self.device)

            with torch.no_grad():
                # Extract pixel_values from inputs dict
                pixel_values = inputs['pixel_values'] if isinstance(inputs, dict) else inputs
                encoder_output = self.modality_encoder['thermal'](pixel_values)
                # Extract pooled output (CLS token representation)
                thermal_features = encoder_output[1] if isinstance(encoder_output, tuple) else encoder_output.pooler_output
                thermal_features = self.modality_proj['thermal'](thermal_features)
                thermal_features = thermal_features / thermal_features.norm(p=2, dim=-1, keepdim=True)
                embedding = thermal_features[0].cpu().numpy()

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
