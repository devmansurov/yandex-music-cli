"""Progress tracking utilities."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Callable
from dataclasses import dataclass

from core.interfaces import ProgressTracker as ProgressTrackerInterface
from core.models import DownloadTask, ProgressUpdate, ProgressType
from config.settings import get_settings


@dataclass
class TrackingState:
    """State for progress tracking."""
    task: DownloadTask
    last_update: datetime
    update_callback: Optional[Callable] = None
    cancel_event: asyncio.Event = None
    
    def __post_init__(self):
        if self.cancel_event is None:
            self.cancel_event = asyncio.Event()


class ProgressTracker(ProgressTrackerInterface):
    """Progress tracker implementation."""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        
        # Active tracking
        self.active_tasks: Dict[str, TrackingState] = {}
        self.update_interval = self.settings.performance.progress_update_interval
    
    async def start_tracking(self, task: DownloadTask) -> None:
        """Start tracking progress for a task."""
        try:
            # Create tracking state
            state = TrackingState(
                task=task,
                last_update=datetime.now()
            )
            
            self.active_tasks[task.id] = state
            
            # Start update loop
            asyncio.create_task(self._update_loop(task.id))
            
            self.logger.info(f"Started tracking task {task.id}")
            
        except Exception as e:
            self.logger.error(f"Error starting progress tracking for {task.id}: {e}")
    
    async def update_progress(self, update: ProgressUpdate) -> None:
        """Update progress for a task."""
        try:
            state = self.active_tasks.get(update.task_id)
            if not state:
                return
            
            # Update task with progress info
            task = state.task
            
            if update.type == ProgressType.DISCOVERY:
                if update.current_depth is not None:
                    task.current_depth = update.current_depth
                if update.discovered_count is not None:
                    task.discovered_artists = update.discovered_count
            
            elif update.type == ProgressType.DOWNLOAD:
                if update.items_completed is not None:
                    task.completed_tracks = update.items_completed
                if update.items_total is not None:
                    task.total_tracks = update.items_total
            
            # Update last update time
            state.last_update = datetime.now()
            
            # Call update callback if set
            if state.update_callback:
                await state.update_callback(update)
            
        except Exception as e:
            self.logger.error(f"Error updating progress for {update.task_id}: {e}")
    
    async def complete_task(self, task_id: str, success: bool, error: Optional[str] = None) -> None:
        """Mark task as completed."""
        try:
            state = self.active_tasks.get(task_id)
            if not state:
                return
            
            # Update task
            task = state.task
            task.completed_at = datetime.now()
            
            if success:
                from core.models import DownloadStatus
                task.status = DownloadStatus.COMPLETED
            else:
                task.status = DownloadStatus.FAILED
                task.error_message = error
            
            # Signal cancellation to stop update loop
            state.cancel_event.set()
            
            self.logger.info(f"Task {task_id} completed - success: {success}")
            
        except Exception as e:
            self.logger.error(f"Error completing task {task_id}: {e}")
    
    async def cancel_task(self, task_id: str) -> None:
        """Cancel task tracking."""
        try:
            state = self.active_tasks.get(task_id)
            if not state:
                return
            
            # Update task status
            from core.models import DownloadStatus
            state.task.status = DownloadStatus.CANCELLED
            state.task.completed_at = datetime.now()
            
            # Signal cancellation
            state.cancel_event.set()
            
            self.logger.info(f"Task {task_id} cancelled")
            
        except Exception as e:
            self.logger.error(f"Error cancelling task {task_id}: {e}")
    
    async def set_update_callback(self, task_id: str, callback: Callable) -> None:
        """Set update callback for a task."""
        state = self.active_tasks.get(task_id)
        if state:
            state.update_callback = callback
    
    async def get_task_status(self, task_id: str) -> Optional[DownloadTask]:
        """Get current task status."""
        state = self.active_tasks.get(task_id)
        return state.task if state else None
    
    async def _update_loop(self, task_id: str) -> None:
        """Update loop for a task."""
        try:
            state = self.active_tasks.get(task_id)
            if not state:
                return
            
            while not state.cancel_event.is_set():
                try:
                    # Wait for update interval or cancellation
                    await asyncio.wait_for(
                        state.cancel_event.wait(),
                        timeout=self.update_interval
                    )
                    break  # Task was cancelled or completed
                    
                except asyncio.TimeoutError:
                    # Continue update loop
                    pass
                
                # Check if task should still be tracked
                if state.task.status.value in ['completed', 'failed', 'cancelled']:
                    break
                
                # Perform periodic update actions here if needed
                # For now, we just log the task is still active
                self.logger.debug(f"Task {task_id} still active")
            
        except Exception as e:
            self.logger.error(f"Error in update loop for {task_id}: {e}")
        
        finally:
            # Clean up
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            
            self.logger.debug(f"Update loop for {task_id} ended")
    
    def get_active_task_count(self) -> int:
        """Get number of active tasks."""
        return len(self.active_tasks)
    
    def get_active_task_ids(self) -> list:
        """Get list of active task IDs."""
        return list(self.active_tasks.keys())


class TelegramProgressTracker(ProgressTracker):
    """Progress tracker with Telegram message updates."""
    
    def __init__(self, bot, update_interval: int = 3):
        super().__init__()
        self.bot = bot
        self.message_update_interval = update_interval
        self.last_message_updates: Dict[str, datetime] = {}
    
    async def start_tracking(self, task: DownloadTask) -> None:
        """Start tracking with Telegram updates."""
        await super().start_tracking(task)
        
        # Set up Telegram update callback
        await self.set_update_callback(
            task.id,
            lambda update: self._send_telegram_update(task, update)
        )
    
    async def _send_telegram_update(self, task: DownloadTask, update: ProgressUpdate) -> None:
        """Send progress update to Telegram."""
        try:
            # Rate limit message updates
            now = datetime.now()
            last_update = self.last_message_updates.get(task.id)
            
            if last_update and (now - last_update).total_seconds() < self.message_update_interval:
                return  # Too soon since last update
            
            # Format progress message
            if update.type == ProgressType.DISCOVERY:
                message = self._format_discovery_message(task, update)
            elif update.type == ProgressType.DOWNLOAD:
                message = self._format_download_message(task, update)
            elif update.type == ProgressType.UPLOAD:
                message = self._format_upload_message(task, update)
            else:
                return  # Unknown update type
            
            # Send update
            if task.chat_id and task.message_id:
                try:
                    await self.bot.edit_message_text(
                        text=message,
                        chat_id=task.chat_id,
                        message_id=task.message_id,
                        parse_mode='Markdown'
                    )
                    
                    self.last_message_updates[task.id] = now
                    
                except Exception as e:
                    self.logger.debug(f"Failed to update message for task {task.id}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error sending Telegram update for {task.id}: {e}")
    
    def _format_discovery_message(self, task: DownloadTask, update: ProgressUpdate) -> str:
        """Format discovery progress message."""
        progress = update.progress_percent
        
        # Progress bar
        bar_length = 20
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        message = f"🔍 Discovering Similar Artists\n\n"
        message += f"📊 Progress: {progress:.1f}%\n"
        message += f"`{bar}` {update.items_completed or 0}/{update.items_total or 0}\n\n"
        
        if update.current_depth is not None and update.max_depth is not None:
            message += f"🌐 Level: {update.current_depth}/{update.max_depth}\n"

        if update.current_item:
            display_item = update.current_item[:40] + "..." if len(update.current_item) > 40 else update.current_item
            message += f"🎯 Current: {display_item}\n"

        if update.eta_seconds:
            eta_text = self._format_eta(update.eta_seconds)
            message += f"⏱️ ETA: {eta_text}\n"
        
        return message
    
    def _format_download_message(self, task: DownloadTask, update: ProgressUpdate) -> str:
        """Format download progress message."""
        progress = update.progress_percent
        
        # Progress bar
        bar_length = 20
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        message = f"🎵 Downloading Tracks\n\n"
        message += f"📊 Progress: {progress:.1f}%\n"
        message += f"`{bar}` {update.items_completed or 0}/{update.items_total or 0}\n\n"
        
        if update.current_item:
            display_item = update.current_item[:50] + "..." if len(update.current_item) > 50 else update.current_item
            message += f"🎯 Current: {display_item}\n"

        if update.download_speed:
            message += f"📡 Speed: {update.download_speed}\n"

        if update.eta_seconds:
            eta_text = self._format_eta(update.eta_seconds)
            message += f"⏱️ ETA: {eta_text}\n"
        
        return message
    
    def _format_upload_message(self, task: DownloadTask, update: ProgressUpdate) -> str:
        """Format upload progress message."""
        progress = update.progress_percent
        
        # Progress bar
        bar_length = 20
        filled = int(bar_length * progress / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        message = f"📤 Uploading Tracks\n\n"
        message += f"📊 Progress: {progress:.1f}%\n"
        message += f"`{bar}` {update.items_completed or 0}/{update.items_total or 0}\n\n"

        if update.current_item:
            display_item = update.current_item[:50] + "..." if len(update.current_item) > 50 else update.current_item
            message += f"📎 Current: {display_item}\n"
        
        return message
    
    def _format_eta(self, seconds: int) -> str:
        """Format ETA in human readable format."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"