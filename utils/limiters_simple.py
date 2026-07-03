"""
Simple rate limiter without transactions.
Uses a fixed 24-hour quota per user and feature.
"""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from database.firebase import db

logger = logging.getLogger("feature_limiters_simple")


def _get_reset_time(window_start: datetime) -> str:
    """
    Calculate the reset time (window_start + 24 hours)
    and convert to user's local timezone.
    """
    reset_time = window_start + timedelta(days=1)
    local_reset = reset_time.astimezone()
    return local_reset.strftime("%I:%M %p")


def enforce_feature_limit_simple(uid: str, feature_name: str, max_limit: int) -> int:
    """
    Enforce a fixed 24-hour quota for a user and feature.

    Each user has their own personal 24-hour window.

    Schema:
        {
            "window_start": Firestore Timestamp,
            "count": integer
        }

    Example:
        Limit = 5
        Day 1 8:00 AM -> Use #1 (window_start = 8:00 AM, count = 1)
        Day 1 8:05 AM -> Use #2 (count = 2)
        ...
        Day 1 8:20 AM -> Use #5 (count = 5)
        Day 1 8:21 AM -> Blocked (count >= max_limit)
        Day 2 8:00 AM -> Reset (window_start = now, count = 1)
    """
    now = datetime.now(timezone.utc)

    rate_limit_ref = db.collection("rate_limits").document(f"{uid}_{feature_name}")

    feature_labels = {
        "rate_limits": "Message",
        "uploads": "Upload",
        "mock_board_exam": "Exam generation",
        "quiz": "Quiz generation",
        "smart_notes": "Smart notes generation",
        "nurseon_ai_chat": "AI Chat",
        "case_studies": "Case study"
    }
    display_label = feature_labels.get(feature_name, "Feature request")

    try:
        # Step 1: Read current state
        doc = rate_limit_ref.get()

        if doc.exists:
            data = doc.to_dict() or {}
            window_start = data.get("window_start")
            count = data.get("count", 0)

            # Ensure window_start has timezone info
            if window_start:
                window_start = window_start if window_start.tzinfo else window_start.replace(tzinfo=timezone.utc)
            else:
                # No window_start, this is the first use
                window_start = now
                count = 0
        else:
            # No document exists, this is the first use
            window_start = now
            count = 0

        # Step 2: Check if the window has expired
        if now >= window_start + timedelta(days=1):
            # Window expired, reset
            window_start = now
            count = 0

        # Step 3: Check if limit exceeded
        if count >= max_limit:
            reset_time = _get_reset_time(window_start)

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"{display_label} limit reached. You can try again at {reset_time}."
            )

        # Step 4: Increment count and write back
        count += 1
        rate_limit_ref.set({
            "window_start": window_start,
            "count": count
        })

        remaining = max_limit - count
        logger.info(
            f"Rate limit check passed for {feature_name}: "
            f"{remaining} slots remaining in personal 24-hour window"
        )
        return remaining

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limiter error for {feature_name}: {str(e)}", exc_info=True)

        # Provide specific error message
        error_str = str(e).lower()
        if "permission" in error_str or "denied" in error_str:
            detail = "Database permission error. Please contact support."
        elif "not found" in error_str or "missing" in error_str:
            detail = "Database configuration error. Please contact support."
        elif "quota" in error_str or "limit" in error_str:
            detail = "Database quota exceeded. Please try again later."
        else:
            detail = "Failed to verify safety rate metrics. Please check server logs for details."

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


def check_rate_limit_status_simple(uid: str, feature_name: str, max_limit: int) -> dict:
    """
    Check rate limit status without consuming a request.

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

        rate_limit_ref = db.collection("rate_limits").document(f"{uid}_{feature_name}")

        try:
            doc = rate_limit_ref.get()
        except Exception as e:
            logger.error(f"Failed to check rate limit status: {str(e)}")
            return {
                "available": True,
                "remaining": max_limit,
                "used": 0,
                "reset_at": None
            }

        if not doc.exists:
            return {
                "available": True,
                "remaining": max_limit,
                "used": 0,
                "reset_at": None
            }

        data = doc.to_dict() or {}
        window_start = data.get("window_start")
        count = data.get("count", 0)

        if window_start:
            window_start = window_start if window_start.tzinfo else window_start.replace(tzinfo=timezone.utc)
        else:
            return {
                "available": True,
                "remaining": max_limit,
                "used": 0,
                "reset_at": None
            }

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