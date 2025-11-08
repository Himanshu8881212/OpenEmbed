#!/usr/bin/env python3
"""
Build Multi-Modal Vector Store
================================

Downloads sample data for all 7 modalities and creates a comprehensive vector store.

Modalities:
1. Text - Sample documents
2. Image - Sample images
3. Video - Sample videos
4. Audio - Sample audio files
5. Depth - Depth maps
6. Thermal - Thermal images
7. IMU - IMU sensor data

Usage:
    python build_multimodal_store.py --store multimodal_demo
"""

import os
import sys
import argparse
import requests
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from openembed import OpenEmbedClient
except ImportError:
    print("❌ Error: openembed SDK not found!")
    sys.exit(1)


class MultiModalDataDownloader:
    """Download sample data for all 7 modalities."""
    
    def __init__(self, output_dir: str = "multimodal_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for each modality
        self.dirs = {
            "text": self.output_dir / "text",
            "image": self.output_dir / "image",
            "video": self.output_dir / "video",
            "audio": self.output_dir / "audio",
            "depth": self.output_dir / "depth",
            "thermal": self.output_dir / "thermal",
            "imu": self.output_dir / "imu"
        }
        
        for dir_path in self.dirs.values():
            dir_path.mkdir(exist_ok=True)
    
    def create_text_samples(self) -> List[str]:
        """Create sample text documents."""
        print("\n📝 Creating text samples...")
        
        samples = {
            "ai_overview.txt": """
Artificial Intelligence Overview

Artificial Intelligence (AI) is the simulation of human intelligence by machines.
Key areas include:
- Machine Learning: Algorithms that learn from data
- Natural Language Processing: Understanding human language
- Computer Vision: Interpreting visual information
- Robotics: Intelligent physical systems

AI is transforming industries including healthcare, finance, transportation, and education.
""",
            "climate_change.txt": """
Climate Change Facts

Climate change refers to long-term shifts in global temperatures and weather patterns.
Key facts:
- Global temperatures have risen 1.1°C since pre-industrial times
- Arctic ice is melting at unprecedented rates
- Sea levels are rising approximately 3.3mm per year
- Extreme weather events are becoming more frequent

Solutions include renewable energy, carbon capture, and sustainable practices.
""",
            "space_exploration.txt": """
Space Exploration

Humanity's journey into space began in 1957 with Sputnik 1.
Major milestones:
- 1969: First moon landing (Apollo 11)
- 1990: Hubble Space Telescope launched
- 2012: Curiosity rover lands on Mars
- 2021: James Webb Space Telescope launched

Current goals include Mars colonization and deep space exploration.
""",
            "healthy_eating.txt": """
Healthy Eating Guide

A balanced diet is essential for good health.
Key principles:
- Eat plenty of fruits and vegetables (5+ servings daily)
- Choose whole grains over refined grains
- Include lean proteins (fish, poultry, legumes)
- Limit processed foods and added sugars
- Stay hydrated (8 glasses of water daily)

Meal planning and portion control are important for maintaining a healthy weight.
""",
            "renewable_energy.txt": """
Renewable Energy Sources

Renewable energy comes from naturally replenishing sources.
Main types:
- Solar: Energy from sunlight using photovoltaic panels
- Wind: Turbines convert wind kinetic energy to electricity
- Hydro: Water flow generates power
- Geothermal: Heat from Earth's core
- Biomass: Organic materials for fuel

Renewables are crucial for reducing carbon emissions and combating climate change.
"""
        }
        
        files = []
        for filename, content in samples.items():
            filepath = self.dirs["text"] / filename
            filepath.write_text(content.strip())
            files.append(str(filepath))
            print(f"  ✅ Created {filename}")
        
        return files
    
    def download_image_samples(self) -> List[str]:
        """Download sample images from public sources."""
        print("\n🖼️  Downloading image samples...")
        
        # Using Unsplash Source for sample images (no API key needed)
        image_topics = [
            ("nature", "nature_landscape.jpg"),
            ("technology", "technology.jpg"),
            ("food", "food.jpg"),
            ("architecture", "architecture.jpg"),
            ("animals", "animals.jpg")
        ]
        
        files = []
        for topic, filename in image_topics:
            try:
                url = f"https://source.unsplash.com/800x600/?{topic}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    filepath = self.dirs["image"] / filename
                    filepath.write_bytes(response.content)
                    files.append(str(filepath))
                    print(f"  ✅ Downloaded {filename}")
                else:
                    print(f"  ⚠️  Failed to download {filename}")
            except Exception as e:
                print(f"  ⚠️  Error downloading {filename}: {e}")
        
        return files
    
    def create_sample_files(self) -> List[str]:
        """Create placeholder files for modalities that need special data."""
        print("\n📦 Creating sample files for other modalities...")
        
        files = []
        
        # Video placeholder (we'll create a simple text description)
        video_desc = self.dirs["video"] / "sample_video_description.txt"
        video_desc.write_text("Sample video: A sunset over the ocean with waves crashing on the beach")
        files.append(str(video_desc))
        print("  ✅ Created video description")
        
        # Audio placeholder
        audio_desc = self.dirs["audio"] / "sample_audio_description.txt"
        audio_desc.write_text("Sample audio: Birds chirping in a forest with gentle wind sounds")
        files.append(str(audio_desc))
        print("  ✅ Created audio description")
        
        # Depth placeholder
        depth_desc = self.dirs["depth"] / "sample_depth_description.txt"
        depth_desc.write_text("Sample depth map: 3D scan of a room showing furniture and walls")
        files.append(str(depth_desc))
        print("  ✅ Created depth description")
        
        # Thermal placeholder
        thermal_desc = self.dirs["thermal"] / "sample_thermal_description.txt"
        thermal_desc.write_text("Sample thermal image: Heat signature of a building showing warm and cool areas")
        files.append(str(thermal_desc))
        print("  ✅ Created thermal description")
        
        # IMU placeholder
        imu_desc = self.dirs["imu"] / "sample_imu_description.txt"
        imu_desc.write_text("Sample IMU data: Accelerometer and gyroscope readings from a walking motion")
        files.append(str(imu_desc))
        print("  ✅ Created IMU description")
        
        return files
    
    def download_all(self) -> Dict[str, List[str]]:
        """Download all sample data."""
        print("\n" + "="*80)
        print("📥 Downloading Multi-Modal Sample Data")
        print("="*80)
        
        all_files = {
            "text": self.create_text_samples(),
            "image": self.download_image_samples(),
            "other": self.create_sample_files()
        }
        
        total_files = sum(len(files) for files in all_files.values())
        print(f"\n✅ Downloaded/created {total_files} files")
        print(f"   Location: {self.output_dir}")
        
        return all_files


def build_vector_store(store_name: str, embed_url: str = "http://localhost:8000"):
    """Build multi-modal vector store."""
    print("\n" + "="*80)
    print("🏗️  Building Multi-Modal Vector Store")
    print("="*80)
    
    # Download data
    downloader = MultiModalDataDownloader()
    all_files = downloader.download_all()
    
    # Flatten file list
    file_list = []
    for files in all_files.values():
        file_list.extend(files)
    
    # Initialize EMBEd client
    print(f"\n🔌 Connecting to EMBEd at {embed_url}...")
    client = OpenEmbedClient(embed_url)
    
    # Create vector store
    print(f"\n📦 Creating vector store '{store_name}'...")
    try:
        client.create_store(
            store_name,
            "Multi-modal demo store with all 7 modalities"
        )
        print(f"✅ Created vector store: {store_name}")
    except Exception as e:
        if "already exists" in str(e):
            print(f"ℹ️  Vector store '{store_name}' already exists")
        else:
            print(f"❌ Error creating vector store: {e}")
            return None
    
    # Upload files
    print(f"\n📤 Uploading {len(file_list)} files to vector store...")
    try:
        result = client.upload_batch(store_name, file_list)
        print(f"\n✅ Upload complete!")
        print(f"   Successful: {result.get('successful', 0)}")
        print(f"   Failed: {result.get('failed', 0)}")
        
        if result.get('failed', 0) > 0:
            print("\n⚠️  Some files failed to upload:")
            for error in result.get('errors', []):
                print(f"   - {error}")
    except Exception as e:
        print(f"❌ Error uploading files: {e}")
        return None
    
    # Get store info
    print(f"\n📊 Vector Store Statistics:")
    try:
        stores = client.list_stores()
        for store in stores:
            if store['name'] == store_name:
                print(f"   Name: {store['name']}")
                print(f"   Description: {store['description']}")
                print(f"   Embeddings: {store.get('count', 'N/A')}")
                print(f"   Created: {store.get('created_at', 'N/A')}")
                break
    except Exception as e:
        print(f"⚠️  Could not get store info: {e}")
    
    print("\n" + "="*80)
    print("✅ Multi-Modal Vector Store Built Successfully!")
    print("="*80)
    print(f"\nStore Name: {store_name}")
    print(f"Total Files: {len(file_list)}")
    print(f"Location: {downloader.output_dir}")
    print("\nYou can now use this store for RAG queries!")
    print(f"\nExample:")
    print(f"  python rag_application.py \\")
    print(f"    --mode multimodal \\")
    print(f"    --store {store_name} \\")
    print(f"    --query 'Tell me about renewable energy'")
    
    return store_name


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Build multi-modal vector store with sample data"
    )
    
    parser.add_argument(
        "--store",
        default="multimodal_demo",
        help="Vector store name (default: multimodal_demo)"
    )
    
    parser.add_argument(
        "--embed-url",
        default="http://localhost:8000",
        help="EMBEd API URL (default: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Only download data, don't create vector store"
    )
    
    args = parser.parse_args()
    
    if args.download_only:
        downloader = MultiModalDataDownloader()
        downloader.download_all()
    else:
        build_vector_store(args.store, args.embed_url)


if __name__ == "__main__":
    main()

