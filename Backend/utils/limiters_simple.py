"""
Simple rate limiter without transactions.
Uses a read-then-write pattern that's more reliable than transactions for this use case.
"""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from database.firebase import db

logger = logging.getLogger("feature_limiters_simple")

def enforce_feature_limit_simple(uid: str, feature_name: str, max_limit: int) -> int:
    """
    Simple rate limiter without transactions.
    
    This uses a read-then-write pattern which is more reliable for rate limiting
    where strict atomicity is not critical (it's better to allow a few extra
    requests than to block everything due to transaction failures).
    """
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(days=1)
    
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
        timestamps = []
        
        if doc.exists:
            data = doc.to_dict() or {}
            raw_timestamps = data.get("timestamps", [])
            # Ensure all timestamps have timezone info
            timestamps = [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in raw_timestamps]
        
        # Step 2: Filter out old timestamps
        valid_timestamps = [t for t in timestamps if t > twenty_four_hours_ago]
        
        # Step 3: Check if limit exceeded
        if len(valid_timestamps) >= max_limit:
            oldest_action = min(valid_timestamps)
            cooldown_end = oldest_action + timedelta(days=1)
            local_cooldown_time = cooldown_end.astimezone() 
            formatted_time = local_cooldown_time.strftime("%I:%M %p")
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"{display_label} limit reached. You can try again at {formatted_time}."
            )
        
        # Step 4: Add new timestamp and write back
        valid_timestamps.append(now)
        rate_limit_ref.set({"timestamps": valid_timestamps})
        
        remaining = max_limit - len(valid_timestamps)
        logger.info(f"Rate limit check passed for {feature_name}: {remaining} slots remaining")
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
    """
    try:
        now = datetime.now(timezone.utc)
        twenty_four_hours_ago = now - timedelta(days=1)
        
        rate_limit_ref = db.collection("rate_limits").document(f"{uid}_{feature_name}")
        
        try:
            doc = rate_limit_ref.get()
        except Exception as e:
            logger.error(f"Failed to check rate limit status: {str(e)}")
            return {
                "available": True,
                "remaining": max_limit,
                "reset_at": None
            }
        
        timestamps = []
        if doc.exists:
            data = doc.to_dict() or {}
            raw_timestamps = data.get("timestamps", [])
            timestamps = [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in raw_timestamps]
        
        valid_timestamps = [t for t in timestamps if t > twenty_four_hours_ago]
        remaining = max(0, max_limit - len(valid_timestamps))
        
        reset_at = None
        if len(valid_timestamps) >= max_limit:
            oldest_action = min(valid_timestamps)
            reset_at = (oldest_action + timedelta(days=1)).isoformat()
        
        return {
            "available": remaining > 0,
            "remaining": remaining,
            "reset_at": reset_at
        }
        
    except Exception as e:
        logger.error(f"Error checking rate limit: {str(e)}", exc_info=True)
        return {
            "available": True,
            "remaining": max_limit,
            "reset_at": None
        }