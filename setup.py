"""Setup script for Yandex Music CLI."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="ymusic-cli",
    version="1.0.0",
    author="devmansurov",
    author_email="",
    description="CLI tool for automated artist discovery and track downloading from Yandex Music",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/devmansurov/yandex-music-cli",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Sound/Audio",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "ymusic-cli=ymusic_cli.cli:main",
            "ymusic-serve=ymusic_cli.serve:cli_entry",
        ],
    },
    include_package_data=True,
    keywords="yandex music download cli artist discovery",
    project_urls={
        "Bug Reports": "https://github.com/devmansurov/yandex-music-cli/issues",
        "Source": "https://github.com/devmansurov/yandex-music-cli",
    },
)
