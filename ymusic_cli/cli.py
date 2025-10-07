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

from ymusic_cli.config.settings import get_settings
from ymusic_cli.services.yandex_service import YandexMusicService
from ymusic_cli.services.download_service import DownloadOrchestrator
from ymusic_cli.services.discovery_service import ArtistDiscoveryService
from ymusic_cli.services.cache_service import create_cache_service
from ymusic_cli.services.progress_service import ProgressService
from ymusic_cli.core.models import DownloadOptions, Quality, Artist, Track
from ymusic_cli.core.exceptions import ServiceError, NotFoundError
from ymusic_cli.utils.file_manager import FileManager
from ymusic_cli.utils.progress_tracker import ProgressTracker


class MusicDiscoveryCLI:
    """CLI tool for music discovery and downloads."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.settings = get_settings()
        self.logger = self._setup_logging()

        # Use default output directory from settings if not specified
        if self.args.output_dir is None:
            self.args.output_dir = str(self.settings.file_server.downloads_dir)

        # Services (to be initialized)
        self.cache_service = None
        self.music_service = None
        self.download_service = None
        self.discovery_service = None
        self.file_manager = None
        self.progress_service = None

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
        """Setup logging with file output using CommandLogger."""
        from ymusic_cli.utils.logger import CommandLogger

        # Extract command parameters for log naming
        command_params = {
            'artist_ids': self.args.artist_id.split(',') if hasattr(self.args, 'artist_id') and self.args.artist_id else [],
            'similar': getattr(self.args, 'similar', 0),
            'depth': getattr(self.args, 'depth', 0),
            'years': self._parse_years(self.args.years) if hasattr(self.args, 'years') and self.args.years else None,
            'tracks': getattr(self.args, 'tracks', 0),
            'in_top_n': getattr(self.args, 'in_top_n', None),
            'archive': getattr(self.args, 'archive', False),
        }

        # Determine log level
        log_level = "DEBUG" if self.args.verbose else self.settings.logging.level

        # Create command logger
        self.command_logger = CommandLogger(
            log_dir=self.settings.logging.log_dir,
            command_params=command_params,
            log_to_file=self.settings.logging.log_to_file,
            log_to_console=self.settings.logging.log_to_console,
            log_level=log_level
        )

        logger = self.command_logger.get_logger()

        # Suppress noisy loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("telegram").setLevel(logging.WARNING)

        # Log to file notification
        if self.settings.logging.log_to_file:
            log_path = self.command_logger.get_log_path()
            print(f"📝 Logging to: {log_path}\n")

        return logger

    async def initialize_services(self) -> None:
        """Initialize all required services."""
        self.logger.info("Initializing services...")

        try:
            # Cache service (with optional Redis support)
            self.cache_service = create_cache_service()

            # Initialize cache (required for Redis async connection)
            if hasattr(self.cache_service, 'initialize'):
                await self.cache_service.initialize()

            # Log cache type
            if hasattr(self.cache_service, 'use_redis'):
                cache_type = "Redis with in-memory fallback" if self.cache_service.use_redis else "In-Memory"
            else:
                cache_type = "In-Memory"
            self.logger.info(f"✓ Cache service initialized ({cache_type})")

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

            # Progress service (for resumable operations)
            self.progress_service = ProgressService(cache_service=self.cache_service)
            self.logger.debug("✓ Progress service initialized")

            self.logger.info("✓ All services initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize services: {e}")
            raise

    async def cleanup_services(self) -> None:
        """Cleanup all services."""
        self.logger.info("Cleaning up services...")

        if self.download_service:
            await self.download_service.cleanup()

        # Cleanup cache service (important for Redis connections)
        if self.cache_service and hasattr(self.cache_service, 'cleanup'):
            await self.cache_service.cleanup()

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

            # Enable year-based discovery filtering
            options.enable_year_filtering_for_discovery = True
            options.skip_artists_without_year_content = True

        # Parse --in-top filter (requires --years)
        if self.args.in_top:
            if not self.args.years:
                raise ValueError("--in-top requires --years filter to be specified")

            try:
                in_top_n, in_top_percent = self._parse_in_top(self.args.in_top)
                options.in_top_n = in_top_n
                options.in_top_percent = in_top_percent
            except ValueError as e:
                raise ValueError(f"Invalid --in-top value: {e}")

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

    def _parse_in_top(self, value: str) -> tuple[Optional[int], Optional[float]]:
        """Parse --in-top value to either numeric or percentage.

        Args:
            value: String like "10" or "10%"

        Returns:
            Tuple of (numeric_value, percentage_value) where one is None

        Raises:
            ValueError: If value is invalid
        """
        if not value:
            return None, None

        value = value.strip()

        # Check if percentage
        if value.endswith('%'):
            try:
                percent = float(value[:-1])
                if percent <= 0 or percent > 100:
                    raise ValueError(f"Percentage must be between 0 and 100, got {percent}%")
                return None, percent
            except ValueError as e:
                if "could not convert" in str(e):
                    raise ValueError(f"Invalid percentage format: {value}. Use format like '10%'")
                raise

        # Otherwise numeric
        try:
            numeric = int(value)
            if numeric <= 0:
                raise ValueError(f"Numeric value must be positive, got {numeric}")
            return numeric, None
        except ValueError:
            raise ValueError(f"Invalid --in-top value: {value}. Use numeric (e.g., '10') or percentage (e.g., '10%')")

    async def discover_artists(self, base_artist_id: str, options: DownloadOptions) -> List[Artist]:
        """Discover artists based on recursive depth."""
        self.logger.info(f"Discovering artists from base artist ID: {base_artist_id}")

        discovered_artists = []

        # Always include base artist
        base_artist = await self.music_service.get_artist(base_artist_id)
        if not base_artist:
            raise NotFoundError(f"Artist {base_artist_id} not found", "artist")

        # Check if base artist has content in year range (if year filtering is enabled)
        if options.enable_year_filtering_for_discovery and options.years:
            has_content = await self.music_service.check_artist_has_content_in_years(
                base_artist_id, options.years
            )
            if not has_content:
                self.logger.info(
                    f"✗ Base artist {base_artist.name} has no content in {options.years[0]}-{options.years[1]}"
                )
                self.logger.info(
                    f"  → Continuing to discover similar artists (they may have content in this range)..."
                )
                # Don't add base artist to results, but continue to similar artist discovery
            else:
                discovered_artists.append(base_artist)
                self.logger.info(f"✓ Base artist: {base_artist.name}")
        else:
            # No year filtering, always add base artist
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
                # More informative message based on filters
                if (options.in_top_n or options.in_top_percent) and options.years:
                    in_top_str = f"{options.in_top_n}" if options.in_top_n else f"{options.in_top_percent}%"
                    self.logger.info(
                        f"  ✗ {artist.name}: No tracks in top {in_top_str} matching {options.years[0]}-{options.years[1]}"
                    )
                else:
                    self.logger.info(f"  ✗ {artist.name}: No tracks found")
                return []

            self.logger.info(f"  → Downloading {len(tracks)} tracks from {artist.name}...")

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

                    # Extract year for filename generation
                    year = None
                    if track.year:
                        year = track.year
                    elif hasattr(self.args, 'years') and self.args.years:
                        try:
                            start_year, end_year = self._parse_years(self.args.years)
                            if start_year == end_year:
                                year = start_year
                        except:
                            pass

                    # Download track with artist and year for enhanced cache filenames
                    success = await self.download_service.download_track(
                        track,
                        output_path,
                        artist=artist,
                        year=year
                    )

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
                f"  ✓ Downloaded {len(downloaded_tracks)}/{len(tracks)} tracks from {artist.name}"
            )

            return downloaded_tracks

        except Exception as e:
            self.logger.error(f"Error processing artist {artist.name}: {e}")
            return []

    def _generate_track_filename(self, track: Track, artist: Artist) -> str:
        """Generate enhanced filename for a track with metadata.

        Format: {ArtistName} - {TrackTitle} [{Year}] [AID{ArtistID}] [TID{TrackID}].mp3
        Example: Юлдуз Усманова - Sevaman seni [2024] [AID328849] [TID142345678].mp3
        """
        # Get base components
        title = self._sanitize_filename(track.title)
        artist_name = self._sanitize_filename(artist.name)

        # Get year from track or filter
        year = None
        if track.year:
            year = track.year
        elif hasattr(self.args, 'years') and self.args.years:
            # Use year range from filter
            try:
                start_year, end_year = self._parse_years(self.args.years)
                if start_year == end_year:
                    year = start_year
                # else: year range ambiguous, skip year in filename
            except:
                pass

        # Build filename components
        # Format: {ArtistName} - {TrackTitle} [{Year}] [AID{ArtistID}] [TID{TrackID}].mp3
        parts = [f"{artist_name} - {title}"]

        # Add year if available
        if year:
            parts.append(f"[{year}]")

        # Add Artist ID
        parts.append(f"[AID{artist.id}]")

        # Add Track ID
        parts.append(f"[TID{track.id}]")

        filename = " ".join(parts) + ".mp3"

        # Ensure filename isn't too long (filesystem limit ~255 chars)
        if len(filename) > 250:
            # Calculate how much space we need for metadata
            metadata_suffix = ""
            if year:
                metadata_suffix += f" [{year}]"
            metadata_suffix += f" [AID{artist.id}] [TID{track.id}].mp3"

            # Truncate title part to fit
            max_base_len = 250 - len(metadata_suffix) - len(artist_name) - 3  # 3 for " - "
            if max_base_len > 20:  # Ensure we have reasonable space
                title_truncated = title[:max_base_len]
                filename = f"{artist_name} - {title_truncated}{metadata_suffix}"
            else:
                # If artist name is too long, truncate it too
                max_artist_len = 50
                max_title_len = 250 - len(metadata_suffix) - max_artist_len - 3
                artist_truncated = artist_name[:max_artist_len]
                title_truncated = title[:max_title_len] if max_title_len > 0 else ""
                filename = f"{artist_truncated} - {title_truncated}{metadata_suffix}"

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

    async def create_archive(self, output_dir: Path) -> None:
        """Create ZIP archive of downloaded tracks.

        Args:
            output_dir: Directory containing downloaded tracks
        """
        try:
            self.logger.info("Creating archive of downloaded tracks...")

            # Generate archive name
            archive_name = self.args.archive_name
            if not archive_name:
                # Auto-generate from directory name and date
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archive_name = f"{output_dir.name}_{timestamp}"

            # Create archive using file manager
            archive_path = await self.file_manager.create_archive(
                source_dir=output_dir,
                archive_name=archive_name,
                output_dir=output_dir.parent
            )

            # Update statistics
            archive_size_mb = archive_path.stat().st_size / (1024 * 1024)
            self.stats['archive_path'] = str(archive_path)
            self.stats['archive_size_mb'] = archive_size_mb

            self.logger.info(f"✓ Archive created: {archive_path.name} ({archive_size_mb:.2f} MB)")

        except Exception as e:
            self.logger.error(f"Failed to create archive: {e}")
            # Don't fail the entire process if archiving fails

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

            # Parse artist IDs (support comma-separated values)
            artist_ids = [aid.strip() for aid in self.args.artist_id.split(',') if aid.strip()]
            self.logger.info(f"Processing {len(artist_ids)} base artist(s): {', '.join(artist_ids)}")

            # Handle progress checkpoint operations
            checkpoint = None
            command_hash = None

            if self.args.session_name:
                # Generate command hash for compatibility check
                command_hash = self.progress_service.generate_command_hash(
                    artist_ids=artist_ids,
                    similar_limit=options.similar_limit,
                    max_depth=options.max_depth,
                    songs_per_artist=options.songs_per_artist
                )

                # Handle --reset-progress
                if self.args.reset_progress:
                    if await self.progress_service.reset_session(self.args.session_name):
                        self.logger.info(f"✓ Progress reset for session: {self.args.session_name}")
                    else:
                        self.logger.info(f"  No existing progress found for session: {self.args.session_name}")

                # Handle --resume
                elif self.args.resume:
                    checkpoint = await self.progress_service.load_checkpoint(self.args.session_name)
                    if checkpoint:
                        # Validate compatibility
                        if not self.progress_service.validate_compatibility(checkpoint, command_hash):
                            self.logger.error(
                                "❌ Cannot resume: checkpoint incompatible with current parameters. "
                                "Use --reset-progress to start fresh."
                            )
                            return

                        self.logger.info(f"📍 Resuming from checkpoint:")
                        self.logger.info(f"   Last position: artist #{checkpoint.last_artist_index}/{checkpoint.total_artists}")
                        self.logger.info(f"   Already processed: {len(checkpoint.processed_artist_ids)} artists")
                        self.logger.info(f"   Last artist ID: {checkpoint.last_artist_id}")
                    else:
                        self.logger.info(f"  No checkpoint found for session '{self.args.session_name}', starting fresh")

            # Discover artists from all base artist IDs
            all_artists = []
            for idx, artist_id in enumerate(artist_ids):
                self.logger.info(f"\nDiscovering from base artist ID {idx + 1}/{len(artist_ids)}: {artist_id}")
                discovered = await self.discover_artists(artist_id, options)
                all_artists.extend(discovered)

            # Remove duplicates while preserving order
            seen = set()
            artists = []
            for artist in all_artists:
                if artist.id not in seen:
                    seen.add(artist.id)
                    artists.append(artist)

            # Create or update checkpoint with total artist count
            if self.args.session_name and not checkpoint:
                checkpoint = await self.progress_service.create_checkpoint(
                    session_name=self.args.session_name,
                    total_artists=len(artists),
                    command_hash=command_hash
                )

            # Filter out already-processed artists if resuming
            original_count = len(artists)
            if checkpoint:
                artists = self.progress_service.get_remaining_artists(artists)
                if len(artists) < original_count:
                    self.logger.info(
                        f"✓ Skipped {original_count - len(artists)} already-processed artists "
                        f"({len(artists)} remaining)"
                    )
                    if artists:
                        self.logger.info(f"→ Resuming from artist: {artists[0].name} ({artists[0].id})")

            self.stats['artists_processed'] = original_count  # Total discovered
            self.logger.info(f"\nProcessing {len(artists)} unique artists (from {len(artist_ids)} base artist(s))...")

            # Download tracks from all artists
            all_downloaded_tracks = []

            # Create progress bar for artists if tqdm is available
            if tqdm:
                # Adjust progress bar initial value if resuming
                initial = checkpoint.last_artist_index if checkpoint else 0
                total = checkpoint.total_artists if checkpoint else len(artists)
                artist_iter = tqdm(artists, desc="Artists", unit="artist", initial=initial, total=total)
            else:
                artist_iter = artists

            artist_index_offset = checkpoint.last_artist_index if checkpoint else 0

            for idx, artist in enumerate(artist_iter):
                current_index = artist_index_offset + idx + 1

                # Log artist processing status BEFORE downloading
                if (options.in_top_n or options.in_top_percent) and options.years:
                    in_top_str = f"{options.in_top_n}" if options.in_top_n else f"{options.in_top_percent}%"
                    self.logger.info(
                        f"📍 Processing: {artist.name} (checking top {in_top_str} for {options.years[0]}-{options.years[1]})"
                    )

                tracks = await self.download_artist_tracks(artist, options, output_dir)

                # Log result for this artist
                if not tracks and (options.in_top_n or options.in_top_percent) and options.years:
                    self.logger.info(f"  ✗ Skipped {artist.name} - no matching tracks in specified range")

                all_downloaded_tracks.extend(tracks)

                # Save progress checkpoint after each artist
                if self.args.session_name:
                    await self.progress_service.save_checkpoint(
                        session_name=self.args.session_name,
                        artist_id=artist.id,
                        artist_index=current_index,
                        total_artists=checkpoint.total_artists if checkpoint else original_count,
                        command_hash=command_hash
                    )

                # Respect max concurrent downloads setting
                if self.args.parallel < 5:
                    await asyncio.sleep(0.5)  # Small delay between artists

            # Apply shuffle if requested
            if self.args.shuffle and all_downloaded_tracks:
                await self.shuffle_and_renumber_tracks(output_dir)

            # Create archive if requested
            if self.args.archive and all_downloaded_tracks:
                await self.create_archive(output_dir)

            # Mark progress checkpoint as complete
            if self.args.session_name:
                await self.progress_service.mark_complete(self.args.session_name)
                self.logger.info(f"✅ Session completed: {self.args.session_name}")

            # Print final statistics
            self.stats['end_time'] = datetime.now()
            self._print_statistics()

            # Log completion and cleanup
            if hasattr(self, 'command_logger') and self.settings.logging.log_to_file:
                log_path = self.command_logger.get_log_path()
                self.logger.info(f"✅ Execution complete. Log saved to: {log_path}")

                # Cleanup old logs
                self.command_logger.cleanup_old_logs(
                    max_files=self.settings.logging.max_log_files,
                    max_age_days=self.settings.logging.log_rotation_days
                )

        except KeyboardInterrupt:
            self.logger.warning("\n\n⚠️  Process interrupted by user")
            self._print_statistics()

            # Save progress on interruption
            if self.args.session_name and self.progress_service:
                summary = self.progress_service.get_progress_summary()
                if summary:
                    self.logger.info(f"\n💾 Progress saved:\n{summary}")
                self.logger.info(f"\n📍 Resume with: --session-name {self.args.session_name} --resume")

            # Log interruption
            if hasattr(self, 'command_logger') and self.settings.logging.log_to_file:
                log_path = self.command_logger.get_log_path()
                self.logger.warning(f"⚠️  Interrupted. Partial log saved to: {log_path}")

        except Exception as e:
            self.logger.error(f"\n\n❌ Error: {e}", exc_info=self.args.verbose)

            # Save progress on error
            if self.args.session_name and self.progress_service:
                summary = self.progress_service.get_progress_summary()
                if summary:
                    self.logger.info(f"\n💾 Progress saved:\n{summary}")
                self.logger.info(f"\n📍 Resume with: --session-name {self.args.session_name} --resume")

            # Log error
            if hasattr(self, 'command_logger') and self.settings.logging.log_to_file:
                log_path = self.command_logger.get_log_path()
                self.logger.error(f"❌ Execution failed. Error log saved to: {log_path}")

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

        # Archive statistics if archive was created
        if 'archive_path' in self.stats:
            print(f"\n📦 Archive created:   {self.stats['archive_path']}")
            print(f"Archive size:         {self.stats['archive_size_mb']:.2f} MB")

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

    # Required arguments (mutually exclusive group)
    artist_input = parser.add_mutually_exclusive_group(required=True)
    artist_input.add_argument(
        '-a', '--artist-id',
        type=str,
        metavar='ID',
        help='Base artist ID(s) from Yandex Music (comma-separated for multiple: "123,456,789")'
    )
    artist_input.add_argument(
        '--artists-file',
        type=str,
        metavar='FILE',
        help='Path to file containing comma-separated artist IDs (useful for 300+ artists)'
    )

    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        default=None,
        metavar='DIR',
        help='Output directory for downloaded tracks (default: from DOWNLOADS_DIR in .env)'
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
        '--in-top',
        type=str,
        metavar='N',
        dest='in_top',
        help='Only download tracks in artist\'s top N most popular songs. '
             'Accepts numeric (e.g., "10") or percentage (e.g., "10%%"). '
             'Requires --years filter.'
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

    parser.add_argument(
        '--archive', '--zip',
        action='store_true',
        dest='archive',
        help='Create a ZIP archive of all downloaded tracks after completion'
    )

    parser.add_argument(
        '--archive-name',
        type=str,
        metavar='NAME',
        dest='archive_name',
        help='Custom archive filename (without .zip extension). Default: auto-generated from output directory and timestamp'
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

    # Progress management
    parser.add_argument(
        '--session-name',
        type=str,
        metavar='NAME',
        dest='session_name',
        help='Unique session name for progress tracking (enables resume on failure/interruption)'
    )

    parser.add_argument(
        '--resume', '--continue',
        action='store_true',
        dest='resume',
        help='Resume from last checkpoint if session exists (requires --session-name)'
    )

    parser.add_argument(
        '--reset-progress',
        action='store_true',
        dest='reset_progress',
        help='Clear saved progress for this session and start fresh (requires --session-name)'
    )

    # Utility options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging for debugging'
    )

    args = parser.parse_args()

    # Handle --artists-file: read and set artist_id from file
    if args.artists_file:
        try:
            file_path = Path(args.artists_file)
            if not file_path.exists():
                parser.error(f"Artists file not found: {args.artists_file}")

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            if not content:
                parser.error(f"Artists file is empty: {args.artists_file}")

            # Set artist_id from file content (overwrites None from args)
            args.artist_id = content

        except IOError as e:
            parser.error(f"Failed to read artists file: {e}")

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

    # Validate progress-related arguments
    if (args.resume or args.reset_progress) and not args.session_name:
        parser.error("--resume and --reset-progress require --session-name")

    if args.resume and args.reset_progress:
        parser.error("--resume and --reset-progress cannot be used together")

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
