"""
Fallback rate limiter that doesn't use Firestore transactions.
Used when transactions fail repeatedly.
"""
import logging
import time
import threading
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status

logger = logging.getLogger("feature_limiters_fallback")

# In-memory storage as fallback (note: this is per-instance, not shared across instances)
_memory_limits = {}
_memory_lock = threading.Lock()

def enforce_feature_limit_fallback(uid: str, feature_name: str, max_limit: int) -> int:
    """
    Fallback rate limiter using in-memory storage.
    This is used when Firestore transactions fail.
    Note: This only works for single-instance deployments.
    For multi-instance, use Redis or similar.
    """
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(days=1)
    
    key = f"{uid}_{feature_name}"
    
    with _memory_lock:
        if key not in _memory_limits:
            _memory_limits[key] = []
        
        # Clean old timestamps
        _memory_limits[key] = [t for t in _memory_limits[key] if t > twenty_four_hours_ago]
        
        # Check limit
        if len(_memory_limits[key]) >= max_limit:
            oldest_action = min(_memory_limits[key])
            cooldown_end = oldest_action + timedelta(days=1)
            local_cooldown_time = cooldown_end.astimezone()
            formatted_time = local_cooldown_time.strftime("%I:%M %p")
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit reached. You can try again at {formatted_time}."
            )
        
        # Add timestamp
        _memory_limits[key].append(now)
        remaining = max_limit - len(_memory_limits[key])
        
        logger.warning(
            f"Using fallback in-memory rate limiter for {feature_name}. "
            f"This is not recommended for production multi-instance deployments."
        )
        
        return remaining


def cleanup_memory_limits():
    """Clean up old entries from memory to prevent memory leaks."""
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(days=1)
    
    with _memory_lock:
        keys_to_delete = []
        for key, timestamps in _memory_limits.items():
            valid_timestamps = [t for t in timestamps if t > twenty_four_hours_ago]
            if not valid_timestamps:
                keys_to_delete.append(key)
            else:
                _memory_limits[key] = valid_timestamps
        
        for key in keys_to_delete:
            del _memory_limits[key]
    
    logger.info(f"Cleaned up {len(keys_to_delete)} expired rate limit entries from memory")