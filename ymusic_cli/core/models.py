"""Core domain models for the Telegram Music Bot."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from enum import Enum
from pathlib import Path


class DownloadStatus(Enum):
    """Download task status."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProgressType(Enum):
    """Progress update types."""
    DISCOVERY = "discovery"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    COMPLETE = "complete"
    ERROR = "error"


class Quality(Enum):
    """Audio quality levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Artist:
    """Artist information."""
    id: str
    name: str
    country: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    track_count: int = 0
    similarity_score: Optional[float] = None
    discovered_from: Optional[str] = None  # Parent artist ID for recursive discovery
    depth: int = 0  # Discovery depth level


@dataclass
class Album:
    """Album information."""
    id: str
    name: str
    year: Optional[int] = None
    artist_ids: List[str] = field(default_factory=list)
    track_count: int = 0
    genres: List[str] = field(default_factory=list)


@dataclass
class Track:
    """Track information."""
    id: str
    title: str
    artist_ids: List[str] = field(default_factory=list)
    album_id: Optional[str] = None
    duration_ms: int = 0
    file_size: Optional[int] = None
    file_path: Optional[Path] = None
    download_url: Optional[str] = None
    quality: Quality = Quality.HIGH
    explicit: bool = False
    year: Optional[int] = None
    genres: List[str] = field(default_factory=list)
    countries: List[str] = field(default_factory=list)
    
    # Metadata for UI
    artist_names: List[str] = field(default_factory=list)
    album_name: Optional[str] = None


@dataclass
class DownloadOptions:
    """Download configuration options."""
    # Selection criteria
    top_n: Optional[int] = None
    top_percent: Optional[float] = None
    
    # Filters
    years: Optional[tuple[int, int]] = None  # (start_year, end_year)
    countries: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    exclude_explicit: bool = False
    
    # Quality settings
    quality: Quality = Quality.HIGH
    
    # Similar artists options
    similar_limit: int = 5
    similar_country_filter: Optional[str] = None  # 'same' or country codes
    min_tracks_per_artist: int = 3
    
    # Recursive discovery options
    max_depth: int = 2
    max_total_artists: int = 50
    songs_per_artist: int = 3
    priority_countries: List[str] = field(default_factory=list)
    exclude_artists: Set[str] = field(default_factory=set)

    # Year-based discovery options
    enable_year_filtering_for_discovery: bool = False  # Skip artists without year content
    skip_artists_without_year_content: bool = True  # When year filter active
    max_similar_artist_attempts: int = 20  # Max attempts to find similar artist with year content

    # File options
    skip_existing: bool = True
    max_file_size_mb: int = 100


@dataclass
class UserSettings:
    """User preferences and settings."""
    user_id: int
    default_quality: Quality = Quality.HIGH
    default_top_n: int = 10
    auto_skip_explicit: bool = False
    preferred_countries: List[str] = field(default_factory=list)
    preferred_genres: List[str] = field(default_factory=list)
    max_concurrent_downloads: int = 3
    notifications_enabled: bool = True
    language: str = "en"
    
    # Advanced settings
    enable_deduplication: bool = True
    enable_progress_updates: bool = True
    progress_update_interval: int = 5  # seconds


@dataclass
class DownloadTask:
    """Download task information."""
    id: str
    user_id: int
    command: str
    status: DownloadStatus = DownloadStatus.PENDING
    options: DownloadOptions = field(default_factory=DownloadOptions)
    
    # Progress tracking
    total_tracks: int = 0
    completed_tracks: int = 0
    failed_tracks: int = 0
    current_track: Optional[Track] = None
    
    # Discovery info (for recursive operations)
    total_artists: int = 0
    discovered_artists: int = 0
    current_artist: Optional[Artist] = None
    current_depth: int = 0
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Telegram context
    chat_id: int = 0
    message_id: Optional[int] = None


@dataclass
class ProgressUpdate:
    """Progress update information."""
    task_id: str
    type: ProgressType
    progress_percent: float = 0.0
    
    # Context-specific data
    current_item: Optional[str] = None  # Current track/artist name
    items_completed: int = 0
    items_total: int = 0
    
    # Discovery-specific
    current_depth: Optional[int] = None
    max_depth: Optional[int] = None
    discovered_count: Optional[int] = None
    
    # Download-specific
    download_speed: Optional[str] = None  # e.g., "1.2 MB/s"
    eta_seconds: Optional[int] = None
    file_size: Optional[int] = None
    
    # Error information
    error_message: Optional[str] = None
    
    # Additional context
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoveryResult:
    """Result of artist discovery operation."""
    base_artist: Artist
    discovered_artists: List[Artist] = field(default_factory=list)
    discovery_tree: Dict[str, List[str]] = field(default_factory=dict)  # artist_id -> [similar_artist_ids]
    
    # Statistics
    total_discovered: int = 0
    max_depth_reached: int = 0
    countries_found: Set[str] = field(default_factory=set)
    discovery_time_seconds: float = 0.0
    
    # Metadata
    discovery_params: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 3600  # 1 hour default
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return (datetime.now() - self.created_at).total_seconds() > self.ttl_seconds


@dataclass
class FileInfo:
    """File information for downloads."""
    path: Path
    size: int
    format: str
    quality: Quality
    checksum: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def size_mb(self) -> float:
        """File size in MB."""
        return self.size / (1024 * 1024)


@dataclass
class QueueStats:
    """Queue statistics."""
    pending_tasks: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    average_processing_time: float = 0.0
    total_downloads: int = 0
    total_data_mb: float = 0.0


@dataclass
class BotStats:
    """Bot-wide statistics."""
    uptime_seconds: float = 0.0
    total_users: int = 0
    active_users_24h: int = 0
    total_commands: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0
    total_data_downloaded_mb: float = 0.0
    queue_stats: QueueStats = field(default_factory=QueueStats)
    
    # Performance metrics
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    disk_usage_mb: float = 0.0