"""
Fallback rate limiter that doesn't use Firestore.
Used when Firestore fails repeatedly.
"""
import logging
import threading
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status

logger = logging.getLogger("feature_limiters_fallback")

# In-memory storage as fallback (note: this is per-instance, not shared across instances)
_memory_limits = {}
_memory_lock = threading.Lock()


def _get_reset_time(window_start: datetime) -> str:
    """
    Calculate the reset time (window_start + 24 hours)
    and convert to user's local timezone.
    """
    reset_time = window_start + timedelta(days=1)
    local_reset = reset_time.astimezone()
    return local_reset.strftime("%I:%M %p")


def enforce_feature_limit_fallback(uid: str, feature_name: str, max_limit: int) -> int:
    """
    Fallback rate limiter using in-memory storage with fixed 24-hour quota.

    This is used when Firestore operations fail.
    The behavior is identical to limiters_simple.py but uses in-memory storage.

    Note: This only works for single-instance deployments.
    For multi-instance, use Redis or similar.
    """
    now = datetime.now(timezone.utc)
    key = f"{uid}_{feature_name}"

    with _memory_lock:
        if key not in _memory_limits:
            _memory_limits[key] = {
                "window_start": now,
                "count": 0
            }

        data = _memory_limits[key]
        window_start = data["window_start"]
        count = data["count"]

        # Check if the window has expired
        if now >= window_start + timedelta(days=1):
            window_start = now
            count = 0

        # Check if limit exceeded
        if count >= max_limit:
            reset_time = _get_reset_time(window_start)

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit reached. You can try again at {reset_time}."
            )

        # Increment count
        count += 1
        _memory_limits[key] = {
            "window_start": window_start,
            "count": count
        }

        remaining = max_limit - count

        logger.warning(
            f"Using fallback in-memory rate limiter for {feature_name}. "
            f"Remaining: {remaining} in personal 24-hour window"
        )

        return remaining


def check_rate_limit_status_fallback(uid: str, feature_name: str, max_limit: int) -> dict:
    """
    Check rate limit status without consuming a request using in-memory storage.

    Returns:
        {
            "available": bool,
            "remaining": int,
            "used": int,
            "reset_at": str | None
        }

    If the window has expired, returns:
        remaining = max_limit
        used = 0
        available = True
        reset_at = None
    """
    try:
        now = datetime.now(timezone.utc)
        key = f"{uid}_{feature_name}"

        with _memory_lock:
            if key not in _memory_limits:
                return {
                    "available": True,
                    "remaining": max_limit,
                    "used": 0,
                    "reset_at": None
                }

            data = _memory_limits[key]
            window_start = data["window_start"]
            count = data["count"]

            # Check if the window has expired
            if now >= window_start + timedelta(days=1):
                return {
                    "available": True,
                    "remaining": max_limit,
                    "used": 0,
                    "reset_at": None
                }

            used = count
            remaining = max(0, max_limit - used)

            reset_at = None
            if used >= max_limit:
                reset_at = _get_reset_time(window_start)

            return {
                "available": remaining > 0,
                "remaining": remaining,
                "used": used,
                "reset_at": reset_at
            }

    except Exception as e:
        logger.error(f"Error checking rate limit status: {str(e)}", exc_info=True)
        return {
            "available": True,
            "remaining": max_limit,
            "used": 0,
            "reset_at": None
        }


def cleanup_memory_limits():
    """Clean up expired entries from memory to prevent memory leaks."""
    now = datetime.now(timezone.utc)

    with _memory_lock:
        keys_to_delete = []
        for key, data in _memory_limits.items():
            window_start = data.get("window_start")
            if window_start:
                # If window_start is more than 24 hours ago, mark for deletion
                if now - window_start > timedelta(days=1):
                    keys_to_delete.append(key)

        for key in keys_to_delete:
            del _memory_limits[key]

    if keys_to_delete:
        logger.info(f"Cleaned up {len(keys_to_delete)} expired rate limit entries from memory")