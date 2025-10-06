# Distribution Guide

This guide explains how to share and distribute the Yandex Music CLI package.

## Package Overview

The standalone package is located at:
```
/home/devmansurov/Projects/Personal/ymusic/ymusic-cli/
```

This package contains everything needed to run the CLI independently from the Telegram bot.

## Package Structure

```
ymusic-cli/
├── README.md                    # Main documentation
├── INSTALL.md                   # Installation instructions
├── LICENSE                      # MIT License
├── setup.py                     # Package installer
├── requirements.txt             # Dependencies
├── .env.example                 # Configuration template
├── .gitignore                   # Git ignore rules
├── ymusic_cli/                  # Main package
│   ├── __init__.py             # Package init
│   ├── cli.py                  # CLI entry point
│   ├── config/                 # Configuration
│   │   ├── settings.py
│   │   └── validators.py
│   ├── core/                   # Core models
│   │   ├── models.py
│   │   ├── exceptions.py
│   │   └── interfaces.py
│   ├── services/               # Services
│   │   ├── yandex_service.py
│   │   ├── download_service.py
│   │   ├── discovery_service.py
│   │   └── cache_service.py
│   └── utils/                  # Utilities
│       ├── file_manager.py
│       └── progress_tracker.py
├── scripts/
│   └── install.sh              # Installation script
└── docs/                       # Documentation
    ├── USAGE.md
    ├── QUICK_START.md
    └── TESTING.md
```

## Distribution Methods

### Method 1: GitHub Repository (Recommended)

1. **Create GitHub Repository:**
   ```bash
   cd /home/devmansurov/Projects/Personal/ymusic/ymusic-cli
   git init
   git add .
   git commit -m "Initial commit: Yandex Music CLI v1.0.0"
   ```

2. **Create GitHub repo at https://github.com/new**
   - Name: `ymusic-cli`
   - Description: "CLI tool for automated artist discovery and track downloading from Yandex Music"
   - Make it public or private

3. **Push to GitHub:**
   ```bash
   git remote add origin https://github.com/devmansurov/yandex-downloader-cli.git
   git branch -M main
   git push -u origin main
   ```

4. **Users can install:**
   ```bash
   git clone https://github.com/devmansurov/yandex-downloader-cli.git
   cd ymusic-cli
   bash scripts/install.sh
   ```

### Method 2: Direct Archive

1. **Create compressed archive:**
   ```bash
   cd /home/devmansurov/Projects/Personal/ymusic
   tar -czf ymusic-cli-v1.0.0.tar.gz ymusic-cli/
   ```

2. **Share the archive:**
   - Upload to file hosting (Google Drive, Dropbox, etc.)
   - Send directly to users
   - Host on your own server

3. **Users can install:**
   ```bash
   # Extract archive
   tar -xzf ymusic-cli-v1.0.0.tar.gz
   cd ymusic-cli
   bash scripts/install.sh
   ```

### Method 3: PyPI Package (Advanced)

1. **Prepare for PyPI:**
   ```bash
   cd /home/devmansurov/Projects/Personal/ymusic/ymusic-cli
   pip install build twine
   python -m build
   ```

2. **Upload to PyPI:**
   ```bash
   twine upload dist/*
   ```

3. **Users can install:**
   ```bash
   pip install ymusic-cli
   ymusic-cli --help
   ```

### Method 4: Docker Image (Future)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
ENTRYPOINT ["python", "-m", "ymusic_cli"]
```

## Pre-Distribution Checklist

- [x] All source files copied
- [x] Dependencies listed in requirements.txt
- [x] setup.py configured
- [x] README.md created
- [x] INSTALL.md created
- [x] LICENSE file added
- [x] .gitignore configured
- [x] .env.example template created
- [x] Installation script created
- [x] Documentation complete

## Testing Before Distribution

### 1. Test in Clean Environment

```bash
# Create test directory
mkdir ~/test_ymusic_cli
cd ~/test_ymusic_cli

# Copy package
cp -r /home/devmansurov/Projects/Personal/ymusic/ymusic-cli .
cd ymusic-cli

# Test installation
bash scripts/install.sh

# Test CLI
source venv/bin/activate
python -m ymusic_cli --help
```

### 2. Test Basic Functionality

```bash
# Copy .env from bot
cp /home/devmansurov/Projects/Personal/ymusic/server/bot/.env .

# Test download
python -m ymusic_cli -a 9045812 -n 1 -o ./test -v
```

### 3. Test on Different System (Optional)

- Test on clean Ubuntu/Debian VM
- Test on macOS (if available)
- Test on Windows (if available)

## Sharing Instructions for Users

### Quick Start (Copy-Paste Ready)

```markdown
# Install Yandex Music CLI

## Quick Install (Linux/macOS)
\`\`\`bash
# Download and install
git clone https://github.com/devmansurov/yandex-downloader-cli.git
cd ymusic-cli
bash scripts/install.sh

# Configure your token
nano .env  # Add YANDEX_TOKEN

# Test
source venv/bin/activate
python -m ymusic_cli --help
\`\`\`

## Usage
\`\`\`bash
# Download 10 songs from an artist
python -m ymusic_cli -a 9045812 -n 10 -o ./downloads

# With similar artists
python -m ymusic_cli -a 9045812 -n 5 -s 15 -o ./downloads
\`\`\`

For full documentation, see README.md
```

## Version Management

### Updating the Package

1. **Update version in setup.py:**
   ```python
   version="1.0.1",
   ```

2. **Update version in ymusic_cli/__init__.py:**
   ```python
   __version__ = "1.0.1"
   ```

3. **Create release:**
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```

## Support and Maintenance

### Issue Tracking

If distributing via GitHub, users can report issues at:
```
https://github.com/devmansurov/yandex-downloader-cli/issues
```

### Updates

To update users' installations:
```bash
cd ymusic-cli
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

## Security Notes

**Important:**
- Never include `.env` file with actual tokens
- Always use `.env.example` as template
- Remind users to keep their tokens private
- Don't commit tokens to Git

## FAQ for Distribution

### Q: Do I need the whole bot codebase?
**A:** No! This standalone package has everything needed.

### Q: Can users install without git?
**A:** Yes, share the tar.gz archive instead.

### Q: Does this work on Windows?
**A:** Yes, with Python 3.9+ installed.

### Q: Can I distribute this commercially?
**A:** Yes, under MIT License terms.

### Q: What if the Yandex API changes?
**A:** Update `yandex-music` package version in requirements.txt

## Distribution Checklist

Before sharing:

- [ ] Test in clean environment
- [ ] Verify all documentation is up-to-date
- [ ] Remove any sensitive data (.env files)
- [ ] Test installation script
- [ ] Create release notes
- [ ] Tag version in git
- [ ] Update CHANGELOG.md
- [ ] Announce release (if public)

## Example Release Notes

```markdown
## ymusic-cli v1.0.0

First stable release!

### Features
- Download tracks from any Yandex Music artist
- Discover similar artists recursively
- Advanced filtering (years, countries)
- Shuffle mode with numeric prefixes
- Progress tracking with tqdm
- Smart caching

### Installation
\`\`\`bash
git clone https://github.com/devmansurov/yandex-downloader-cli.git
cd ymusic-cli
bash scripts/install.sh
\`\`\`

### Requirements
- Python 3.9+
- Yandex Music account

See INSTALL.md for detailed instructions.
```

---

**Ready for distribution! 🚀**
