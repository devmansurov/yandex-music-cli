# Yandex Music CLI 🎵

A powerful command-line tool for automated artist discovery and track downloading from Yandex Music.

## Features

- ✅ Download top N songs from any artist
- ✅ Discover and download from similar artists
- ✅ Recursive artist discovery (similar artists of similar artists)
- ✅ Advanced filtering (years, countries, exclude artists)
- ✅ Shuffle mode with automatic numbering
- ✅ Smart caching to avoid re-downloads
- ✅ Concurrent downloads with progress tracking
- ✅ Quality selection (high/medium/low)

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/devmansurov/yandex-music-cli.git
cd yandex-music-cli

# Install dependencies
pip install -r requirements.txt

# OR install as package
pip install .

# Configure your Yandex Music token
cp .env.example .env
# Edit .env and add your YANDEX_TOKEN
```

### Get Yandex Music Token

1. Go to https://music.yandex.ru/ and log in
2. Open browser DevTools (F12)
3. Go to Application → Cookies → music.yandex.ru
4. Copy the value of the `Session_id` cookie
5. Add it to `.env` file as `YANDEX_TOKEN=your_token_here`

### Basic Usage

```bash
# Download 10 songs from a single artist
python -m ymusic_cli -a 9045812 -n 10 -o ./music

# OR if installed as package
ymusic-cli -a 9045812 -n 10 -o ./music
```

## Usage Examples

### 1. Download from Single Artist
```bash
# With custom output directory
ymusic-cli -a 9045812 -n 10 -o ./downloads

# Using default directory (./storage/downloads)
ymusic-cli -a 9045812 -n 10
```

### 2. Download from Multiple Artists
```bash
ymusic-cli -a "9045812,41114,328849" -n 10 -o ./downloads
# Downloads from 3 different artists (automatically deduplicates)
```

### 3. Discover Similar Artists
```bash
ymusic-cli -a 9045812 -n 5 -s 15 -o ./downloads
# Downloads from base artist + 15 similar artists
```

### 4. Multiple Artists with Similar Discovery
```bash
ymusic-cli -a "9045812,41114" -n 5 -s 10 -o ./downloads
# Discovers similar artists from 2 base artists (automatically deduplicates)
```

### 5. Recursive Discovery
```bash
ymusic-cli -a 9045812 -n 5 -s 10 -d 1 -o ./downloads
# Discovers similar artists recursively (depth 1)
```

### 6. Shuffle Mode
```bash
ymusic-cli -a 9045812 -n 10 -s 20 --shuffle -o ./playlist
# All songs in one folder with numeric prefixes (001_, 002_, etc.)
```

### 7. With Filters
```bash
ymusic-cli -a 9045812 -n 10 -y 2020-2024 -c US,GB -o ./downloads
# Filter by year range and countries
```

### 8. Smart Year-Based Filtering
```bash
# Year range (2024-2025)
ymusic-cli -a "9045812,10393751,222668" -n 5 -s 3 -d 1 -y 2024-2025 -o ./downloads

# Single year (2025 only)
ymusic-cli -a "9045812,10393751,222668" -n 5 -s 3 -d 1 -y 2025 -o ./downloads

# Year-based smart filtering behavior:
# - Skips base artists with NO songs in specified year(s)
# - For similar artists, checks each candidate for year content
# - If similar artist has no matching songs, automatically tries NEXT similar artist
# - Downloads top N tracks (already sorted by Yandex by popularity)
# - Continues through all depth levels to find artists with matching content
```

### 9. Create Archive After Download
```bash
# Download and create ZIP archive
ymusic-cli -a "9045812" -n 10 -o ./downloads --archive

# Custom archive name
ymusic-cli -a "9045812" -n 10 -o ./downloads --archive --archive-name "xushnud_top_10"

# Shuffle and archive combined
ymusic-cli -a "9045812,10393751" -n 5 --shuffle --archive -o ./downloads
```

## Parameters

### Required
- `-a, --artist-id ID` - Yandex Music artist ID(s) (comma-separated for multiple: "123,456,789")

### Optional
- `-o, --output-dir DIR` - Output directory (default: `./storage/downloads`)

### Discovery Options
- `-n, --tracks N` - Tracks per artist (default: 10)
- `-s, --similar N` - Similar artists count (default: 0 = base only)
- `-d, --depth N` - Recursive depth (default: 0 = no recursion)

### Filters
- `-y, --years RANGE` - Year filter (e.g., "2025" or "2024-2025"). When used with discovery, enables smart filtering:
  - Skips base artists without year content
  - Automatically tries next similar artists if one doesn't have year content
  - Tracks are already sorted by Yandex by popularity (no manual sorting needed)
- `-c, --countries LIST` - Country codes (e.g., "US,GB,CA")
- `--exclude IDS` - Exclude artist IDs

### Download Options
- `-q, --quality LEVEL` - Audio quality: low/medium/high (default: high)
- `-p, --parallel N` - Parallel downloads (default: 2)

### File Organization
- `--shuffle` - Shuffle all songs into one folder with numeric prefixes (001_, 002_, etc.)
- `--archive` / `--zip` - Create a ZIP archive of all downloaded tracks after completion
- `--archive-name NAME` - Custom archive filename (without .zip extension). Default: auto-generated from output directory and timestamp

### Utility
- `-v, --verbose` - Enable verbose logging
- `-h, --help` - Show help message

## Discovery Modes

### Base Artist Only (Default)
```bash
ymusic-cli -a 9045812 -o ./music
```
Downloads only from the base artist.

### Flat Discovery
```bash
ymusic-cli -a 9045812 -s 15 -o ./music
```
Base artist + 15 similar artists (16 total).

### Recursive Discovery (Depth 1)
```bash
ymusic-cli -a 9045812 -s 10 -d 1 -o ./music
```
Base → 10 similar → 10 similar from each = up to 111 unique artists.

## Getting Artist IDs

### Method 1: Yandex Music Website
1. Visit https://music.yandex.ru/
2. Search for the artist
3. Copy ID from URL: `https://music.yandex.ru/artist/9045812`
   - The ID is `9045812`

### Method 2: Search in Browser
Search "artist name yandex music" and get ID from the URL.

## Requirements

- Python 3.9+
- Yandex Music account
- Yandex Music Session ID token

## Dependencies

- `yandex-music` - Yandex Music API client
- `aiohttp` - Async HTTP requests
- `aiofiles` - Async file operations
- `mutagen` - Audio metadata handling
- `tqdm` - Progress bars
- `python-dotenv` - Configuration management

## Troubleshooting

### Error: "Artist not found"
- Verify the artist ID is correct
- Check the URL on https://music.yandex.ru/

### Error: "Failed to initialize services"
- Ensure `.env` file exists with valid `YANDEX_TOKEN`
- Check token is not expired

### No tracks downloaded
- Artist might not have tracks matching your filters
- Try without filters: remove `-y` and `-c`
- Use `-v` flag for detailed logs

### Progress bars not showing
- Install tqdm: `pip install tqdm`
- Progress bars are optional

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Author

devmansurov

## Acknowledgments

- [yandex-music-api](https://github.com/MarshalX/yandex-music-api) for the excellent Yandex Music API client

---

**Enjoy discovering and downloading music! 🎵**
