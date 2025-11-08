"""Setup configuration for OpenEmbed Python SDK."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="openembed-sdk",
    version="1.0.0",
    author="OpenEmbed Team",
    author_email="support@openembed.io",
    description="Official Python SDK for OpenEmbed - Multi-Modal Embedding Warehouse",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Himanshu8881212/EMBEd",
    py_modules=["openembed"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ],
    },
)

