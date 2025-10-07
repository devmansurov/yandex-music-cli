"""Enhanced logging with file output and rotation."""

import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class CommandLogger:
    """Logger that creates unique log file per command execution."""

    def __init__(
        self,
        log_dir: Path,
        command_params: Dict[str, Any],
        log_to_file: bool = True,
        log_to_console: bool = True,
        log_level: str = "INFO"
    ):
        """Initialize command logger with automatic filename generation.

        Args:
            log_dir: Directory to store log files
            command_params: Dictionary of command parameters for filename generation
            log_to_file: Whether to log to file
            log_to_console: Whether to log to console
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Generate log filename
        self.log_file = self._generate_log_filename(command_params)

        # Setup logging
        self.logger = self._setup_logging(log_to_file, log_to_console, log_level)

    def _generate_log_filename(self, params: Dict[str, Any]) -> Path:
        """Generate unique log filename based on command parameters.

        Format: ymusic_{timestamp}_{operation}_{params}.log
        Example: ymusic_20251007_143052_discovery_a328849_s50_d2_y2024-2025.log

        Args:
            params: Command parameters dictionary

        Returns:
            Path to log file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Build parameter string
        param_parts = []

        # Artist IDs
        if 'artist_ids' in params and params['artist_ids']:
            artist_ids = params['artist_ids']
            if isinstance(artist_ids, str):
                artist_ids = [a.strip() for a in artist_ids.split(',') if a.strip()]

            artist_count = len(artist_ids)
            if artist_count == 1:
                param_parts.append(f"a{artist_ids[0]}")
            else:
                param_parts.append(f"{artist_count}artists")

        # Similar artists count
        if 'similar' in params and params['similar']:
            param_parts.append(f"s{params['similar']}")

        # Discovery depth
        if 'depth' in params and params['depth']:
            param_parts.append(f"d{params['depth']}")

        # Year range
        if 'years' in params and params['years']:
            years = params['years']
            if isinstance(years, tuple) and len(years) == 2:
                start, end = years
                param_parts.append(f"y{start}-{end}")

        # Track count
        if 'tracks' in params and params['tracks']:
            param_parts.append(f"n{params['tracks']}")

        # In-top filter
        if 'in_top_n' in params and params['in_top_n']:
            param_parts.append(f"top{params['in_top_n']}")

        # Determine operation type
        is_discovery = (params.get('depth', 0) > 0 or params.get('similar', 0) > 0)
        is_archive = params.get('archive', False)

        if is_archive:
            operation = "archive"
        elif is_discovery:
            operation = "discovery"
        else:
            operation = "download"

        # Build filename
        param_str = "_".join(param_parts) if param_parts else "default"
        filename = f"ymusic_{timestamp}_{operation}_{param_str}.log"

        # Ensure filename isn't too long
        if len(filename) > 200:
            # Truncate param string
            filename = f"ymusic_{timestamp}_{operation}_{param_str[:100]}.log"

        return self.log_dir / filename

    def _setup_logging(
        self,
        log_to_file: bool,
        log_to_console: bool,
        log_level: str
    ) -> logging.Logger:
        """Setup logging with file and console handlers.

        Args:
            log_to_file: Enable file logging
            log_to_console: Enable console logging
            log_level: Logging level string

        Returns:
            Configured logger instance
        """
        # Get or create logger
        logger = logging.getLogger("ymusic_cli")
        logger.setLevel(logging.DEBUG)  # Capture all levels, handlers will filter

        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # File handler
        if log_to_file:
            try:
                file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)  # Log everything to file
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                print(f"Warning: Failed to create file handler: {e}", file=sys.stderr)

        # Console handler
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        # Prevent propagation to root logger
        logger.propagate = False

        return logger

    def get_logger(self) -> logging.Logger:
        """Get the configured logger instance.

        Returns:
            Logger instance
        """
        return self.logger

    def get_log_path(self) -> Path:
        """Get path to the log file.

        Returns:
            Path to log file
        """
        return self.log_file

    def cleanup_old_logs(self, max_files: int = 100, max_age_days: int = 30) -> int:
        """Clean up old log files based on count and age.

        Args:
            max_files: Maximum number of log files to keep
            max_age_days: Maximum age of log files in days

        Returns:
            Number of log files deleted
        """
        deleted_count = 0

        try:
            # Get all log files sorted by modification time (newest first)
            log_files = sorted(
                self.log_dir.glob("ymusic_*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # Remove oldest files if exceeding max count
            if len(log_files) > max_files:
                for old_file in log_files[max_files:]:
                    try:
                        old_file.unlink()
                        deleted_count += 1
                    except Exception:
                        pass

            # Remove files older than max age
            if max_age_days > 0:
                cutoff_time = datetime.now() - timedelta(days=max_age_days)
                for log_file in log_files:
                    try:
                        file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                        if file_time < cutoff_time:
                            log_file.unlink()
                            deleted_count += 1
                    except Exception:
                        pass

            if deleted_count > 0:
                self.logger.debug(f"Cleaned up {deleted_count} old log files")

        except Exception as e:
            self.logger.debug(f"Error during log cleanup: {e}")

        return deleted_count


def create_command_logger(
    command_params: Dict[str, Any],
    log_dir: Optional[Path] = None,
    log_to_file: bool = True,
    log_to_console: bool = True,
    log_level: str = "INFO"
) -> CommandLogger:
    """Factory function to create a command logger.

    Args:
        command_params: Command parameters for log filename
        log_dir: Directory for log files (default: ./storage/logs)
        log_to_file: Enable file logging
        log_to_console: Enable console logging
        log_level: Logging level

    Returns:
        CommandLogger instance
    """
    if log_dir is None:
        log_dir = Path("./storage/logs")

    return CommandLogger(
        log_dir=log_dir,
        command_params=command_params,
        log_to_file=log_to_file,
        log_to_console=log_to_console,
        log_level=log_level
    )
