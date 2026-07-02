import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from database.firebase import db

logger = logging.getLogger("feature_limiters")

# Configuration
# Use simple non-transactional approach by default (more reliable)
# Transactions can be enabled if you need strict atomicity
USE_TRANSACTIONS = False  # Set to True to use transactions (may fail)
USE_FALLBACK_AFTER_FAILURES = 2
_consecutive_failures = 0
_fallback_enabled = False

def enforce_feature_limit(uid: str, feature_name: str, max_limit: int) -> int:
    """
    Enforces a rolling 24-hour request/action limit for a specific user and feature.
    
    Uses a simple read-then-write pattern by default (more reliable).
    Falls back to in-memory storage if Firestore is unavailable.
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

    # 1. Define the separate, clean transactional operation function
    def _execute_transaction(transaction):
        try:
            # Pass the injected transaction instance directly into the read call
            doc = rate_limit_ref.get(transaction=transaction)
        except Exception as read_err:
            logger.error(f"Failed to read limit state for user {uid}: {str(read_err)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database read error. Please try again in a moment."
            )
            
        timestamps = []
        if doc.exists:
            data = doc.to_dict() or {}
            raw_timestamps = data.get("timestamps", [])
            timestamps = [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in raw_timestamps]
        
        # Drop timestamps older than 24 hours
        valid_timestamps = [t for t in timestamps if t > twenty_four_hours_ago]
        
        if len(valid_timestamps) >= max_limit:
            oldest_action = min(valid_timestamps)
            cooldown_end = oldest_action + timedelta(days=1)
            
            local_cooldown_time = cooldown_end.astimezone() 
            formatted_time = local_cooldown_time.strftime("%I:%M %p")
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"{display_label} limit reached. You can try again at {formatted_time}."
            )
            
        valid_timestamps.append(now)
        
        # Write operations inside transactions must occur AFTER all read operations
        transaction.set(rate_limit_ref, {"timestamps": valid_timestamps})
        
        return max_limit - len(valid_timestamps)

    # 2. Use simple non-transactional approach (more reliable)
    global _consecutive_failures, _fallback_enabled
    
    try:
        # Use simple read-then-write (no transactions)
        from utils.limiters_simple import enforce_feature_limit_simple
        result = enforce_feature_limit_simple(uid, feature_name, max_limit)
        # Success - reset failure counter
        _consecutive_failures = 0
        return result
        
    except HTTPException:
        # Pass up rate limits immediately
        raise
    except Exception as e:
        _consecutive_failures += 1
        logger.error(f"Simple limiter failed: {str(e)}", exc_info=True)
        
        # Enable fallback after consecutive failures
        if _consecutive_failures >= USE_FALLBACK_AFTER_FAILURES:
            if not _fallback_enabled:
                logger.warning(f"Enabling fallback rate limiter after {_consecutive_failures} failures")
                _fallback_enabled = True
            
            # Try fallback
            try:
                from utils.limiters_fallback import enforce_feature_limit_fallback
                logger.info(f"Using fallback rate limiter for {feature_name}")
                return enforce_feature_limit_fallback(uid, feature_name, max_limit)
            except Exception as fallback_err:
                logger.error(f"Fallback also failed: {str(fallback_err)}")
        
        # If all else fails, allow the request (fail open)
        logger.warning(f"All rate limiters failed, allowing request for {feature_name}")
        return max_limit


def check_rate_limit_status(uid: str, feature_name: str, max_limit: int) -> dict:
    """
    Check rate limit status without consuming a request.
    Returns remaining slots and reset time.
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
                "available": True,  # Allow request if we can't check
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
            "available": True,  # Fail open to allow requests
            "remaining": max_limit,
            "reset_at": None
        }