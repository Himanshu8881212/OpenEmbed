#!/usr/bin/env python3
"""
Verification script to check if all dependencies match LanguageBind requirements.
Run this inside the Docker container to verify the installation.
"""

import sys

def check_version(package_name, expected_version):
    """Check if a package has the expected version."""
    try:
        if package_name == "torch":
            import torch
            actual = torch.__version__
        elif package_name == "transformers":
            import transformers
            actual = transformers.__version__
        elif package_name == "numpy":
            import numpy
            actual = numpy.__version__
        elif package_name == "opencv-python":
            import cv2
            actual = cv2.__version__
        elif package_name == "scipy":
            import scipy
            actual = scipy.__version__
        elif package_name == "einops":
            import einops
            actual = einops.__version__
        elif package_name == "tokenizers":
            import tokenizers
            actual = tokenizers.__version__
        else:
            return True, "skipped"

        # Handle version suffixes like +cpu, +cu116, etc.
        actual_base = actual.split('+')[0]
        expected_base = expected_version.split('+')[0]

        if actual_base == expected_base:
            return True, actual
        else:
            return False, actual
    except ImportError as e:
        return False, f"NOT INSTALLED: {e}"

def main():
    """Main verification function."""
    print("=" * 70)
    print("🔍 LanguageBind Dependency Verification")
    print("=" * 70)

    # Official LanguageBind requirements
    requirements = {
        "torch": "1.13.1",
        "transformers": "4.30.2",
        "tokenizers": "0.13.3",
        "numpy": "1.23.0",
        "scipy": "1.10.1",
        "opencv-python": "4.7.0.72",
        "einops": "0.6.1",
    }

    all_pass = True

    for package, expected in requirements.items():
        passed, actual = check_version(package, expected)
        status = "✅" if passed else "❌"
        print(f"{status} {package:20s} Expected: {expected:10s} Actual: {actual}")
        if not passed:
            all_pass = False

    print("=" * 70)

    if all_pass:
        print("✅ All dependencies verified successfully!")
        print("\n🎉 LanguageBind should initialize without errors")
    else:
        print("❌ Some dependencies have incorrect versions!")
        print("\n⚠️  LanguageBind may fail to initialize")
        sys.exit(1)

    print("=" * 70)

    # Try importing LanguageBind
    print("\n🧪 Testing LanguageBind import...")
    try:
        from app.languagebind import LanguageBind, to_device, transform_dict, LanguageBindImageTokenizer
        print("✅ LanguageBind imported successfully!")
    except Exception as e:
        print(f"❌ Failed to import LanguageBind: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n✨ All checks passed!")

if __name__ == "__main__":
    main()
