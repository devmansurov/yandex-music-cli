# Quick Start Guide

## Setup

```bash
cd /home/devmansurov/Projects/Personal/ymusic/server/bot
source venv/bin/activate
```

## Basic Usage

### 1. Download from Single Artist (Base Only)
```bash
python scripts/music_discovery_cli.py -a 9045812 -n 10 -o ./my_music
```

### 2. Discover Similar Artists (Flat Mode)
```bash
python scripts/music_discovery_cli.py -a 9045812 -n 5 -s 15 -o ./my_music
```

### 3. Recursive Discovery
```bash
python scripts/music_discovery_cli.py -a 9045812 -n 5 -s 10 -d 1 -o ./my_music
```

### 4. Shuffle Mode
```bash
python scripts/music_discovery_cli.py -a 9045812 -n 10 -s 20 --shuffle -o ./my_music
```

### 5. With Filters
```bash
python scripts/music_discovery_cli.py -a 9045812 -n 10 -y 2020-2024 -c US,GB -q high -o ./my_music
```

## Quick Reference

| Short | Long | Default | Description |
|-------|------|---------|-------------|
| `-a` | `--artist-id` | **Required** | Yandex Music artist ID |
| `-o` | `--output-dir` | **Required** | Output directory |
| `-n` | `--tracks` | 10 | Tracks per artist |
| `-s` | `--similar` | 0 | Similar artists (0 = base only) |
| `-d` | `--depth` | 0 | Recursive depth |
| `-y` | `--years` | none | Year filter (e.g., 2020-2024) |
| `-c` | `--countries` | none | Country codes (e.g., US,GB) |
| `-q` | `--quality` | high | Audio quality |
| `-p` | `--parallel` | 2 | Parallel downloads |
| | `--shuffle` | false | Shuffle with numeric prefixes |
| | `--exclude` | none | Exclude artist IDs |
| `-v` | `--verbose` | false | Detailed logging |

## Discovery Modes

### Base Artist Only (Default)
```bash
-a 9045812 -o ./music
# or explicitly: -a 9045812 -s 0 -o ./music
```

### Flat Discovery (Base + Similar)
```bash
-a 9045812 -s 15 -o ./music
# Downloads from 16 artists (1 base + 15 similar)
```

### Recursive (Depth 1)
```bash
-a 9045812 -s 10 -d 1 -o ./music
# Downloads from up to 111 artists (1 + 10 + 10×10)
```

## Tips

1. **Start small:** Test with `-n 2 -s 2` first
2. **Use verbose:** Add `-v` when debugging
3. **Shuffle later:** Run without `--shuffle` first, shuffle if needed
4. **Monitor space:** Check disk space for large downloads
5. **Validation:** `-d > 0` requires `-s > 0`

## Common Patterns

```bash
# Quick test run
python scripts/music_discovery_cli.py -a 9045812 -n 2 -s 2 -o ./test -v

# High quality playlist
python scripts/music_discovery_cli.py -a 9045812 -n 5 -s 30 -y 2020-2024 --shuffle -o ./playlist

# Fast parallel download
python scripts/music_discovery_cli.py -a 9045812 -n 10 -s 20 -p 5 -o ./downloads

# Filtered discovery
python scripts/music_discovery_cli.py -a 9045812 -s 15 -y 2020-2024 -c US,GB --exclude 123,456 -o ./music
```

## Getting Artist IDs

1. Visit https://music.yandex.ru/
2. Search for the artist
3. Copy ID from URL: `https://music.yandex.ru/artist/9045812`

Or use the bot's `/search` command.

## Backward Compatibility

Old parameter names still work:
```bash
# Old (still works)
--artist-id --songs-per-artist --similar-artists --recursive-depth --max-concurrent --include-similar

# New (recommended)
-a -n -s -d -p
```

**Note:** `--include-similar` is no longer needed. Just set `-s > 0` to include similar artists.

## Full Documentation

See [README_CLI.md](README_CLI.md) for complete documentation.
