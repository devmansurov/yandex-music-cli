# Music Discovery CLI Tool

A powerful command-line tool for automated artist discovery and track downloading from Yandex Music. This tool leverages all existing bot services to discover similar artists recursively and download their top tracks with extensive filtering options.

## Features

- ✅ Download top N songs from any artist
- ✅ Discover and download from similar artists
- ✅ Recursive artist discovery (similar artists of similar artists)
- ✅ Advanced filtering (years, countries, exclude artists)
- ✅ Shuffle mode with automatic numbering
- ✅ Organized folder structure or flat layout
- ✅ Concurrent downloads with progress tracking
- ✅ Smart caching to avoid re-downloads
- ✅ Quality selection (high/medium/low)

## Installation

### Prerequisites

1. **Python 3.9+** with the bot's virtual environment
2. **Yandex Music Token** (already configured in your bot)
3. **Optional: tqdm** for progress bars (recommended)

### Install tqdm (Optional but Recommended)

```bash
cd /home/devmansurov/Projects/Personal/ymusic/server/bot
source venv/bin/activate
pip install tqdm
```

## Usage

### Basic Syntax

```bash
cd /home/devmansurov/Projects/Personal/ymusic/server/bot
source venv/bin/activate

python scripts/music_discovery_cli.py -a <ARTIST_ID> -o <OUTPUT_DIR> [OPTIONS]
```

### Required Arguments

| Short | Long | Description | Example |
|-------|------|-------------|---------|
| `-a` | `--artist-id` | Yandex Music artist ID | `-a 9045812` |
| `-o` | `--output-dir` | Output directory for downloads | `-o ./my_music` |

### Discovery Options

| Short | Long | Default | Description |
|-------|------|---------|-------------|
| `-n` | `--tracks` | 10 | Number of top tracks per artist |
| `-s` | `--similar` | 0 | Similar artists count (0 = only base artist) |
| `-d` | `--depth` | 0 | Recursive depth (0 = no recursion) |

**Important:**
- `-s 0` downloads only from the base artist (default)
- `-s 15` downloads from base + 15 similar artists
- `-s 10 -d 1` does recursive discovery (depth 1) with 10 similar per artist

### Filter Options

| Short | Long | Description | Example |
|-------|------|-------------|---------|
| | `--exclude` | Artist IDs to exclude | `--exclude 123,456,789` |
| `-y` | `--years` | Year filter (single or range) | `-y 2020-2024` or `-y 2023` |
| `-c` | `--countries` | Country codes | `-c US,GB,CA` |

### Download Options

| Short | Long | Default | Description |
|-------|------|---------|-------------|
| `-q` | `--quality` | high | Audio quality (low/medium/high) |
| `-p` | `--parallel` | 2 | Maximum parallel downloads |
| | `--shuffle` | false | Shuffle with numeric prefixes |

### Utility Options

| Short | Long | Description |
|-------|------|-------------|
| `-v` | `--verbose` | Enable verbose logging |

## Examples

### 1. Download Top 10 Songs from a Single Artist

Download the top 10 songs from artist ID 9045812 only (no similar artists):

```bash
python scripts/music_discovery_cli.py -a 9045812 -n 10 -o ./downloads
```

**Output structure:**
```
downloads/
└── Artist Name/
    ├── Artist Name - Song 1.mp3
    ├── Artist Name - Song 2.mp3
    └── ... (10 songs total)
```

### 2. Download from Artist + 15 Similar Artists (Flat Mode)

Download top 10 songs from the base artist and 15 similar artists:

```bash
python scripts/music_discovery_cli.py -a 9045812 -n 10 -s 15 -o ./downloads
```

**Output structure:**
```
downloads/
├── Artist Name 1/
│   └── ... (10 songs)
├── Artist Name 2/
│   └── ... (10 songs)
└── ... (16 artists total: 1 base + 15 similar)
```

**Total tracks:** ~160 (16 artists × 10 songs)

### 3. Recursive Discovery (Depth 1)

Download from base artist, 10 similar artists, and 10 similar artists from each of those:

```bash
python scripts/music_discovery_cli.py -a 9045812 -n 10 -s 10 -d 1 -o ./downloads
```

**Discovery process:**
1. Base artist → 10 similar artists (depth 0)
2. Each of those 10 artists → 10 more similar artists each (depth 1)
3. **Total artists:** 1 + 10 + (10 × 10) = up to 111 artists

**Note:** Duplicate artists are automatically filtered out.

### 4. Download with Shuffle Mode

Download and shuffle all songs into one folder with numeric prefixes:

```bash
python scripts/music_discovery_cli.py -a 9045812 -n 5 -s 20 --shuffle -o ./downloads
```

**Output structure:**
```
downloads/
├── 001_Artist Name - Song Title.mp3
├── 002_Another Artist - Another Song.mp3
├── 003_Artist Name - Different Song.mp3
└── ... (all songs shuffled with numeric prefixes)
```

### 5. Download with Year Filter (2020-2024)

Download only songs released between 2020 and 2024:

```bash
python scripts/music_discovery_cli.py -a 9045812 -n 10 -y 2020-2024 -o ./downloads
```

### 6. Download with Multiple Filters

Combine multiple filters for precise control:

```bash
python scripts/music_discovery_cli.py \
  -a 9045812 \
  -n 5 \
  -s 20 \
  -y 2020-2024 \
  -c US,GB \
  --exclude 12345,67890 \
  -q high \
  -p 3 \
  -o ./downloads
```

### 7. Verbose Mode for Debugging

Enable detailed logging to troubleshoot issues:

```bash
python scripts/music_discovery_cli.py -a 9045812 -n 5 -o ./downloads -v
```

