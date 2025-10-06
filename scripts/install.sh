#!/bin/bash
# Yandex Music CLI - Quick Install Script

set -e

echo "🎵 Yandex Music CLI - Installation Script"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed."
    echo "Please install Python 3.9 or higher first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✓ Found Python $PYTHON_VERSION"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ Error: pip3 is not installed."
    echo "Installing pip..."
    python3 -m ensurepip --upgrade
fi

echo "✓ pip is available"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Setup configuration
if [ ! -f ".env" ]; then
    echo "Creating .env configuration file..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: You need to edit .env and add your YANDEX_TOKEN"
    echo "   1. Go to https://music.yandex.ru/ and login"
    echo "   2. Open browser DevTools (F12)"
    echo "   3. Go to Application → Cookies → music.yandex.ru"
    echo "   4. Copy the 'Session_id' cookie value"
    echo "   5. Edit .env and set: YANDEX_TOKEN=your_session_id"
    echo ""
else
    echo "✓ .env file already exists"
    echo ""
fi

# Test installation
echo "Testing installation..."
if python -m ymusic_cli --help &> /dev/null; then
    echo "✓ Installation successful!"
else
    echo "❌ Installation test failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Installation Complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your YANDEX_TOKEN"
echo "2. Activate virtual environment: source venv/bin/activate"
echo "3. Run the CLI: python -m ymusic_cli --help"
echo ""
echo "Example usage:"
echo "  python -m ymusic_cli -a 9045812 -n 10 -o ./downloads"
echo ""
echo "For detailed documentation, see README.md and INSTALL.md"
echo "=========================================="
