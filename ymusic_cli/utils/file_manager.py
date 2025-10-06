"""File management utilities."""

import asyncio
import hashlib
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
import aiofiles
import aiofiles.os
from datetime import datetime, timedelta

from core.interfaces import FileManager as FileManagerInterface
from core.models import FileInfo
from core.exceptions import FileSystemError
from config.settings import get_settings


class FileManager(FileManagerInterface):
    """File management implementation."""
    
    def __init__(self, temp_dir: Path, storage_dir: Path):
        self.temp_dir = Path(temp_dir)
        self.storage_dir = Path(storage_dir)
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        
        # File type mappings
        self.audio_extensions = {'.mp3', '.flac', '.m4a', '.ogg', '.wav'}
        self.allowed_extensions = self.audio_extensions.copy()
    
    async def initialize(self) -> None:
        """Initialize the file manager."""
        try:
            # Ensure directories exist
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories
            (self.storage_dir / "downloads").mkdir(exist_ok=True)
            (self.storage_dir / "cache").mkdir(exist_ok=True)
            
            self.logger.info(f"File manager initialized - temp: {self.temp_dir}, storage: {self.storage_dir}")
            
            # Start cleanup task
            asyncio.create_task(self._periodic_cleanup())
            
        except Exception as e:
            self.logger.error(f"Failed to initialize file manager: {e}")
            raise FileSystemError(f"File manager initialization failed: {e}")
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # Clean up temporary files
            await self.cleanup_temp_files(0)  # Clean all temp files
            self.logger.info("File manager cleanup complete")
        except Exception as e:
            self.logger.error(f"Error during file manager cleanup: {e}")
    
    async def save_file(self, data: bytes, filename: str, temp: bool = False) -> Path:
        """Save file to storage."""
        try:
            # Sanitize filename
            safe_filename = self._sanitize_filename(filename)
            
            # Choose directory
            target_dir = self.temp_dir if temp else self.storage_dir / "downloads"
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename if needed
            file_path = target_dir / safe_filename
            if file_path.exists():
                file_path = self._generate_unique_filename(file_path)
            
            # Check file size
            if len(data) > self.settings.files.max_file_size_mb * 1024 * 1024:
                raise FileSystemError(
                    f"File too large: {len(data) / 1024 / 1024:.1f} MB "
                    f"(max: {self.settings.files.max_file_size_mb} MB)"
                )
            
            # Write file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(data)
            
            self.logger.debug(f"Saved file: {file_path} ({len(data)} bytes)")
            return file_path
            
        except Exception as e:
            self.logger.error(f"Error saving file {filename}: {e}")
            raise FileSystemError(f"Failed to save file: {e}", filename)
    
    async def get_file_info(self, path: Path) -> Optional[FileInfo]:
        """Get file information."""
        try:
            if not path.exists():
                return None
            
            stat = path.stat()
            
            # Determine format from extension
            format_name = path.suffix.lower().lstrip('.')
            
            # Get quality (simplified logic)
            quality = self._detect_quality(path)
            
            file_info = FileInfo(
                path=path,
                size=stat.st_size,
                format=format_name,
                quality=quality,
                created_at=datetime.fromtimestamp(stat.st_ctime)
            )
            
            return file_info
            
        except Exception as e:
            self.logger.error(f"Error getting file info for {path}: {e}")
            return None
    
    async def delete_file(self, path: Path) -> bool:
        """Delete a file."""
        try:
            if path.exists():
                await aiofiles.os.remove(path)
                self.logger.debug(f"Deleted file: {path}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting file {path}: {e}")
            return False
    
    async def cleanup_temp_files(self, older_than_hours: int = 24) -> int:
        """Clean up temporary files."""
        cleaned_count = 0
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        
        try:
            for file_path in self.temp_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < cutoff_time:
                            await self.delete_file(file_path)
                            cleaned_count += 1
                    except Exception as e:
                        self.logger.debug(f"Error cleaning file {file_path}: {e}")
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} temporary files")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Error during temp file cleanup: {e}")
            return cleaned_count
    
    async def get_disk_usage(self) -> Dict[str, float]:
        """Get disk usage statistics."""
        try:
            # Get storage directory usage
            storage_usage = await self._get_directory_size(self.storage_dir)
            temp_usage = await self._get_directory_size(self.temp_dir)
            
            # Get available space
            storage_stat = shutil.disk_usage(self.storage_dir)
            
            return {
                'storage_used_mb': storage_usage / (1024 * 1024),
                'temp_used_mb': temp_usage / (1024 * 1024),
                'total_space_mb': storage_stat.total / (1024 * 1024),
                'available_space_mb': storage_stat.free / (1024 * 1024),
                'used_percent': ((storage_stat.total - storage_stat.free) / storage_stat.total) * 100
            }
            
        except Exception as e:
            self.logger.error(f"Error getting disk usage: {e}")
            return {}
    
    async def calculate_checksum(self, path: Path) -> str:
        """Calculate file checksum."""
        try:
            hash_md5 = hashlib.md5()
            async with aiofiles.open(path, 'rb') as f:
                while chunk := await f.read(8192):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
            
        except Exception as e:
            self.logger.error(f"Error calculating checksum for {path}: {e}")
            raise FileSystemError(f"Failed to calculate checksum: {e}", str(path))
    
    async def find_duplicates(self, directory: Path) -> Dict[str, List[Path]]:
        """Find duplicate files by checksum."""
        checksums: Dict[str, List[Path]] = {}
        
        try:
            for file_path in directory.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in self.allowed_extensions:
                    try:
                        checksum = await self.calculate_checksum(file_path)
                        if checksum not in checksums:
                            checksums[checksum] = []
                        checksums[checksum].append(file_path)
                    except Exception as e:
                        self.logger.debug(f"Error processing file {file_path}: {e}")
            
            # Return only duplicates
            duplicates = {checksum: paths for checksum, paths in checksums.items() if len(paths) > 1}
            
            if duplicates:
                total_dupes = sum(len(paths) - 1 for paths in duplicates.values())
                self.logger.info(f"Found {len(duplicates)} sets of duplicates ({total_dupes} duplicate files)")
            
            return duplicates
            
        except Exception as e:
            self.logger.error(f"Error finding duplicates in {directory}: {e}")
            return {}
    
    async def move_file(self, source: Path, destination: Path) -> bool:
        """Move file from source to destination."""
        try:
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file
            shutil.move(str(source), str(destination))
            
            self.logger.debug(f"Moved file: {source} -> {destination}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error moving file {source} to {destination}: {e}")
            return False
    
    async def copy_file(self, source: Path, destination: Path) -> bool:
        """Copy file from source to destination."""
        try:
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(str(source), str(destination))
            
            self.logger.debug(f"Copied file: {source} -> {destination}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error copying file {source} to {destination}: {e}")
            return False
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage."""
        import re
        
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)  # Remove control characters
        sanitized = sanitized.strip()
        
        # Ensure filename isn't empty
        if not sanitized:
            sanitized = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Limit length
        if len(sanitized) > 200:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            max_name_len = 195 - len(ext)
            sanitized = name[:max_name_len] + ('.' + ext if ext else '')
        
        return sanitized
    
    def _generate_unique_filename(self, path: Path) -> Path:
        """Generate unique filename by adding counter."""
        counter = 1
        base_name = path.stem
        extension = path.suffix
        parent = path.parent
        
        while True:
            new_name = f"{base_name}_{counter}{extension}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
            
            # Safety limit
            if counter > 1000:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                return parent / f"{base_name}_{timestamp}{extension}"
    
    def _detect_quality(self, path: Path) -> str:
        """Detect audio quality from file (simplified)."""
        # This is a simplified implementation
        # In a real implementation, you might use mutagen or similar
        try:
            size_mb = path.stat().st_size / (1024 * 1024)
            
            # Rough quality estimation based on file size (very basic)
            if size_mb > 8:
                return "high"
            elif size_mb > 4:
                return "medium"
            else:
                return "low"
                
        except:
            return "unknown"
    
    async def _get_directory_size(self, directory: Path) -> int:
        """Get total size of directory in bytes."""
        total_size = 0
        try:
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            self.logger.debug(f"Error calculating directory size for {directory}: {e}")
        return total_size
    
    async def _periodic_cleanup(self) -> None:
        """Periodically clean up old files."""
        while True:
            try:
                # Sleep for 1 hour
                await asyncio.sleep(3600)
                
                # Clean up temp files older than configured hours
                await self.cleanup_temp_files(self.settings.files.auto_cleanup_hours)
                
            except Exception as e:
                self.logger.error(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying