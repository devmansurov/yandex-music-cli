"""Abstract interfaces for the bot components (SOLID - Interface Segregation Principle)."""

from abc import ABC, abstractmethod
from typing import List, Optional, AsyncIterator, Dict, Any
from pathlib import Path

from .models import (
    Track, Artist, Album, DownloadOptions, DownloadTask, 
    ProgressUpdate, DiscoveryResult, UserSettings, CacheEntry,
    FileInfo, BotStats
)


class MusicService(ABC):
    """Abstract interface for music streaming services."""
    
    @abstractmethod
    async def search_artist(self, query: str) -> List[Artist]:
        """Search for artists by name."""
        pass
    
    @abstractmethod
    async def get_artist(self, artist_id: str) -> Optional[Artist]:
        """Get artist information by ID."""
        pass
    
    @abstractmethod
    async def get_artist_tracks(self, artist_id: str, options: DownloadOptions) -> List[Track]:
        """Get tracks for an artist with filtering."""
        pass
    
    @abstractmethod
    async def get_similar_artists(self, artist_id: str, limit: int = 50) -> List[Artist]:
        """Get similar artists for a given artist."""
        pass
    
    @abstractmethod
    async def get_track_download_info(self, track: Track) -> Optional[str]:
        """Get download URL for a track."""
        pass
    
    @abstractmethod
    async def get_chart_tracks(self, chart_type: str, options: DownloadOptions) -> List[Track]:
        """Get tracks from a chart."""
        pass


class DownloadService(ABC):
    """Abstract interface for download operations."""
    
    @abstractmethod
    async def download_track(self, track: Track, output_path: Path) -> bool:
        """Download a single track."""
        pass
    
    @abstractmethod
    async def download_tracks(
        self, 
        tracks: List[Track], 
        progress_callback: Optional[callable] = None
    ) -> AsyncIterator[Track]:
        """Download multiple tracks with progress updates."""
        pass
    
    @abstractmethod
    async def get_download_progress(self, task_id: str) -> Optional[ProgressUpdate]:
        """Get current download progress."""
        pass
    
    @abstractmethod
    async def cancel_download(self, task_id: str) -> bool:
        """Cancel an active download."""
        pass


class DiscoveryService(ABC):
    """Abstract interface for artist discovery."""
    
    @abstractmethod
    async def discover_similar_artists(
        self, 
        artist_id: str, 
        options: DownloadOptions
    ) -> DiscoveryResult:
        """Discover similar artists."""
        pass
    
    @abstractmethod
    async def discover_recursive(
        self, 
        artist_id: str, 
        options: DownloadOptions,
        progress_callback: Optional[callable] = None
    ) -> DiscoveryResult:
        """Discover artists recursively."""
        pass


class CacheService(ABC):
    """Abstract interface for caching."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Set value in cache with TTL."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass


class ProgressTracker(ABC):
    """Abstract interface for progress tracking."""
    
    @abstractmethod
    async def start_tracking(self, task: DownloadTask) -> None:
        """Start tracking progress for a task."""
        pass
    
    @abstractmethod
    async def update_progress(self, update: ProgressUpdate) -> None:
        """Update progress for a task."""
        pass
    
    @abstractmethod
    async def complete_task(self, task_id: str, success: bool, error: Optional[str] = None) -> None:
        """Mark task as completed."""
        pass
    
    @abstractmethod
    async def cancel_task(self, task_id: str) -> None:
        """Cancel task tracking."""
        pass


class FileManager(ABC):
    """Abstract interface for file management."""
    
    @abstractmethod
    async def save_file(self, data: bytes, filename: str, temp: bool = False) -> Path:
        """Save file to storage."""
        pass
    
    @abstractmethod
    async def get_file_info(self, path: Path) -> Optional[FileInfo]:
        """Get file information."""
        pass
    
    @abstractmethod
    async def delete_file(self, path: Path) -> bool:
        """Delete a file."""
        pass
    
    @abstractmethod
    async def cleanup_temp_files(self, older_than_hours: int = 24) -> int:
        """Clean up temporary files."""
        pass
    
    @abstractmethod
    async def get_disk_usage(self) -> Dict[str, float]:
        """Get disk usage statistics."""
        pass
    
    @abstractmethod
    async def calculate_checksum(self, path: Path) -> str:
        """Calculate file checksum."""
        pass
    
    @abstractmethod
    async def find_duplicates(self, directory: Path) -> Dict[str, List[Path]]:
        """Find duplicate files by checksum."""
        pass


class UserRepository(ABC):
    """Abstract interface for user data storage."""
    
    @abstractmethod
    async def get_user_settings(self, user_id: int) -> Optional[UserSettings]:
        """Get user settings."""
        pass
    
    @abstractmethod
    async def save_user_settings(self, settings: UserSettings) -> None:
        """Save user settings."""
        pass
    
    @abstractmethod
    async def get_user_download_history(self, user_id: int, limit: int = 100) -> List[Track]:
        """Get user's download history."""
        pass
    
    @abstractmethod
    async def add_download_to_history(self, user_id: int, track: Track) -> None:
        """Add download to user's history."""
        pass
    
    @abstractmethod
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics."""
        pass


class TaskRepository(ABC):
    """Abstract interface for task storage."""
    
    @abstractmethod
    async def save_task(self, task: DownloadTask) -> None:
        """Save download task."""
        pass
    
    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """Get download task by ID."""
        pass
    
    @abstractmethod
    async def get_user_tasks(self, user_id: int, active_only: bool = False) -> List[DownloadTask]:
        """Get tasks for a user."""
        pass
    
    @abstractmethod
    async def update_task_status(self, task_id: str, status: str, error: Optional[str] = None) -> None:
        """Update task status."""
        pass
    
    @abstractmethod
    async def cleanup_old_tasks(self, older_than_hours: int = 168) -> int:  # 1 week
        """Clean up old completed tasks."""
        pass


class NotificationService(ABC):
    """Abstract interface for notifications."""
    
    @abstractmethod
    async def send_progress_update(self, chat_id: int, message_id: int, update: ProgressUpdate) -> None:
        """Send progress update to user."""
        pass
    
    @abstractmethod
    async def send_download_complete(self, chat_id: int, track: Track, file_path: Path) -> None:
        """Send completed download to user."""
        pass
    
    @abstractmethod
    async def send_error_notification(self, chat_id: int, error: str) -> None:
        """Send error notification to user."""
        pass
    
    @abstractmethod
    async def send_discovery_result(self, chat_id: int, result: DiscoveryResult) -> None:
        """Send discovery results to user."""
        pass


class RateLimiter(ABC):
    """Abstract interface for rate limiting."""
    
    @abstractmethod
    async def is_allowed(self, user_id: int, action: str) -> bool:
        """Check if action is allowed for user."""
        pass
    
    @abstractmethod
    async def record_action(self, user_id: int, action: str) -> None:
        """Record user action for rate limiting."""
        pass
    
    @abstractmethod
    async def get_remaining_quota(self, user_id: int, action: str) -> int:
        """Get remaining quota for user action."""
        pass
    
    @abstractmethod
    async def reset_quota(self, user_id: int, action: str) -> None:
        """Reset quota for user action."""
        pass


class StatsCollector(ABC):
    """Abstract interface for statistics collection."""
    
    @abstractmethod
    async def record_command(self, user_id: int, command: str) -> None:
        """Record command usage."""
        pass
    
    @abstractmethod
    async def record_download(self, user_id: int, track: Track, success: bool) -> None:
        """Record download attempt."""
        pass
    
    @abstractmethod
    async def get_bot_stats(self) -> BotStats:
        """Get overall bot statistics."""
        pass
    
    @abstractmethod
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user-specific statistics."""
        pass


class AuthService(ABC):
    """Abstract interface for authentication and authorization."""
    
    @abstractmethod
    async def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        pass
    
    @abstractmethod
    async def is_admin(self, user_id: int) -> bool:
        """Check if user has admin privileges."""
        pass
    
    @abstractmethod
    async def add_allowed_user(self, user_id: int) -> None:
        """Add user to allowed list."""
        pass
    
    @abstractmethod
    async def remove_allowed_user(self, user_id: int) -> None:
        """Remove user from allowed list."""
        pass