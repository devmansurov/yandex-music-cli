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

### 9. Download Recent Hits from Top Popular Songs
```bash
# Get up to 5 songs from 2024-2025 that are in artist's top 10 most popular
ymusic-cli -a 9045812 -n 5 -y 2024-2025 --in-top 10 -o ./downloads

# Get up to 3 songs from 2024-2025 that are in artist's top 5% most popular
# If artist has 100 tracks, this checks top 5 songs
ymusic-cli -a 9045812 -n 3 -y 2024-2025 --in-top 5% -o ./downloads

# Get recent hits from top 15% of artist's catalog with discovery
# If artist has 110 tracks, this checks top 17 songs (110 * 0.15 = 16.5 → 17)
ymusic-cli -a 9045812 -s 20 -n 5 -y 2024-2025 --in-top 15% -o ./downloads

# How --in-top works:
# 1. Gets artist's ALL tracks (already sorted by popularity by Yandex)
# 2. Takes only top N or top N% most popular tracks
# 3. Filters these tracks by year range
# 4. Downloads up to requested number that match BOTH criteria
# 5. Strict mode: If only 2 songs match, downloads only 2 (not 5)
```

### 10. Large-Scale Discovery (300+ Artists)
```bash
# For very large artist lists (300+ artists), use --artists-file to avoid shell command line limits
# Shell command line max length: ~131KB (varies by system)

# Step 1: Create a file with comma-separated artist IDs (one line, no spaces recommended)
cat > artists.txt << 'EOF'
451,1053,1056,1151,1156,1438,1520328,1532779,1555742,1636897,2334946,2429955,2444218...
EOF

# Step 2: Run with --artists-file instead of -a
ymusic-cli --artists-file artists.txt -n 10 --similar 50 --depth 2 -o ./downloads

# For persistent execution on remote servers (survives SSH disconnect):
# Option A: Using nohup
nohup ymusic-cli --artists-file artists.txt -n 10 --similar 50 --depth 2 -o ./downloads > ymusic.log 2>&1 &

# Option B: Using screen
screen -dmS discovery ymusic-cli --artists-file artists.txt -n 10 --similar 50 --depth 2 -o ./downloads
screen -r discovery  # Attach to session

# Benefits of --artists-file:
# ✓ No shell command line length limits
# ✓ Reusable artist lists across multiple runs
# ✓ Easier to manage and version control large artist collections
# ✓ Works with both -a and --artists-file (mutually exclusive)
```

### 11. Progress Resume for Large Operations (New!)
```bash
# When downloading from thousands of artists (e.g., 40,918), enable progress resume
# to avoid restarting from scratch if interrupted

# Start with session name to enable resume capability
ymusic-cli --artists-file artists.txt \
  --session-name my_discovery \
  -n 10 --similar 50 --depth 2 \
  -o ./downloads

# If process is interrupted/killed, resume from exact position
ymusic-cli --artists-file artists.txt \
  --session-name my_discovery \
  --resume \
  -n 10 --similar 50 --depth 2 \
  -o ./downloads

# Reset and start fresh (clears saved progress)
ymusic-cli --artists-file artists.txt \
  --session-name my_discovery \
  --reset-progress \
  -n 10 --similar 50 --depth 2 \
  -o ./downloads

# How progress resume works:
# 1. Saves checkpoint after processing each artist
# 2. Stores progress in Redis (if available) or JSON file
# 3. On --resume, skips all already-processed artists (instant, no API calls)
# 4. Validates command compatibility before resume
# 5. Works with interruptions, errors, or manual stops

# Example: Processing 40,918 artists, interrupted at #890
# Without --resume: Restart checks artists 1-889 (~15 min wasted)
# With --resume:    Skip directly to #890 (< 1 second)

# Benefits:
# ✓ Instant resume - skips processed artists in O(1) time
# ✓ Zero API overhead - no re-checking completed artists
# ✓ Crash recovery - resume from exact position after any failure
# ✓ Session isolation - run multiple sessions with different configs
```

