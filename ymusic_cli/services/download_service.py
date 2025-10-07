"""Download orchestration service."""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional, AsyncIterator, Dict, Any
import aiohttp
import aiofiles
from datetime import datetime
import time

from ymusic_cli.core.interfaces import DownloadService, MusicService, FileManager, ProgressTracker, CacheService
from ymusic_cli.core.models import Track, DownloadTask, ProgressUpdate, ProgressType, DownloadStatus
from ymusic_cli.core.exceptions import DownloadError, NetworkError, FileSystemError
from ymusic_cli.config.settings import get_settings


class DownloadOrchestrator(DownloadService):
    """Orchestrates download operations with progress tracking."""
    
    def __init__(
        self,
        music_service: MusicService,
        file_manager: FileManager,
        progress_tracker: Optional[ProgressTracker] = None,
        cache_service: Optional[CacheService] = None
    ):
        self.music_service = music_service
        self.file_manager = file_manager
        self.progress_tracker = progress_tracker
        self.cache_service = cache_service
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        
        # Active downloads tracking
        self.active_downloads: Dict[str, DownloadTask] = {}
        self.download_semaphore = asyncio.Semaphore(self.settings.limits.max_concurrent_downloads)
        
        # Session for downloads
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> None:
        """Initialize the download service."""
        connector = aiohttp.TCPConnector(
            limit=20,
            limit_per_host=5
        )
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        self.logger.info("Download service initialized")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.close()
        self.logger.info("Download service cleaned up")
    
    async def download_track(
        self,
        track: Track,
        output_path: Path,
        artist: Optional[Any] = None,
        year: Optional[int] = None
    ) -> bool:
        """Download a single track with caching support.

        Args:
            track: Track to download
            output_path: Path where the track should be saved
            artist: Artist object for enhanced filename generation (optional)
            year: Year for enhanced filename generation (optional)
        """
        if not self.session:
            raise DownloadError("Download service not initialized")

        try:
            # Generate cache key for this track
            cache_key = f"track_{track.id}"

            # Check if track failed recently (negative cache)
            if self.cache_service:
                failed_key = f"failed_track_{track.id}"
                failed = await self.cache_service.get(failed_key)
                if failed:
                    self.logger.debug(f"Skipping recently failed track {track.id}: {failed}")
                    return False

            # Check if track exists in cache
            if self.cache_service:
                cached_path = await self.cache_service.get(cache_key)
                if cached_path:
                    # Check if cached file still exists
                    cached_file = Path(cached_path)
                    if cached_file.exists():
                        # If output path is different from cached path, create hard link
                        if cached_file != output_path:
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            # Use hard link to save disk space
                            try:
                                if output_path.exists():
                                    output_path.unlink()
                                os.link(str(cached_file), str(output_path))
                                self.logger.info(f"Using cached track {track.id} from {cached_file}")
                            except OSError as e:
                                # Fallback to copy if hard link fails
                                self.logger.warning(f"Hard link failed, falling back to copy: {e}")
                                import shutil
                                shutil.copy2(str(cached_file), str(output_path))
                                self.logger.info(f"Using cached track {track.id} from {cached_file}")
                        else:
                            self.logger.info(f"Track {track.id} already cached at {cached_file}")
                        track.file_path = output_path
                        track.file_size = output_path.stat().st_size
                        return True
                    else:
                        # Cached file missing, remove from cache
                        await self.cache_service.delete(cache_key)

            # Use songs cache directory if available, otherwise use provided path
            if hasattr(self.settings.files, 'songs_cache_dir'):
                cache_dir = self.settings.files.songs_cache_dir
                cache_dir.mkdir(parents=True, exist_ok=True)
                # Create enhanced filename for cache
                file_ext = output_path.suffix
                cache_filename = self._generate_enhanced_filename(track, artist, year, file_ext)
                cache_path = cache_dir / cache_filename
            else:
                cache_path = output_path

            # Get download URL
            download_url = await self.music_service.get_track_download_info(track)
            if not download_url:
                raise DownloadError(f"No download URL for track {track.id}", track.id)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download file
            async with self.session.get(download_url) as response:
                if response.status != 200:
                    raise DownloadError(
                        f"HTTP {response.status} when downloading track {track.id}",
                        track.id
                    )
                
                file_size = int(response.headers.get('content-length', 0))
                
                # Check file size limit
                if file_size > self.settings.files.max_file_size_mb * 1024 * 1024:
                    raise DownloadError(
                        f"File too large: {file_size / 1024 / 1024:.1f} MB",
                        track.id
                    )
                
                # Download with chunked reading
                # Ensure cache directory exists
                cache_path.parent.mkdir(parents=True, exist_ok=True)

                async with aiofiles.open(cache_path, 'wb') as file:
                    downloaded = 0
                    chunk_size = self.settings.files.download_chunk_size
                    
                    async for chunk in response.content.iter_chunked(chunk_size):
                        await file.write(chunk)
                        downloaded += len(chunk)
                        
                        # Optional progress callback could be added here
            
            # If we downloaded to cache, create hard link to output path if different
            if cache_path != output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                # Use hard link instead of copy to save disk space
                # Hard links point to the same inode (same physical file)
                try:
                    # Remove existing file if it exists (for updates)
                    if output_path.exists():
                        output_path.unlink()
                    os.link(str(cache_path), str(output_path))
                    self.logger.debug(f"Created hard link from {cache_path} to {output_path}")
                except OSError as e:
                    # Fallback to copy if hard link fails (e.g., cross-filesystem)
                    self.logger.warning(f"Hard link failed, falling back to copy: {e}")
                    import shutil
                    shutil.copy2(str(cache_path), str(output_path))

            # Update track with file info
            track.file_path = output_path
            track.file_size = output_path.stat().st_size

            # Store in cache
            if self.cache_service and hasattr(self.settings.files, 'songs_cache_dir'):
                ttl = getattr(self.settings.files, 'songs_cache_ttl', 0)
                # If TTL is 0, use a very large value (10 years)
                if ttl == 0:
                    ttl = 10 * 365 * 24 * 3600  # 10 years in seconds
                await self.cache_service.set(cache_key, str(cache_path), ttl)
                self.logger.info(f"Cached track {track.id} at {cache_path} with TTL {ttl}s")

            self.logger.info(f"Successfully downloaded track {track.id} to {output_path}")
            return True
            
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error downloading track {track.id}: {e}")
            # Cache network failures for 5 minutes (short TTL for quick retry)
            if self.cache_service:
                await self.cache_service.set(f"failed_track_{track.id}", str(e), ttl_seconds=300)
            raise NetworkError(f"Network error: {e}")
        except OSError as e:
            self.logger.error(f"File system error downloading track {track.id}: {e}")
            # Don't cache filesystem errors (might be resolved immediately)
            raise FileSystemError(f"File system error: {e}", str(output_path))
        except Exception as e:
            self.logger.error(f"Unexpected error downloading track {track.id}: {e}")
            # Cache generic failures for 5 minutes
            if self.cache_service:
                await self.cache_service.set(f"failed_track_{track.id}", str(e), ttl_seconds=300)
            raise DownloadError(f"Download failed: {e}", track.id)
    
    async def download_tracks(
        self,
        tracks: List[Track],
        progress_callback: Optional[callable] = None
    ) -> AsyncIterator[Track]:
        """Download multiple tracks with progress updates."""
        if not tracks:
            return
        
        self.logger.info(f"Starting download of {len(tracks)} tracks")
        
        # Create semaphore for concurrent downloads
        semaphore = asyncio.Semaphore(self.settings.limits.max_concurrent_downloads)
        completed_count = 0
        start_time = time.time()
        
        async def download_single_track(track: Track) -> Optional[Track]:
            """Download a single track with semaphore."""
            async with semaphore:
                try:
                    # Generate output path
                    temp_dir = self.settings.files.temp_dir
                    filename = self._generate_filename(track)
                    output_path = temp_dir / filename
                    
                    # Download the track
                    success = await self.download_track(track, output_path)
                    if success:
                        return track
                    return None
                    
                except Exception as e:
                    self.logger.error(f"Failed to download track {track.id}: {e}")
                    return None
        
        # Create download tasks
        download_tasks = [download_single_track(track) for track in tracks]
        
        # Process downloads as they complete
        for coro in asyncio.as_completed(download_tasks):
            try:
                result = await coro
                completed_count += 1
                
                # Send progress update
                if progress_callback:
                    progress = (completed_count / len(tracks)) * 100
                    elapsed = time.time() - start_time
                    eta = (elapsed / completed_count) * (len(tracks) - completed_count) if completed_count > 0 else 0
                    
                    update = ProgressUpdate(
                        task_id="",  # Will be set by caller
                        type=ProgressType.DOWNLOAD,
                        progress_percent=progress,
                        current_item=result.title if result else "Failed track",
                        items_completed=completed_count,
                        items_total=len(tracks),
                        eta_seconds=int(eta)
                    )
                    await progress_callback(update)
                
                # Yield completed track
                if result:
                    yield result
                    
            except Exception as e:
                self.logger.error(f"Error in download completion handling: {e}")
                completed_count += 1
        
        self.logger.info(f"Completed download of {completed_count}/{len(tracks)} tracks")
    
    async def get_download_progress(self, task_id: str) -> Optional[ProgressUpdate]:
        """Get current download progress."""
        task = self.active_downloads.get(task_id)
        if not task:
            return None
        
        return ProgressUpdate(
            task_id=task_id,
            type=ProgressType.DOWNLOAD,
            progress_percent=(task.completed_tracks / max(task.total_tracks, 1)) * 100,
            current_item=task.current_track.title if task.current_track else None,
            items_completed=task.completed_tracks,
            items_total=task.total_tracks
        )
    
    async def cancel_download(self, task_id: str) -> bool:
        """Cancel an active download."""
        task = self.active_downloads.get(task_id)
        if not task:
            return False
        
        try:
            task.status = DownloadStatus.CANCELLED
            # Note: In a full implementation, you'd need to cancel ongoing asyncio tasks
            del self.active_downloads[task_id]
            
            if self.progress_tracker:
                await self.progress_tracker.cancel_task(task_id)
            
            self.logger.info(f"Cancelled download task {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling download {task_id}: {e}")
            return False
    
    def _generate_enhanced_filename(
        self,
        track: Track,
        artist: Optional[Any],
        year: Optional[int],
        file_ext: str = ".mp3"
    ) -> str:
        """Generate enhanced filename with artist ID, track ID, and year metadata.

        Format: {ArtistName} - {TrackTitle} [{Year}] [AID{ArtistID}] [TID{TrackID}].mp3
        Example: Юлдуз Усманова - Sevaman seni [2024] [AID328849] [TID142345678].mp3
        """
        # Get artist name
        if artist and hasattr(artist, 'name'):
            artist_name = self._sanitize_filename(artist.name)
        elif track.artist_names:
            artist_name = self._sanitize_filename(", ".join(track.artist_names))
        else:
            artist_name = "Unknown Artist"

        # Get track title
        title = self._sanitize_filename(track.title)

        # Build filename components
        parts = [f"{artist_name} - {title}"]

        # Add year if available
        if year:
            parts.append(f"[{year}]")
        elif hasattr(track, 'year') and track.year:
            parts.append(f"[{track.year}]")

        # Add Artist ID if available
        if artist and hasattr(artist, 'id'):
            parts.append(f"[AID{artist.id}]")

        # Add Track ID (always available)
        parts.append(f"[TID{track.id}]")

        filename = " ".join(parts) + file_ext

        # Ensure filename isn't too long (filesystem limit ~255 chars)
        if len(filename) > 250:
            # Calculate metadata suffix length
            metadata_suffix = ""
            if year:
                metadata_suffix += f" [{year}]"
            elif hasattr(track, 'year') and track.year:
                metadata_suffix += f" [{track.year}]"
            if artist and hasattr(artist, 'id'):
                metadata_suffix += f" [AID{artist.id}]"
            metadata_suffix += f" [TID{track.id}]{file_ext}"

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

    def _generate_filename(self, track: Track) -> str:
        """Generate a safe filename for a track (legacy method for backward compatibility)."""
        # Sanitize title and artist names
        title = self._sanitize_filename(track.title)
        artists = ", ".join(track.artist_names) if track.artist_names else "Unknown Artist"
        artists = self._sanitize_filename(artists)

        # Create filename with quality indicator
        quality_suffix = f"_{track.quality.value}" if track.quality != track.quality.HIGH else ""
        filename = f"{artists} - {title}{quality_suffix}.mp3"

        # Ensure filename isn't too long
        if len(filename) > 200:
            filename = filename[:197] + "..."

        return filename
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename by removing invalid characters."""
        import re
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)  # Remove control characters
        return sanitized.strip()


class DownloadQueue:
    """Queue manager for download tasks."""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.queue: asyncio.Queue = asyncio.Queue()
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: List[str] = []
        self.failed_tasks: List[str] = []
        self.logger = logging.getLogger(__name__)
    
    async def add_task(self, download_task: DownloadTask) -> None:
        """Add a download task to the queue."""
        await self.queue.put(download_task)
        self.logger.info(f"Added task {download_task.id} to download queue")
    
    async def start_processing(self, download_service: DownloadService) -> None:
        """Start processing the download queue."""
        while True:
            try:
                # Wait for a task
                task = await self.queue.get()
                
                # Wait if we have too many concurrent downloads
                while len(self.active_tasks) >= self.max_concurrent:
                    await asyncio.sleep(1)
                
                # Start the download task
                async_task = asyncio.create_task(
                    self._process_download_task(task, download_service)
                )
                self.active_tasks[task.id] = async_task
                
            except Exception as e:
                self.logger.error(f"Error in download queue processing: {e}")
    
    async def _process_download_task(
        self,
        task: DownloadTask,
        download_service: DownloadService
    ) -> None:
        """Process a single download task."""
        try:
            task.status = DownloadStatus.DOWNLOADING
            task.started_at = datetime.now()
            
            # This would integrate with the full download logic
            # For now, it's a placeholder
            
            task.status = DownloadStatus.COMPLETED
            task.completed_at = datetime.now()
            self.completed_tasks.append(task.id)
            
        except Exception as e:
            task.status = DownloadStatus.FAILED
            task.error_message = str(e)
            self.failed_tasks.append(task.id)
            self.logger.error(f"Download task {task.id} failed: {e}")
        
        finally:
            # Remove from active tasks
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]