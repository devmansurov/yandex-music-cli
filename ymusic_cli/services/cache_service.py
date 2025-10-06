"""Cache service implementation with Redis and in-memory fallback."""

import asyncio
import json
import logging
import pickle
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
import hashlib

from core.interfaces import CacheService
from core.models import CacheEntry
from core.exceptions import CacheError
from config.settings import get_settings


class InMemoryCacheService(CacheService):
    """In-memory cache implementation."""
    
    def __init__(self):
        self.cache: Dict[str, CacheEntry] = {}
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            entry = self.cache.get(key)
            if not entry:
                return None
            
            if entry.is_expired:
                del self.cache[key]
                return None
            
            return entry.value
            
        except Exception as e:
            self.logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Set value in cache with TTL."""
        try:
            entry = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl_seconds
            )
            self.cache[key] = entry
            
        except Exception as e:
            self.logger.error(f"Error setting cache key {key}: {e}")
            raise CacheError(f"Failed to set cache key: {e}")
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            return self.cache.pop(key, None) is not None
        except Exception as e:
            self.logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        try:
            self.cache.clear()
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            raise CacheError(f"Failed to clear cache: {e}")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            entry = self.cache.get(key)
            if not entry:
                return False
            
            if entry.is_expired:
                del self.cache[key]
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking cache key {key}: {e}")
            return False
    
    async def _periodic_cleanup(self) -> None:
        """Periodically clean up expired entries."""
        while True:
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                
                expired_keys = []
                for key, entry in self.cache.items():
                    if entry.is_expired:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.cache[key]
                
                if expired_keys:
                    self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
                
            except Exception as e:
                self.logger.error(f"Error in cache cleanup: {e}")
                await asyncio.sleep(60)  # Wait a bit before retrying


class RedisCacheService(CacheService):
    """Redis-based cache implementation."""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis = None
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis.asyncio as redis
            self.redis = redis.from_url(self.redis_url, decode_responses=False)
            
            # Test connection
            await self.redis.ping()
            self.logger.info("Redis cache service initialized")
            
        except ImportError:
            raise CacheError("redis package not installed")
        except Exception as e:
            self.logger.error(f"Failed to initialize Redis: {e}")
            raise CacheError(f"Redis initialization failed: {e}")
    
    async def cleanup(self) -> None:
        """Clean up Redis connection."""
        if self.redis:
            await self.redis.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.redis:
            return None
        
        try:
            data = await self.redis.get(key)
            if not data:
                return None
            
            # Deserialize the data
            return pickle.loads(data)
            
        except Exception as e:
            self.logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Set value in cache with TTL."""
        if not self.redis:
            raise CacheError("Redis not initialized")
        
        try:
            # Serialize the data
            data = pickle.dumps(value)
            await self.redis.setex(key, ttl_seconds, data)
            
        except Exception as e:
            self.logger.error(f"Error setting cache key {key}: {e}")
            raise CacheError(f"Failed to set cache key: {e}")
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.redis:
            return False
        
        try:
            result = await self.redis.delete(key)
            return result > 0
        except Exception as e:
            self.logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        if not self.redis:
            raise CacheError("Redis not initialized")
        
        try:
            await self.redis.flushdb()
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            raise CacheError(f"Failed to clear cache: {e}")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.redis:
            return False
        
        try:
            result = await self.redis.exists(key)
            return result > 0
        except Exception as e:
            self.logger.error(f"Error checking cache key {key}: {e}")
            return False


class SmartCacheService(CacheService):
    """Smart cache that falls back from Redis to in-memory."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        
        # Initialize primary and fallback caches
        if redis_url and self.settings.cache.enabled:
            self.primary_cache = RedisCacheService(redis_url)
            self.fallback_cache = InMemoryCacheService()
            self.use_redis = True
        else:
            self.primary_cache = InMemoryCacheService()
            self.fallback_cache = None
            self.use_redis = False
    
    async def initialize(self) -> None:
        """Initialize the cache service."""
        try:
            if self.use_redis:
                await self.primary_cache.initialize()
                self.logger.info("Using Redis cache with in-memory fallback")
            else:
                self.logger.info("Using in-memory cache only")
        except Exception as e:
            if self.fallback_cache:
                self.logger.warning(f"Redis failed, using in-memory cache: {e}")
                self.primary_cache = self.fallback_cache
                self.use_redis = False
            else:
                raise
    
    async def cleanup(self) -> None:
        """Clean up cache resources."""
        if hasattr(self.primary_cache, 'cleanup'):
            await self.primary_cache.cleanup()
        if self.fallback_cache and hasattr(self.fallback_cache, 'cleanup'):
            await self.fallback_cache.cleanup()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache with fallback."""
        # Try primary cache first
        try:
            return await self.primary_cache.get(key)
        except Exception as e:
            self.logger.warning(f"Primary cache failed for get({key}): {e}")
            
            # Try fallback cache
            if self.fallback_cache:
                try:
                    return await self.fallback_cache.get(key)
                except Exception as e2:
                    self.logger.error(f"Fallback cache also failed for get({key}): {e2}")
            
            return None
    
    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Set value in cache with fallback."""
        # Try primary cache first
        try:
            await self.primary_cache.set(key, value, ttl_seconds)
            return
        except Exception as e:
            self.logger.warning(f"Primary cache failed for set({key}): {e}")
            
            # Try fallback cache
            if self.fallback_cache:
                try:
                    await self.fallback_cache.set(key, value, ttl_seconds)
                    return
                except Exception as e2:
                    self.logger.error(f"Fallback cache also failed for set({key}): {e2}")
            
            # If both fail, raise the original error
            raise CacheError(f"All cache backends failed: {e}")
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        success = False
        
        # Try primary cache
        try:
            success = await self.primary_cache.delete(key)
        except Exception as e:
            self.logger.warning(f"Primary cache failed for delete({key}): {e}")
        
        # Try fallback cache
        if self.fallback_cache:
            try:
                fallback_success = await self.fallback_cache.delete(key)
                success = success or fallback_success
            except Exception as e:
                self.logger.warning(f"Fallback cache failed for delete({key}): {e}")
        
        return success
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        errors = []
        
        # Clear primary cache
        try:
            await self.primary_cache.clear()
        except Exception as e:
            errors.append(f"Primary cache: {e}")
        
        # Clear fallback cache
        if self.fallback_cache:
            try:
                await self.fallback_cache.clear()
            except Exception as e:
                errors.append(f"Fallback cache: {e}")
        
        if errors:
            raise CacheError(f"Cache clear errors: {'; '.join(errors)}")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        # Try primary cache first
        try:
            return await self.primary_cache.exists(key)
        except Exception as e:
            self.logger.warning(f"Primary cache failed for exists({key}): {e}")
            
            # Try fallback cache
            if self.fallback_cache:
                try:
                    return await self.fallback_cache.exists(key)
                except Exception as e2:
                    self.logger.error(f"Fallback cache also failed for exists({key}): {e2}")
            
            return False
    
    def generate_cache_key(self, prefix: str, *args: Any) -> str:
        """Generate a consistent cache key."""
        # Create a hash of the arguments
        key_data = f"{prefix}:" + ":".join(str(arg) for arg in args)
        return hashlib.md5(key_data.encode()).hexdigest()


def create_cache_service() -> CacheService:
    """Factory function to create the appropriate cache service."""
    settings = get_settings()
    
    if settings.cache.enabled and settings.cache.redis_url:
        return SmartCacheService(settings.cache.redis_url)
    else:
        return InMemoryCacheService()