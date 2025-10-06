#!/usr/bin/env python3
"""
CLI tool for automated artist discovery and track downloading from Yandex Music.

This script leverages all existing bot services to discover similar artists recursively
and download their top tracks with various filtering options.
"""

import sys
import os
import asyncio
import argparse
import logging
import random
from pathlib import Path
from typing import List, Optional, Set
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tqdm import tqdm
except ImportError:
    print("Warning: tqdm not installed. Install with: pip install tqdm")
    print("Progress bars will be disabled.")
    tqdm = None

from config.settings import get_settings
from services.yandex_service import YandexMusicService
from services.download_service import DownloadOrchestrator
from services.discovery_service import ArtistDiscoveryService
from services.cache_service import create_cache_service
from core.models import DownloadOptions, Quality, Artist, Track
from core.exceptions import ServiceError, NotFoundError
from utils.file_manager import FileManager
from utils.progress_tracker import ProgressTracker


class MusicDiscoveryCLI:
    """CLI tool for music discovery and downloads."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.settings = get_settings()
        self.logger = self._setup_logging()

        # Services (to be initialized)
        self.cache_service = None
        self.music_service = None
        self.download_service = None
        self.discovery_service = None
        self.file_manager = None

        # Statistics
        self.stats = {
            'artists_processed': 0,
            'tracks_downloaded': 0,
            'tracks_failed': 0,
            'total_size_mb': 0.0,
            'start_time': None,
            'end_time': None
        }

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        log_level = logging.DEBUG if self.args.verbose else logging.INFO

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )

        # Suppress noisy loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.WARNING)

        return logging.getLogger(__name__)

    async def initialize_services(self) -> None:
        """Initialize all required services."""
        self.logger.info("Initializing services...")

        try:
            # Cache service
            self.cache_service = create_cache_service()
            self.logger.debug("✓ Cache service initialized")

            # Yandex Music service
            self.music_service = YandexMusicService(
                self.settings.yandex.token,
                self.cache_service
            )
            await self.music_service.initialize()
            self.logger.debug("✓ Yandex Music service initialized")

            # File manager
            self.file_manager = FileManager(
                temp_dir=self.settings.files.temp_dir,
                storage_dir=self.settings.files.storage_dir
            )
            self.logger.debug("✓ File manager initialized")

            # Download service
            self.download_service = DownloadOrchestrator(
                music_service=self.music_service,
                file_manager=self.file_manager,
                progress_tracker=None,
                cache_service=self.cache_service
            )
            await self.download_service.initialize()
            self.logger.debug("✓ Download service initialized")

            # Discovery service
            self.discovery_service = ArtistDiscoveryService(
                music_service=self.music_service,
                cache_service=self.cache_service
            )
            self.logger.debug("✓ Discovery service initialized")

            self.logger.info("✓ All services initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize services: {e}")
            raise

    async def cleanup_services(self) -> None:
        """Cleanup all services."""
        self.logger.info("Cleaning up services...")

        if self.download_service:
            await self.download_service.cleanup()

        self.logger.info("✓ Cleanup complete")

    def _build_download_options(self) -> DownloadOptions:
        """Build download options from CLI arguments."""
        options = DownloadOptions()

        # Basic options
        options.top_n = self.args.tracks
        options.quality = Quality(self.args.quality)
        options.skip_existing = True

        # Similar artists options
        options.similar_limit = self.args.similar
        options.max_depth = self.args.depth
        options.max_total_artists = 999  # No limit, controlled by depth and similar

        # Filters
        if self.args.years:
            start_year, end_year = self._parse_years(self.args.years)
            options.years = (start_year, end_year)

        if self.args.countries:
            options.countries = [c.strip().upper() for c in self.args.countries.split(',')]

        if self.args.exclude:
            options.exclude_artists = set(self.args.exclude.split(','))

        return options

    def _parse_years(self, years_str: str) -> tuple[int, int]:
        """Parse years string to tuple."""
        if '-' in years_str:
            parts = years_str.split('-')
            return int(parts[0]), int(parts[1])
        else:
            year = int(years_str)
            return year, year

    async def discover_artists(self, base_artist_id: str, options: DownloadOptions) -> List[Artist]:
        """Discover artists based on recursive depth."""
        self.logger.info(f"Discovering artists from base artist ID: {base_artist_id}")

        discovered_artists = []

        # Always include base artist
        base_artist = await self.music_service.get_artist(base_artist_id)
        if not base_artist:
            raise NotFoundError(f"Artist {base_artist_id} not found", "artist")

        discovered_artists.append(base_artist)
        self.logger.info(f"✓ Base artist: {base_artist.name}")

        # If no similar artists requested (similar_limit == 0), return just base artist
        if options.similar_limit == 0:
            self.logger.info("No similar artists requested (--similar 0), downloading from base artist only")
            return discovered_artists

        # Discover similar artists
        if self.args.depth == 0:
            # Flat discovery: just get direct similar artists (no recursion)
            self.logger.info(f"Fetching {options.similar_limit} similar artists (flat mode)...")
            similar_artists = await self.music_service.get_similar_artists(
                base_artist_id,
                limit=options.similar_limit
            )

            # Filter by excluded artists
            filtered_similar = [
                a for a in similar_artists
                if a.id not in options.exclude_artists
            ]

            discovered_artists.extend(filtered_similar)
            self.logger.info(f"✓ Found {len(filtered_similar)} similar artists")

        else:
            # Recursive discovery
            self.logger.info(
                f"Starting recursive discovery (depth={self.args.depth}, "
                f"similar_per_artist={options.similar_limit})..."
            )

            result = await self.discovery_service.discover_recursive(
                artist_id=base_artist_id,
                options=options,
                progress_callback=self._discovery_progress_callback
            )

            discovered_artists = result.discovered_artists
            self.logger.info(
                f"✓ Recursive discovery complete: {len(discovered_artists)} total artists "
                f"(max depth: {result.max_depth_reached})"
            )

        return discovered_artists

    async def _discovery_progress_callback(self, progress: dict) -> None:
        """Callback for discovery progress updates."""
        if self.args.verbose:
            depth = progress.get('current_depth', '?')
            artist = progress.get('current_artist', 'Unknown')
            count = progress.get('discovered_count', 0)
            self.logger.debug(f"Discovery: Depth {depth} | Artist: {artist} | Total: {count}")

    async def download_artist_tracks(
        self,
        artist: Artist,
        options: DownloadOptions,
        output_dir: Path
    ) -> List[Track]:
        """Download tracks for a single artist."""
        try:
            # Get artist tracks
            tracks = await self.music_service.get_artist_tracks(
                artist.id,
                options
            )

            if not tracks:
                self.logger.warning(f"No tracks found for artist: {artist.name}")
                return []

            self.logger.info(f"Downloading {len(tracks)} tracks from {artist.name}...")

            # Create artist folder if not shuffling
            if not self.args.shuffle:
                artist_dir = output_dir / self._sanitize_filename(artist.name)
                artist_dir.mkdir(parents=True, exist_ok=True)
            else:
                artist_dir = output_dir

            # Download tracks
            downloaded_tracks = []

            # Create progress bar if tqdm is available
            if tqdm:
                track_iter = tqdm(tracks, desc=f"  {artist.name}", unit="track", leave=False)
            else:
                track_iter = tracks

            for track in track_iter:
                try:
                    # Generate filename
                    filename = self._generate_track_filename(track, artist)
                    output_path = artist_dir / filename

                    # Skip if file exists
                    if output_path.exists():
                        self.logger.debug(f"Skipping existing: {filename}")
                        self.stats['tracks_downloaded'] += 1
                        downloaded_tracks.append(track)
                        continue

                    # Download track
                    success = await self.download_service.download_track(track, output_path)

                    if success:
                        downloaded_tracks.append(track)
                        self.stats['tracks_downloaded'] += 1

                        # Update size statistics
                        if output_path.exists():
                            size_mb = output_path.stat().st_size / (1024 * 1024)
                            self.stats['total_size_mb'] += size_mb
                    else:
                        self.stats['tracks_failed'] += 1
                        self.logger.warning(f"Failed to download: {track.title}")

                except Exception as e:
                    self.stats['tracks_failed'] += 1
                    self.logger.error(f"Error downloading track {track.title}: {e}")
                    continue

            self.logger.info(
                f"✓ Downloaded {len(downloaded_tracks)}/{len(tracks)} tracks from {artist.name}"
            )

            return downloaded_tracks

        except Exception as e:
            self.logger.error(f"Error processing artist {artist.name}: {e}")
            return []

    def _generate_track_filename(self, track: Track, artist: Artist) -> str:
        """Generate filename for a track."""
        title = self._sanitize_filename(track.title)
        artist_name = self._sanitize_filename(artist.name)

        filename = f"{artist_name} - {title}.mp3"

        # Ensure filename isn't too long
        if len(filename) > 200:
            filename = filename[:197] + "..."

        return filename

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename by removing invalid characters."""
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)
        return sanitized.strip()

    async def shuffle_and_renumber_tracks(self, output_dir: Path) -> None:
        """Shuffle all tracks and add numeric prefixes."""
        self.logger.info("Shuffling tracks and adding numeric prefixes...")

        # Get all MP3 files
        all_files = list(output_dir.rglob("*.mp3"))

        if not all_files:
            self.logger.warning("No tracks found to shuffle")
            return

        # Shuffle files
        random.shuffle(all_files)

        # Create temporary directory for shuffled files
        temp_dir = output_dir / "_shuffled_temp"
        temp_dir.mkdir(exist_ok=True)

        # Move and rename files with numeric prefixes
        self.logger.info(f"Renumbering {len(all_files)} tracks...")

        for i, file_path in enumerate(all_files, start=1):
            # Generate new filename with numeric prefix
            prefix = f"{i:03d}_"  # e.g., 001_, 002_, etc.
            new_filename = prefix + file_path.name
            new_path = temp_dir / new_filename

            # Move file
            file_path.rename(new_path)

        # Remove old artist directories
        for item in output_dir.iterdir():
            if item.is_dir() and item != temp_dir:
                import shutil
                shutil.rmtree(item)

        # Move all files from temp directory to output directory
        for file_path in temp_dir.iterdir():
            file_path.rename(output_dir / file_path.name)

        # Remove temp directory
        temp_dir.rmdir()

        self.logger.info(f"✓ Shuffled and renumbered {len(all_files)} tracks")

    async def run(self) -> None:
        """Main execution flow."""
        self.stats['start_time'] = datetime.now()

        try:
            # Initialize services
            await self.initialize_services()

            # Build download options
            options = self._build_download_options()

            # Create output directory
            output_dir = Path(self.args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Output directory: {output_dir}")

            # Discover artists
            artists = await self.discover_artists(self.args.artist_id, options)
            self.stats['artists_processed'] = len(artists)

            self.logger.info(f"\nProcessing {len(artists)} artists...")

            # Download tracks from all artists
            all_downloaded_tracks = []

            # Create progress bar for artists if tqdm is available
            if tqdm:
                artist_iter = tqdm(artists, desc="Artists", unit="artist")
            else:
                artist_iter = artists

            for artist in artist_iter:
                tracks = await self.download_artist_tracks(artist, options, output_dir)
                all_downloaded_tracks.extend(tracks)

                # Respect max concurrent downloads setting
                if self.args.parallel < 5:
                    await asyncio.sleep(0.5)  # Small delay between artists

            # Apply shuffle if requested
            if self.args.shuffle and all_downloaded_tracks:
                await self.shuffle_and_renumber_tracks(output_dir)

            # Print final statistics
            self.stats['end_time'] = datetime.now()
            self._print_statistics()

        except KeyboardInterrupt:
            self.logger.warning("\n\n⚠️  Process interrupted by user")
            self._print_statistics()

        except Exception as e:
            self.logger.error(f"\n\n❌ Error: {e}", exc_info=self.args.verbose)
            raise

        finally:
            await self.cleanup_services()

    def _print_statistics(self) -> None:
        """Print download statistics."""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds() if self.stats['end_time'] else 0

        print("\n" + "="*60)
        print("📊 DOWNLOAD STATISTICS")
        print("="*60)
        print(f"Artists processed:    {self.stats['artists_processed']}")
        print(f"Tracks downloaded:    {self.stats['tracks_downloaded']}")
        print(f"Tracks failed:        {self.stats['tracks_failed']}")
        print(f"Total size:           {self.stats['total_size_mb']:.2f} MB")
        print(f"Duration:             {duration:.1f} seconds")

        if duration > 0 and self.stats['tracks_downloaded'] > 0:
            avg_time = duration / self.stats['tracks_downloaded']
            print(f"Avg time per track:   {avg_time:.2f} seconds")

        print("="*60 + "\n")


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="CLI tool for automated artist discovery and track downloading from Yandex Music",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download 10 songs from a single artist (base artist only)
  %(prog)s -a 9045812 -n 10 -o ./downloads

  # Download from artist + 15 similar artists (flat mode)
  %(prog)s -a 9045812 -n 10 -s 15 -o ./downloads

  # Recursive discovery (depth 1) with 10 similar artists per artist
  %(prog)s -a 9045812 -n 10 -s 10 -d 1 -o ./downloads

  # Download with shuffle and year filter
  %(prog)s -a 9045812 -n 5 -s 20 --shuffle -y 2020-2024 -o ./downloads

  # Exclude specific artists and use parallel downloads
  %(prog)s -a 9045812 -s 15 --exclude 123,456,789 -p 3 -o ./downloads
        """
    )

    # Required arguments
    parser.add_argument(
        '-a', '--artist-id',
        type=str,
        required=True,
        metavar='ID',
        help='Base artist ID from Yandex Music'
    )

    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        required=True,
        metavar='DIR',
        help='Output directory for downloaded tracks'
    )

    # Discovery options
    parser.add_argument(
        '-n', '--tracks', '--songs-per-artist',
        type=int,
        default=10,
        metavar='N',
        dest='tracks',
        help='Number of top tracks to download per artist (default: 10)'
    )

    parser.add_argument(
        '-s', '--similar', '--similar-artists',
        type=int,
        default=0,
        metavar='N',
        dest='similar',
        help='Number of similar artists to discover per artist (default: 0, only base artist)'
    )

    parser.add_argument(
        '-d', '--depth', '--recursive-depth',
        type=int,
        default=0,
        metavar='N',
        dest='depth',
        help='Recursive depth for similar artist discovery (default: 0, no recursion)'
    )

    # Filters
    parser.add_argument(
        '--exclude', '--exclude-artists',
        type=str,
        metavar='IDS',
        dest='exclude',
        help='Comma-separated list of artist IDs to exclude'
    )

    parser.add_argument(
        '-y', '--years',
        type=str,
        metavar='RANGE',
        help='Year filter, e.g. "2020" or "2020-2024"'
    )

    parser.add_argument(
        '-c', '--countries',
        type=str,
        metavar='LIST',
        help='Comma-separated country codes, e.g. "US,GB,CA"'
    )

    # File organization
    parser.add_argument(
        '--shuffle',
        action='store_true',
        help='Shuffle all songs into one folder with numeric prefixes (001_, 002_, etc.)'
    )

    # Download options
    parser.add_argument(
        '-q', '--quality',
        type=str,
        choices=['low', 'medium', 'high'],
        default='high',
        metavar='LEVEL',
        help='Audio quality: low, medium, or high (default: high)'
    )

    parser.add_argument(
        '-p', '--parallel', '--max-concurrent',
        type=int,
        default=2,
        metavar='N',
        dest='parallel',
        help='Maximum parallel downloads (default: 2)'
    )

    # Utility options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging for debugging'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.depth < 0:
        parser.error("--depth must be >= 0")

    if args.tracks < 1:
        parser.error("--tracks must be >= 1")

    if args.similar < 0:
        parser.error("--similar must be >= 0")

    if args.parallel < 1:
        parser.error("--parallel must be >= 1")

    # Validate logical consistency
    if args.depth > 0 and args.similar == 0:
        parser.error("--depth > 0 requires --similar > 0 (recursive discovery needs similar artists)")

    # Update settings for max concurrent downloads
    settings = get_settings()
    settings.limits.max_concurrent_downloads = args.parallel

    # Run the CLI
    cli = MusicDiscoveryCLI(args)

    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
