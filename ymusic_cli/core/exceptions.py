"""Custom exceptions for the Telegram Music Bot."""


class BotError(Exception):
    """Base exception for bot errors."""
    
    def __init__(self, message: str, user_friendly: bool = True):
        super().__init__(message)
        self.user_friendly = user_friendly


class ValidationError(BotError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str = ""):
        super().__init__(message, user_friendly=True)
        self.field = field


class AuthenticationError(BotError):
    """Raised when user authentication fails."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, user_friendly=True)


class RateLimitError(BotError):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(message, user_friendly=True)
        self.retry_after = retry_after


class DownloadError(BotError):
    """Raised when download operation fails."""
    
    def __init__(self, message: str, track_id: str = "", retryable: bool = False):
        super().__init__(message, user_friendly=True)
        self.track_id = track_id
        self.retryable = retryable


class ServiceError(BotError):
    """Raised when external service operation fails."""
    
    def __init__(self, message: str, service: str = "", retryable: bool = True):
        super().__init__(message, user_friendly=False)
        self.service = service
        self.retryable = retryable


class ConfigurationError(BotError):
    """Raised when configuration is invalid."""
    
    def __init__(self, message: str):
        super().__init__(message, user_friendly=False)


class StorageError(BotError):
    """Raised when storage operation fails."""
    
    def __init__(self, message: str, operation: str = ""):
        super().__init__(message, user_friendly=False)
        self.operation = operation


class CacheError(BotError):
    """Raised when cache operation fails."""
    
    def __init__(self, message: str):
        super().__init__(message, user_friendly=False)


class NotFoundError(BotError):
    """Raised when requested resource is not found."""
    
    def __init__(self, message: str, resource_type: str = ""):
        super().__init__(message, user_friendly=True)
        self.resource_type = resource_type


class QuotaExceededError(BotError):
    """Raised when user quota is exceeded."""
    
    def __init__(self, message: str, quota_type: str = ""):
        super().__init__(message, user_friendly=True)
        self.quota_type = quota_type


class FileSystemError(BotError):
    """Raised when file system operation fails."""
    
    def __init__(self, message: str, path: str = ""):
        super().__init__(message, user_friendly=False)
        self.path = path


class NetworkError(BotError):
    """Raised when network operation fails."""
    
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message, user_friendly=False)
        self.retryable = retryable


class TaskCancelledError(BotError):
    """Raised when task is cancelled."""
    
    def __init__(self, task_id: str = ""):
        super().__init__("Task was cancelled", user_friendly=True)
        self.task_id = task_id


class ConcurrencyLimitError(BotError):
    """Raised when concurrency limit is reached."""
    
    def __init__(self, message: str = "Too many concurrent operations"):
        super().__init__(message, user_friendly=True)