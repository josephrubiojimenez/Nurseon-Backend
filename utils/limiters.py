import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from database.firebase import db

logger = logging.getLogger("feature_limiters")

def enforce_feature_limit(uid: str, feature_name: str, max_limit: int) -> int:
    """
    Enforces a rolling 24-hour request/action limit for a specific user and feature.
    
    Uses standard db.run_transaction() to handle Firestore transactions natively,
    ensuring safe operations against simultaneous request race conditions.
    """
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(days=1)
    
    rate_limit_ref = db.collection("rate_limits").document(f"{uid}_{feature_name}")
    
    feature_labels = {
        "rate_limits": "Message",
        "uploads": "Upload",
        "mock_board_exam": "Exam generation",
        "quiz": "Quiz generation",
        "smart_notes": "Smart notes generation"
    }
    display_label = feature_labels.get(feature_name, "Feature request")

    # 1. Define the separate, clean transactional operation function
    def _execute_transaction(transaction):
        try:
            # Pass the injected transaction instance directly into the read call
            doc = rate_limit_ref.get(transaction=transaction)
        except Exception as read_err:
            logger.error(f"Failed to read limit state for user {uid}: {str(read_err)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Temporary database congestion. Please try again in a few moments."
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

    # 2. Execute via the official manager
    try:
        return db.run_transaction(_execute_transaction)
    except HTTPException:
        # Pass up rate limits and controlled database connection errors unmodified
        raise
    except Exception as trans_err:
        logger.exception(f"Transaction pipeline failed during feature limit enforcement for user.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify safety rate metrics. Please check server logs for details."
        )