"""Progress checkpoint service for resumable operations."""

import asyncio
import json
import logging
import hashlib
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from ymusic_cli.core.models import ProgressCheckpoint, Artist
from ymusic_cli.core.exceptions import ServiceError
from ymusic_cli.core.interfaces import CacheService
from ymusic_cli.config.settings import get_settings


class ProgressService:
    """Service for managing progress checkpoints for resumable operations."""

    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache = cache_service
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)

        # Progress storage directory
        self.progress_dir = Path("storage/progress")
        self.progress_dir.mkdir(parents=True, exist_ok=True)

        self._current_checkpoint: Optional[ProgressCheckpoint] = None

    def _get_progress_file_path(self, session_name: str) -> Path:
        """Get file path for progress checkpoint."""
        safe_name = session_name.replace("/", "_").replace("\\", "_")
        return self.progress_dir / f"{safe_name}.json"

    def _get_redis_key(self, session_name: str) -> str:
        """Get Redis key for progress checkpoint."""
        return f"ymusic:progress:{session_name}"

    def generate_command_hash(
        self,
        artist_ids: List[str],
        similar_limit: int,
        max_depth: int,
        songs_per_artist: int
    ) -> str:
        """Generate hash for command compatibility check.

        Args:
            artist_ids: List of base artist IDs
            similar_limit: Number of similar artists per artist
            max_depth: Recursive max depth
            songs_per_artist: Number of songs per artist

        Returns:
            Hash string for compatibility checking
        """
        content = f"{','.join(sorted(artist_ids))}_{similar_limit}_{max_depth}_{songs_per_artist}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    async def load_checkpoint(self, session_name: str) -> Optional[ProgressCheckpoint]:
        """Load progress checkpoint from storage.

        Args:
            session_name: Unique session name

        Returns:
            ProgressCheckpoint if found, None otherwise
        """
        try:
            # Try Redis first if available
            if self.cache:
                redis_key = self._get_redis_key(session_name)
                cached_data = await self.cache.get(redis_key)
                if cached_data:
                    self.logger.info(f"Loaded progress from Redis: {session_name}")
                    checkpoint = ProgressCheckpoint.from_dict(cached_data)
                    self._current_checkpoint = checkpoint
                    return checkpoint

            # Fallback to file storage
            file_path = self._get_progress_file_path(session_name)
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.logger.info(f"Loaded progress from file: {file_path}")
                checkpoint = ProgressCheckpoint.from_dict(data)
                self._current_checkpoint = checkpoint
                return checkpoint

            self.logger.info(f"No existing progress found for session: {session_name}")
            return None

        except Exception as e:
            self.logger.error(f"Failed to load checkpoint for {session_name}: {e}")
            return None

    async def save_checkpoint(
        self,
        session_name: str,
        artist_id: str,
        artist_index: int,
        total_artists: Optional[int] = None,
        command_hash: Optional[str] = None
    ) -> None:
        """Save progress checkpoint.

        Args:
            session_name: Unique session name
            artist_id: ID of last processed artist
            artist_index: Index of last processed artist
            total_artists: Total number of artists (for new checkpoints)
            command_hash: Command hash for compatibility (for new checkpoints)
        """
        try:
            # Update existing or create new checkpoint
            if self._current_checkpoint and self._current_checkpoint.session_name == session_name:
                checkpoint = self._current_checkpoint
                checkpoint.last_artist_id = artist_id
                checkpoint.last_artist_index = artist_index
                checkpoint.processed_artist_ids.add(artist_id)
                checkpoint.last_updated_at = datetime.now()
            else:
                # Create new checkpoint
                checkpoint = ProgressCheckpoint(
                    session_name=session_name,
                    total_artists=total_artists or 0,
                    processed_artist_ids={artist_id},
                    last_artist_index=artist_index,
                    last_artist_id=artist_id,
                    command_hash=command_hash or "",
                )
                self._current_checkpoint = checkpoint

            # Save to Redis if available
            if self.cache:
                redis_key = self._get_redis_key(session_name)
                # Save with 30 day TTL
                await self.cache.set(redis_key, checkpoint.to_dict(), ttl_seconds=30 * 24 * 3600)
                self.logger.debug(f"Saved progress to Redis: {session_name} (artist #{artist_index})")

            # Also save to file (backup)
            file_path = self._get_progress_file_path(session_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint.to_dict(), f, indent=2)

            self.logger.debug(f"Saved progress to file: {file_path} (artist #{artist_index})")

        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")
            # Don't raise - progress save failure shouldn't stop the main process

    async def create_checkpoint(
        self,
        session_name: str,
        total_artists: int,
        command_hash: str
    ) -> ProgressCheckpoint:
        """Create a new progress checkpoint.

        Args:
            session_name: Unique session name
            total_artists: Total number of artists to process
            command_hash: Command hash for compatibility check

        Returns:
            New ProgressCheckpoint instance
        """
        checkpoint = ProgressCheckpoint(
            session_name=session_name,
            total_artists=total_artists,
            command_hash=command_hash
        )
        self._current_checkpoint = checkpoint

        # Save initial checkpoint
        try:
            if self.cache:
                redis_key = self._get_redis_key(session_name)
                await self.cache.set(redis_key, checkpoint.to_dict(), ttl_seconds=30 * 24 * 3600)

            file_path = self._get_progress_file_path(session_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint.to_dict(), f, indent=2)

            self.logger.info(f"Created new progress checkpoint: {session_name}")
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")

        return checkpoint

    def is_artist_processed(self, artist_id: str) -> bool:
        """Check if artist has been processed (O(1) set lookup).

        Args:
            artist_id: Artist ID to check

        Returns:
            True if artist was already processed
        """
        if not self._current_checkpoint:
            return False
        return artist_id in self._current_checkpoint.processed_artist_ids

    def get_remaining_artists(self, all_artists: List[Artist]) -> List[Artist]:
        """Filter out already-processed artists.

        Args:
            all_artists: Full list of artists to process

        Returns:
            List of unprocessed artists
        """
        if not self._current_checkpoint:
            return all_artists

        remaining = [
            artist for artist in all_artists
            if artist.id not in self._current_checkpoint.processed_artist_ids
        ]

        self.logger.info(
            f"Filtered {len(all_artists) - len(remaining)} already-processed artists "
            f"({len(remaining)} remaining)"
        )

        return remaining

    async def mark_complete(self, session_name: str) -> None:
        """Mark session as complete.

        Args:
            session_name: Session name to mark complete
        """
        if self._current_checkpoint:
            self._current_checkpoint.is_complete = True

        # Update both storages
        if self.cache:
            redis_key = self._get_redis_key(session_name)
            if self._current_checkpoint:
                # Save with shorter TTL (7 days) for completed sessions
                await self.cache.set(
                    redis_key,
                    self._current_checkpoint.to_dict(),
                    ttl_seconds=7 * 24 * 3600
                )

        file_path = self._get_progress_file_path(session_name)
        if file_path.exists() and self._current_checkpoint:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self._current_checkpoint.to_dict(), f, indent=2)

        self.logger.info(f"Marked session as complete: {session_name}")

    async def reset_session(self, session_name: str) -> bool:
        """Delete progress checkpoint for session.

        Args:
            session_name: Session name to reset

        Returns:
            True if checkpoint was deleted
        """
        try:
            deleted = False

            # Delete from Redis
            if self.cache:
                redis_key = self._get_redis_key(session_name)
                if await self.cache.delete(redis_key):
                    self.logger.info(f"Deleted progress from Redis: {session_name}")
                    deleted = True

            # Delete file
            file_path = self._get_progress_file_path(session_name)
            if file_path.exists():
                file_path.unlink()
                self.logger.info(f"Deleted progress file: {file_path}")
                deleted = True

            # Clear current checkpoint if it matches
            if self._current_checkpoint and self._current_checkpoint.session_name == session_name:
                self._current_checkpoint = None

            return deleted

        except Exception as e:
            self.logger.error(f"Failed to reset session {session_name}: {e}")
            return False

    def validate_compatibility(
        self,
        checkpoint: ProgressCheckpoint,
        command_hash: str
    ) -> bool:
        """Validate that checkpoint is compatible with current command.

        Args:
            checkpoint: Loaded checkpoint
            command_hash: Current command hash

        Returns:
            True if compatible
        """
        if checkpoint.command_hash != command_hash:
            self.logger.warning(
                f"Checkpoint command hash mismatch! "
                f"Checkpoint: {checkpoint.command_hash}, Current: {command_hash}"
            )
            self.logger.warning(
                "This likely means you're trying to resume with different parameters. "
                "Use --reset-progress to start fresh."
            )
            return False
        return True

    def get_progress_summary(self) -> Optional[str]:
        """Get human-readable progress summary.

        Returns:
            Progress summary string or None
        """
        if not self._current_checkpoint:
            return None

        checkpoint = self._current_checkpoint
        progress_pct = (checkpoint.last_artist_index / checkpoint.total_artists * 100) if checkpoint.total_artists > 0 else 0

        elapsed = (checkpoint.last_updated_at - checkpoint.started_at).total_seconds()
        elapsed_hours = elapsed / 3600

        return (
            f"Session: {checkpoint.session_name}\n"
            f"Progress: {checkpoint.last_artist_index}/{checkpoint.total_artists} ({progress_pct:.1f}%)\n"
            f"Last artist: {checkpoint.last_artist_id}\n"
            f"Elapsed: {elapsed_hours:.1f} hours\n"
            f"Tracks: {checkpoint.tracks_downloaded} downloaded, {checkpoint.tracks_failed} failed"
        )
