"""Configuration settings for the Telegram Music Bot."""

import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))


@dataclass
class YandexConfig:
    """Yandex Music API configuration."""
    token: str = field(default_factory=lambda: os.getenv("YANDEX_TOKEN", ""))


@dataclass
class BotLimits:
    """Bot operational limits."""
    max_concurrent_downloads: int = field(default_factory=lambda: int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "5")))
    max_downloads_per_user: int = field(default_factory=lambda: int(os.getenv("MAX_DOWNLOADS_PER_USER", "3")))
    max_artists_per_discovery: int = field(default_factory=lambda: int(os.getenv("MAX_ARTISTS_PER_DISCOVERY", "50")))
    max_recursion_depth: int = field(default_factory=lambda: int(os.getenv("MAX_RECURSION_DEPTH", "5")))
    commands_per_minute: int = field(default_factory=lambda: int(os.getenv("COMMANDS_PER_MINUTE", "10")))
    downloads_per_hour: int = field(default_factory=lambda: int(os.getenv("DOWNLOADS_PER_HOUR", "50")))


@dataclass
class FileConfig:
    """File management configuration."""
    temp_dir: Path = field(default_factory=lambda: Path(os.getenv("TEMP_DIR", "/tmp/music_bot")))
    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", "./storage")))
    songs_cache_dir: Path = field(default_factory=lambda: Path(os.getenv("SONGS_CACHE_DIR", "./storage/downloads/tracks")))
    archives_dir: Path = field(default_factory=lambda: Path(os.getenv("ARCHIVES_DIR", "./storage/downloads/archives")))
    songs_cache_ttl: int = field(default_factory=lambda: int(os.getenv("SONGS_CACHE_TTL", "0")))
    delete_archives_after_upload: bool = field(default_factory=lambda: os.getenv("DELETE_ARCHIVES_AFTER_UPLOAD", "false").lower() == "true")
    max_file_size_mb: int = field(default_factory=lambda: int(os.getenv("MAX_FILE_SIZE_MB", "100")))
    auto_cleanup_hours: int = field(default_factory=lambda: int(os.getenv("AUTO_CLEANUP_HOURS", "24")))
    download_chunk_size: int = field(default_factory=lambda: int(os.getenv("DOWNLOAD_CHUNK_SIZE", "8192")))


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./storage/bot.db"))


@dataclass
class CacheConfig:
    """Cache configuration."""
    redis_url: Optional[str] = field(default_factory=lambda: os.getenv("REDIS_URL") or None)
    ttl_hours: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL_HOURS", "24")))
    enabled: bool = field(default_factory=lambda: os.getenv("ENABLE_CACHE", "true").lower() == "true")


@dataclass
class FeatureFlags:
    """Feature toggles."""
    enable_cache: bool = field(default_factory=lambda: os.getenv("ENABLE_CACHE", "true").lower() == "true")
    enable_deduplication: bool = field(default_factory=lambda: os.getenv("ENABLE_DEDUPLICATION", "true").lower() == "true")
    enable_analytics: bool = field(default_factory=lambda: os.getenv("ENABLE_ANALYTICS", "false").lower() == "true")
    enable_user_preferences: bool = field(default_factory=lambda: os.getenv("ENABLE_USER_PREFERENCES", "true").lower() == "true")
    rate_limit_strict: bool = field(default_factory=lambda: os.getenv("RATE_LIMIT_STRICT", "false").lower() == "true")


@dataclass
class SecurityConfig:
    """Security and access control."""
    allowed_users: List[int] = field(default_factory=lambda: [
        int(uid.strip()) for uid in os.getenv("ALLOWED_USERS", "").split(",") 
        if uid.strip().isdigit()
    ])
    admin_users: List[int] = field(default_factory=lambda: [
        int(uid.strip()) for uid in os.getenv("ADMIN_USERS", "").split(",") 
        if uid.strip().isdigit()
    ])


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    format: str = field(default_factory=lambda: os.getenv("LOG_FORMAT", "json"))
    sentry_dsn: Optional[str] = field(default_factory=lambda: os.getenv("SENTRY_DSN") or None)


@dataclass
class PerformanceConfig:
    """Performance settings."""
    worker_threads: int = field(default_factory=lambda: int(os.getenv("WORKER_THREADS", "4")))
    progress_update_interval: int = field(default_factory=lambda: int(os.getenv("PROGRESS_UPDATE_INTERVAL", "2")))


@dataclass
class Settings:
    """Complete bot settings."""
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    yandex: YandexConfig = field(default_factory=YandexConfig)
    limits: BotLimits = field(default_factory=BotLimits)
    files: FileConfig = field(default_factory=FileConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    def __post_init__(self):
        """Validate and prepare settings."""
        # Ensure directories exist
        self.files.temp_dir.mkdir(parents=True, exist_ok=True)
        self.files.storage_dir.mkdir(parents=True, exist_ok=True)
        (self.files.storage_dir / "downloads").mkdir(parents=True, exist_ok=True)
        
        # Validate required settings
        if not self.telegram.bot_token:
            raise ValueError("BOT_TOKEN is required")
        if not self.yandex.token:
            raise ValueError("YANDEX_TOKEN is required")


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings