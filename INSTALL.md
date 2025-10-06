# Installation Guide

Complete installation instructions for Yandex Music CLI on different operating systems.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Linux Installation](#linux-installation)
- [macOS Installation](#macos-installation)
- [Windows Installation](#windows-installation)
- [Docker Installation](#docker-installation)
- [Getting Your Yandex Token](#getting-your-yandex-token)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- **Python 3.9 or higher**
- **pip** (Python package manager)
- **git** (for cloning the repository)
- **Yandex Music account** with active subscription

## Linux Installation

### Ubuntu / Debian

```bash
# 1. Install Python and dependencies
sudo apt update
sudo apt install python3 python3-pip python3-venv git -y

# 2. Clone the repository
git clone https://github.com/devmansurov/ymusic-cli.git
cd ymusic-cli

# 3. Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure token
cp .env.example .env
nano .env  # Edit and add your YANDEX_TOKEN

# 6. Test installation
python -m ymusic_cli --help
```

### Fedora / RHEL / CentOS

```bash
# 1. Install Python and dependencies
sudo dnf install python3 python3-pip git -y

# 2-6. Same as Ubuntu above
```

### Arch Linux

```bash
# 1. Install Python and dependencies
sudo pacman -S python python-pip git

# 2-6. Same as Ubuntu above
```

## macOS Installation

### Using Homebrew (Recommended)

```bash
# 1. Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install Python
brew install python git

# 3. Clone the repository
git clone https://github.com/devmansurov/ymusic-cli.git
cd ymusic-cli

# 4. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 5. Install dependencies
pip install -r requirements.txt

# 6. Configure token
cp .env.example .env
nano .env  # Edit and add your YANDEX_TOKEN

# 7. Test installation
python -m ymusic_cli --help
```

## Windows Installation

### Using PowerShell

```powershell
# 1. Install Python from https://www.python.org/downloads/
# Make sure to check "Add Python to PATH" during installation

# 2. Install Git from https://git-scm.com/download/win

# 3. Open PowerShell and clone repository
git clone https://github.com/devmansurov/ymusic-cli.git
cd ymusic-cli

# 4. Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 5. Install dependencies
pip install -r requirements.txt

# 6. Configure token
copy .env.example .env
notepad .env  # Edit and add your YANDEX_TOKEN

# 7. Test installation
python -m ymusic_cli --help
```

### Using WSL (Windows Subsystem for Linux)

Follow the Linux Ubuntu installation instructions above.

## Docker Installation

### Using Docker (Coming Soon)

```bash
# Pull image
docker pull devmansurov/ymusic-cli:latest

# Run
docker run -it --rm \
  -v $(pwd)/downloads:/downloads \
  -e YANDEX_TOKEN=your_token_here \
  devmansurov/ymusic-cli -a 9045812 -n 10 -o /downloads
```

## Getting Your Yandex Token

### Method 1: Browser DevTools (Chrome/Firefox)

1. **Open Yandex Music:**
   - Go to https://music.yandex.ru/
   - Log in to your account

2. **Open DevTools:**
   - Press `F12` or `Ctrl+Shift+I` (Windows/Linux)
   - Press `Cmd+Option+I` (macOS)

3. **Find Session ID:**
   - Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
   - Expand **Cookies** → **https://music.yandex.ru**
   - Find cookie named `Session_id`
   - Copy its value

4. **Add to .env:**
   ```bash
   YANDEX_TOKEN=paste_your_session_id_here
   ```

### Method 2: Using Network Tab

1. Open https://music.yandex.ru/ and log in
2. Open DevTools → **Network** tab
3. Refresh the page
4. Look for requests to `music.yandex.ru`
5. Find `Session_id` in request cookies
6. Copy and add to `.env`

## Installation Options

### Option 1: Direct Usage (No Installation)

```bash
git clone https://github.com/devmansurov/ymusic-cli.git
cd ymusic-cli
pip install -r requirements.txt
cp .env.example .env
# Edit .env with token
python -m ymusic_cli -a 123 -o ./music
```

### Option 2: Package Installation

```bash
git clone https://github.com/devmansurov/ymusic-cli.git
cd ymusic-cli
pip install .
cp .env.example ~/.env
# Edit ~/.env with token
ymusic-cli -a 123 -o ./music
```

### Option 3: Development Installation

```bash
git clone https://github.com/devmansurov/ymusic-cli.git
cd ymusic-cli
pip install -e .  # Editable install
cp .env.example .env
# Edit .env with token
ymusic-cli -a 123 -o ./music
```

## Verification

### Verify Python Installation

```bash
python3 --version
# Should show Python 3.9 or higher
```

### Verify Package Installation

```bash
pip list | grep yandex-music
# Should show: yandex-music  X.X.X
```

### Verify CLI Works

```bash
python -m ymusic_cli --help
# Should display help message
```

### Test Download (Small Test)

```bash
python -m ymusic_cli -a 9045812 -n 1 -o ./test_download -v
# Should download 1 track
```

## Troubleshooting

### "Python not found"

**Linux/macOS:**
```bash
which python3
# If empty, install Python 3
```

**Windows:**
```powershell
python --version
# If error, reinstall Python with "Add to PATH" checked
```

### "pip: command not found"

```bash
# Linux/macOS
python3 -m ensurepip --upgrade

# Windows
python -m ensurepip --upgrade
```

### "ModuleNotFoundError: No module named 'yandex_music'"

```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\Activate.ps1  # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### "Failed to initialize services"

1. Check `.env` file exists
2. Verify `YANDEX_TOKEN` is set
3. Check token is not expired (re-login and get new token)
4. Ensure no extra spaces in `.env`:
   ```bash
   YANDEX_TOKEN=your_token_here
   # NOT: YANDEX_TOKEN = your_token_here (spaces)
   ```

### Permission Errors (Linux/macOS)

```bash
# Don't use sudo with pip in virtual environment
# Instead, ensure virtual environment is activated
source venv/bin/activate
pip install -r requirements.txt
```

### SSL Certificate Errors

```bash
# Update certificates
pip install --upgrade certifi

# Or disable SSL verification (not recommended)
export PYTHONHTTPSVERIFY=0  # Linux/macOS
set PYTHONHTTPSVERIFY=0     # Windows
```

## Updating

### Update from Git

```bash
cd ymusic-cli
git pull origin main
pip install -r requirements.txt --upgrade
```

### Update Dependencies Only

```bash
pip install -r requirements.txt --upgrade
```

## Uninstallation

### Remove Package

```bash
# If installed as package
pip uninstall ymusic-cli

# Remove directory
rm -rf ymusic-cli  # Linux/macOS
rmdir /s ymusic-cli  # Windows
```

## Advanced Configuration

### Custom Storage Directory

Edit `.env`:
```bash
STORAGE_DIR=/path/to/custom/storage
TEMP_DIR=/path/to/custom/temp
```

### Increase Download Speed

Edit `.env`:
```bash
MAX_CONCURRENT_DOWNLOADS=10
DOWNLOAD_CHUNK_SIZE=16384
```

### Enable Debug Logging

```bash
# In .env
LOG_LEVEL=DEBUG

# Or use -v flag
ymusic-cli -a 123 -o ./music -v
```

## System Requirements

### Minimum
- **CPU:** 1 core
- **RAM:** 512 MB
- **Disk:** 1 GB free space
- **Network:** Stable internet connection

### Recommended
- **CPU:** 2+ cores
- **RAM:** 2 GB
- **Disk:** 10 GB free space (for downloads)
- **Network:** Broadband connection

## Support

- **Issues:** https://github.com/devmansurov/ymusic-cli/issues
- **Documentation:** See `docs/` folder

---

**Happy downloading! 🎵**
