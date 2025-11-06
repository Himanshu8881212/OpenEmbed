#!/usr/bin/env python3
"""Debug script to test audio embedding generation."""

import sys
sys.path.insert(0, '/Users/himanshuninawe/Work/Working/EMBEd')

import torch
import torchaudio
from app.languagebind.audio.modeling_audio import LanguageBindAudio
from app.languagebind.audio.processing_audio import get_audio_transform

# Load the model
print("Loading audio model...")
model = LanguageBindAudio.from_pretrained(
    'LanguageBind/LanguageBind_Audio_FT',
    cache_dir='./cache_dir',
    attn_implementation="eager"
)

print("\nAudio Vision Config:")
print(f"  num_mel_bins: {model.config.vision_config.num_mel_bins}")
print(f"  target_length: {model.config.vision_config.target_length}")
print(f"  image_size: {model.config.vision_config.image_size}")
print(f"  patch_size: {model.config.vision_config.patch_size}")
print(f"  audio_sample_rate: {model.config.vision_config.audio_sample_rate}")
print(f"  audio_mean: {model.config.vision_config.audio_mean}")
print(f"  audio_std: {model.config.vision_config.audio_std}")

# Load audio file
audio_path = 'demo_files/sample_audio.wav'
print(f"\nLoading audio file: {audio_path}")
waveform, sample_rate = torchaudio.load(audio_path)
print(f"  Waveform shape: {waveform.shape}")
print(f"  Sample rate: {sample_rate}")

# Get transform
print("\nCreating audio transform...")
transform = get_audio_transform(model.config)

# Transform audio
print("\nTransforming audio...")
try:
    audio_features = transform((waveform, sample_rate))
    print(f"  Transformed audio shape: {audio_features.shape}")
    print(f"  Expected shape: [3, {model.config.vision_config.num_mel_bins}, {model.config.vision_config.target_length}]")
    
    # Try to pass through model
    print("\nPassing through vision model...")
    audio_features = audio_features.unsqueeze(0)  # Add batch dimension
    print(f"  Input shape with batch: {audio_features.shape}")
    
    with torch.no_grad():
        output = model.vision_model(audio_features)
        print(f"  Output type: {type(output)}")
        if isinstance(output, tuple):
            print(f"  Output tuple length: {len(output)}")
            for i, o in enumerate(output):
                if hasattr(o, 'shape'):
                    print(f"  Output[{i}] shape: {o.shape}")
        elif hasattr(output, 'pooler_output'):
            print(f"  Pooler output shape: {output.pooler_output.shape}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

