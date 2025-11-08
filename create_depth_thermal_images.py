#!/usr/bin/env python3
"""
Create proper depth and thermal images for testing.
Depth and thermal images need to be single-channel (grayscale).
"""
from PIL import Image
import numpy as np

# Create depth image (single channel grayscale)
depth_data = np.random.randint(0, 256, (224, 224), dtype=np.uint8)
depth_img = Image.fromarray(depth_data, mode='L')
depth_img.save('demo_files/sample_depth.png')
print("✅ Created demo_files/sample_depth.png (grayscale)")

# Create thermal image (single channel grayscale)
thermal_data = np.random.randint(0, 256, (224, 224), dtype=np.uint8)
thermal_img = Image.fromarray(thermal_data, mode='L')
thermal_img.save('demo_files/sample_thermal.png')
print("✅ Created demo_files/sample_thermal.png (grayscale)")