## Understanding Discovery Modes

The `-s` (similar) and `-d` (depth) parameters control how artists are discovered:

### Mode 1: Base Artist Only (Default)
```bash
-a 9045812 -s 0  # or just -a 9045812 (default)
```
- Downloads only from the base artist
- No similar artist discovery

### Mode 2: Flat Discovery
```bash
-a 9045812 -s 15
```
- Base artist + 15 similar artists
- No recursion (depth = 0)
- **Result:** 16 artists total

### Mode 3: Recursive Discovery (Depth 1)
```bash
-a 9045812 -s 10 -d 1
```
- Base artist → 10 similar artists (level 0)
- Each similar artist → 10 more similar artists (level 1)
- **Result:** Up to 111 unique artists

### Mode 4: Recursive Discovery (Depth 2)
```bash
-a 9045812 -s 10 -d 2
```
- Base → 10 similar (level 0)
- Each level 0 → 10 similar (level 1)
- Each level 1 → 10 similar (level 2)
- **Result:** Could be 1000+ artists!

⚠️ **Warning:** Higher depths can result in very large numbers of artists. Start with lower values.

## Output Organization

### Default Mode (Organized by Artist)

Each artist gets their own folder:

```
output-dir/
├── Artist Name 1/
│   ├── Artist Name 1 - Song 1.mp3
│   └── Artist Name 1 - Song 2.mp3
├── Artist Name 2/
│   ├── Artist Name 2 - Song 1.mp3
│   └── Artist Name 2 - Song 2.mp3
└── ...
```

### Shuffle Mode

All songs in one folder with numeric prefixes:

```
output-dir/
├── 001_Artist Name - Song Title.mp3
├── 002_Different Artist - Song Title.mp3
├── 003_Artist Name - Another Song.mp3
└── ...
```

## Advanced Use Cases

### Testing Before Large Downloads

Always test with small numbers first:

```bash
# Test with just 2 songs and 2 similar artists
python scripts/music_discovery_cli.py -a 9045812 -n 2 -s 2 -o ./test -v
```

### High-Performance Downloading

Increase parallel downloads for faster completion:

```bash
python scripts/music_discovery_cli.py -a 9045812 -n 10 -s 20 -p 5 -o ./downloads
```

### Creating a Discovery Playlist

Use shuffle mode with filters:

```bash
python scripts/music_discovery_cli.py \
  -a 9045812 \
  -n 5 \
  -s 30 \
  -y 2020-2024 \
  --shuffle \
  -o ./playlist_2020s
```

## Parameter Validation

The CLI includes smart validation:

```bash
# ERROR: Recursive depth requires similar artists
python scripts/music_discovery_cli.py -a 9045812 -d 1 -s 0
# Error: --depth > 0 requires --similar > 0

# OK: Valid recursive configuration
python scripts/music_discovery_cli.py -a 9045812 -d 1 -s 10
```

## Performance Considerations

### Download Speed

- Default: 2 parallel downloads
- Recommended: 3-5 for optimal balance
- Maximum: Don't exceed 10 to avoid API rate limiting

### Caching

The tool uses the bot's caching system:
- Downloaded tracks are cached
- Similar artist data is cached
- Re-running with same artist IDs will be much faster

### Disk Space

Estimate required space:
- **Average song:** ~5-10 MB (high quality)
- **Example:** 100 artists × 10 songs × 7 MB = ~7 GB

## Troubleshooting

### Error: "Artist not found"

- Verify the artist ID is correct
- Try searching on https://music.yandex.ru/
- The artist ID is in the URL: `https://music.yandex.ru/artist/9045812`

### Error: "Failed to initialize services"

- Check that `.env` file has valid `YANDEX_TOKEN`
- Ensure virtual environment is activated
- Verify bot dependencies are installed: `pip install -r requirements.txt`

### No tracks downloaded

- Artist might not have tracks matching your filters
- Try removing filters (`-y`, `-c`)
- Check with `-v` flag for detailed logs

### Progress bars not showing

- Install tqdm: `pip install tqdm`
- Progress bars enhance the experience but are optional

### Downloads are slow

- Increase parallel downloads: `-p 5`
- Check your internet connection
- Yandex API might be rate-limiting (wait and retry)

## Tips and Best Practices

1. **Start small:** Test with `-n 2 -s 2` first
2. **Use verbose mode:** Add `-v` when testing or debugging
3. **Organize outputs:** Create separate directories for different discovery runs
4. **Check disk space:** Monitor available space for large downloads
5. **Respect API limits:** Don't set `-p` too high
6. **Use filters wisely:** Combine `-y` and `-c` to narrow results

## Getting Artist IDs

### Method 1: Yandex Music Website

1. Go to https://music.yandex.ru/
2. Search for the artist
3. Click on the artist name
4. Copy the ID from the URL: `https://music.yandex.ru/artist/9045812`

### Method 2: Telegram Bot

Use the bot's `/search` command:
```
/search Metallica
```

The bot will show artist IDs in the results.

## Statistics Output

After completion, the tool shows download statistics:

```
============================================================
📊 DOWNLOAD STATISTICS
============================================================
Artists processed:    16
Tracks downloaded:    160
Tracks failed:        0
Total size:           1,234.56 MB
Duration:             180.5 seconds
Avg time per track:   1.13 seconds
============================================================
```

## Backward Compatibility

Old parameter names still work for compatibility:

```bash
# Old syntax (still works)
--artist-id --songs-per-artist --similar-artists --recursive-depth --max-concurrent

# New syntax (recommended)
-a -n -s -d -p
```

---

**Enjoy discovering and downloading music! 🎵**
