"""
Simple LanguageBind model wrapper using transformers AutoModel.
Loads all 6 modality models directly from Hugging Face.
"""
import torch
from transformers import AutoModel, AutoTokenizer, AutoProcessor
from typing import Dict
from loguru import logger


class LanguageBindWrapper:
    """Simple wrapper for LanguageBind models using AutoModel."""

    def __init__(self, clip_type: Dict[str, str], cache_dir: str = './cache_dir'):
        """
        Initialize LanguageBind models.

        Args:
            clip_type: Dictionary mapping modality to model name
            cache_dir: Directory to cache models
        """
        self.clip_type = clip_type
        self.cache_dir = cache_dir
        self.models = {}
        self.device = torch.device('cpu')

    def to(self, device):
        """Move models to device."""
        self.device = device
        for modality, model in self.models.items():
            if model is not None:
                self.models[modality] = model.to(device)
        return self

    def eval(self):
        """Set models to evaluation mode."""
        for model in self.models.values():
            if model is not None:
                model.eval()
        return self

    def load_modality_model(self, modality: str, model_name: str):
        """Load a specific modality model from Hugging Face."""
        try:
            logger.info(f"Loading {modality} model: {model_name}")

            full_model_name = f"LanguageBind/{model_name}"

            model = AutoModel.from_pretrained(
                full_model_name,
                cache_dir=self.cache_dir,
                trust_remote_code=True
            )

            self.models[modality] = model
            logger.info(f"✅ Loaded {modality} model: {full_model_name}")

        except Exception as e:
            logger.error(f"❌ Failed to load {modality} model: {e}")
            raise

    def initialize_models(self):
        """Initialize all configured models."""
        logger.info("Downloading LanguageBind models from Hugging Face...")
        for modality, model_name in self.clip_type.items():
            self.load_modality_model(modality, model_name)
        logger.info("✅ All models loaded successfully!")

    @property
    def modality_config(self):
        """Return modality configurations."""
        return {modality: {} for modality in self.clip_type.keys()}

    def __call__(self, inputs: Dict):
        """
        Process inputs through models.

        Args:
            inputs: Dictionary with modality as key and processed tensors as values

        Returns:
            Dictionary of embeddings for each modality
        """
        outputs = {}

        with torch.no_grad():
            for modality, tensor_input in inputs.items():
                if modality not in self.models:
                    logger.warning(f"Model for {modality} not loaded")
                    continue

                model = self.models[modality]

                try:
                    if modality == 'language':
                        # Text embedding
                        if hasattr(model, 'get_text_features'):
                            outputs[modality] = model.get_text_features(**tensor_input)
                        else:
                            output = model(**tensor_input)
                            outputs[modality] = output.pooler_output if hasattr(output, 'pooler_output') else output.last_hidden_state[:, 0, :]
                    else:
                        # Vision/Audio/Other modalities
                        pixel_values = tensor_input.get('pixel_values') if isinstance(tensor_input, dict) else tensor_input

                        if hasattr(model, 'get_image_features'):
                            outputs[modality] = model.get_image_features(pixel_values)
                        else:
                            output = model(pixel_values=pixel_values)
                            outputs[modality] = output.pooler_output if hasattr(output, 'pooler_output') else output.last_hidden_state[:, 0, :]

                except Exception as e:
                    logger.error(f"Error processing {modality}: {e}")
                    raise

        return outputs


class LanguageBindImageTokenizer:
    """Tokenizer for text processing."""

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    @classmethod
    def from_pretrained(cls, model_name: str, cache_dir: str = './cache_dir'):
        """Load tokenizer from LanguageBind model."""
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            trust_remote_code=True
        )
        return cls(tokenizer)

    def __call__(self, texts, max_length=77, padding='max_length',
                 truncation=True, return_tensors='pt'):
        """Tokenize texts."""
        return self.tokenizer(
            texts,
            max_length=max_length,
            padding=padding,
            truncation=truncation,
            return_tensors=return_tensors
        )


def LanguageBind(clip_type: Dict[str, str], cache_dir: str = './cache_dir'):
    """
    Factory function to create LanguageBind wrapper.

    Args:
        clip_type: Dictionary of modality to model mappings
        cache_dir: Cache directory for models

    Returns:
        LanguageBindWrapper instance
    """
    wrapper = LanguageBindWrapper(clip_type, cache_dir)
    wrapper.initialize_models()
    return wrapper


def to_device(inputs, device):
    """Move inputs to device."""
    if isinstance(inputs, dict):
        return {k: v.to(device) if torch.is_tensor(v) else v
                for k, v in inputs.items()}
    elif torch.is_tensor(inputs):
        return inputs.to(device)
    return inputs


class TextModelWrapper:
    """Wrapper for text model using LanguageBind."""

    def __init__(self, cache_dir='./cache_dir'):
        logger.info("Loading LanguageBind text model...")

        self.model = AutoModel.from_pretrained(
            'LanguageBind/LanguageBind_Image',
            cache_dir=cache_dir,
            trust_remote_code=True
        )
        self.device = torch.device('cpu')
        logger.info("✅ Text model loaded")

    def to(self, device):
        self.device = device
        self.model = self.model.to(device)
        return self

    def eval(self):
        self.model.eval()
        return self

    def __call__(self, inputs):
        with torch.no_grad():
            if hasattr(self.model, 'get_text_features'):
                return self.model.get_text_features(**inputs)
            else:
                output = self.model(**inputs)
                return output.pooler_output if hasattr(output, 'pooler_output') else output.last_hidden_state[:, 0, :]


# Simple transform dictionary - will be populated by LanguageBind package
class TransformDict:
    """Placeholder for transform dictionary."""

    def __getitem__(self, key):
        """Return a simple identity transform."""
        def identity_transform(data):
            return data
        return identity_transform


transform_dict = TransformDict()