### 12. Batch Processing for Limited Disk Space (New!)
```bash
# Problem: Need to process 40,918 artists (~1TB) but only have 183GB disk space
# Solution: Process in batches, archive, clear, and resume

# Manual batch processing
# Step 1: Process first batch of 1,900 artists
ymusic-cli --artists-file artists.txt \
  --session-name production \
  --max-artists 1900 \
  -n 10 --similar 50 --depth 2 \
  -o ./downloads

# Step 2: Create archive and upload
tar -czf batch1.tar.gz -C ./downloads .
# Upload to cloud storage...

# Step 3: Clear downloads
rm -rf ./downloads/*

# Step 4: Resume next batch
ymusic-cli --artists-file artists.txt \
  --session-name production \
  --resume \
  --max-artists 1900 \
  -n 10 --similar 50 --depth 2 \
  -o ./downloads

# Automated batch processing with script
# The batch_process.sh script automates the entire workflow
./batch_process.sh production_40k 1900 artists_list.txt

# What the script does:
# 1. Processes batch of N artists (--max-artists 1900)
# 2. Creates compressed archive (batch_SESSION_N_TIMESTAMP.tar.gz)
# 3. Verifies archive integrity
# 4. Clears downloads directory
# 5. Resumes from checkpoint for next batch
# 6. Repeats until all artists processed

# How --max-artists works:
# - Stops cleanly after processing N artists in current run
# - Saves checkpoint before stopping
# - Shows resume command for next batch
# - Works with --resume for seamless continuation

# Example: 40,918 artists with 183GB disk
# Batch size: 1,900 artists (~150GB per batch)
# Total batches: ~22 batches
# Timeline: ~2-3 hours per batch = ~60 hours total
# Disk usage: Never exceeds 150GB

# Benefits:
# ✓ Process unlimited artists with limited disk space
# ✓ Automated archive → verify → clear → resume cycle
# ✓ Safe: Verifies archives before clearing downloads
# ✓ Resumable: Can stop/restart at any batch
# ✓ Monitoring: Shows progress and disk space per batch
```

### 13. Create Archive After Download
```bash
# Download and create ZIP archive
ymusic-cli -a "9045812" -n 10 -o ./downloads --archive

# Custom archive name
ymusic-cli -a "9045812" -n 10 -o ./downloads --archive --archive-name "xushnud_top_10"

# Shuffle and archive combined
ymusic-cli -a "9045812,10393751" -n 5 --shuffle --archive -o ./downloads
```

## Parameters

### Required (choose one)
- `-a, --artist-id ID` - Yandex Music artist ID(s) (comma-separated for multiple: "123,456,789")
- `--artists-file FILE` - Path to file containing comma-separated artist IDs (for 300+ artists)

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
- `--in-top N` - Only download tracks in artist's top N most popular songs (requires `--years` filter)
  - **Numeric format:** `--in-top 10` - Check top 10 songs by position
  - **Percentage format:** `--in-top 10%` - Check top 10% of all songs
  - **Strict mode:** Only downloads songs matching BOTH criteria (year + popularity)

### Download Options
- `-q, --quality LEVEL` - Audio quality: low/medium/high (default: high)
- `-p, --parallel N` - Parallel downloads (default: 2)

### File Organization
- `--shuffle` - Shuffle all songs into one folder with numeric prefixes (001_, 002_, etc.)
- `--archive` / `--zip` - Create a ZIP archive of all downloaded tracks after completion
- `--archive-name NAME` - Custom archive filename (without .zip extension). Default: auto-generated from output directory and timestamp

### Progress Management (New!)
- `--session-name NAME` - Unique session name for progress tracking (enables resume on interruption/failure)
- `--resume` / `--continue` - Resume from last checkpoint if session exists (requires `--session-name`)
- `--reset-progress` - Clear saved progress for session and start fresh (requires `--session-name`)
- `--max-artists N` - Stop after processing N artists in this run (for batch processing with limited disk space). Works with `--resume` for batch workflow.

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

## HTTP File Server

The CLI includes a built-in HTTP file server to browse and download your music collection through a web browser.

### Starting the Server

```bash
# Start with defaults from .env
ymusic-serve

# Custom port
ymusic-serve --port 3000

# Serve custom directory
ymusic-serve --dir /path/to/music

# Custom host and port
ymusic-serve --host 127.0.0.1 --port 8888

# Verbose logging
ymusic-serve -v
```

### Configuration

Add to your `.env` file:

```env
# HTTP File Server (optional)
FILE_SERVER_ENABLED=false
FILE_SERVER_HOST=0.0.0.0
FILE_SERVER_PORT=8080
DOWNLOADS_DIR=./storage/downloads
```

### Features

- 🎨 **Beautiful UI** - Clean, modern web interface
- 📁 **Directory Browsing** - Navigate through folders easily
- 🔒 **Security** - Directory traversal protection built-in
- 🎵 **Audio Support** - Proper MIME types for music files
- 📊 **File Information** - File sizes in human-readable format
- 🗺️ **Breadcrumb Navigation** - Easy navigation through directories

### Accessing the Server

Once started, open your browser and navigate to:
- Local access: `http://localhost:8080`
- Network access: `http://YOUR_SERVER_IP:8080`

The server will display all files and folders in your downloads directory. Click on folders to browse, click on files to download.

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
