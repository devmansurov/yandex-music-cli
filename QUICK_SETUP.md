# Quick Setup Guide

## Repository Information

**Name:** yandex-music-cli  
**URL:** https://github.com/devmansurov/yandex-music-cli  
**Description:** CLI tool for automated artist discovery and track downloading from Yandex Music

## For You (Developer)

### Push to GitHub

```bash
# 1. Create repository on GitHub (if not already created)
# Go to: https://github.com/new
# Name: yandex-music-cli
# Don't initialize with README/license

# 2. Push your code
cd /home/devmansurov/Projects/Personal/ymusic/ymusic-cli
git push -u origin main
```

## For Users

### Installation

```bash
# Clone repository
git clone https://github.com/devmansurov/yandex-music-cli.git
cd yandex-music-cli

# Run installation script
bash scripts/install.sh

# Configure token
nano .env  # Add YANDEX_TOKEN

# Activate environment
source venv/bin/activate

# Test
python -m ymusic_cli --help
```

### Quick Usage

```bash
# Download 10 songs from an artist
python -m ymusic_cli -a 9045812 -n 10 -o ./music

# With similar artists
python -m ymusic_cli -a 9045812 -n 5 -s 15 -o ./music

# Recursive discovery
python -m ymusic_cli -a 9045812 -n 5 -s 10 -d 1 -o ./music

# Shuffle mode
python -m ymusic_cli -a 9045812 -n 10 -s 20 --shuffle -o ./playlist
```

## Documentation

- **README.md** - Full documentation
- **INSTALL.md** - Detailed installation guide
- **docs/USAGE.md** - Complete parameter reference
- **docs/QUICK_START.md** - Quick reference card

## Package Features

- ✅ Download from any Yandex Music artist
- ✅ Similar artist discovery (flat & recursive)  
- ✅ Advanced filters (years, countries, exclude)
- ✅ Shuffle mode with numeric prefixes
- ✅ Progress tracking
- ✅ Smart caching
- ✅ Cross-platform support

**Ready to use! 🎵**
