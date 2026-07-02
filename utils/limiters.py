import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from database.firebase import db

logger = logging.getLogger("feature_limiters")

def enforce_feature_limit(uid: str, feature_name: str, max_limit: int) -> int:
    """
    Enforces a rolling 24-hour request/action limit for a specific user and feature.
    
    Uses Firestore transactions via context managers to prevent race conditions,
    automatically evicts timestamps older than 24 hours to keep document sizes small,
    and returns dynamically tailored error feedback based on the feature type.
    """
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(days=1)
    
    # Document isolated by both user ID and feature type
    rate_limit_ref = db.collection("rate_limits").document(f"{uid}_{feature_name}")
    
    # Context-aware user messages to prevent mixed terminology bugs
    feature_labels = {
        "rate_limits": "Message",
        "uploads": "Upload",
        "mock_board_exam": "Exam generation",
        "quiz": "Quiz generation",
        "smart_notes": "Smart notes generation"  # Fixed missing mapping for your router
    }
    display_label = feature_labels.get(feature_name, "Feature request")

    # Instantiate the Firestore transaction context object
    transaction = db.transaction()

    try:
        with transaction:
            # 1. READ phase (Must happen before writes inside a transaction)
            try:
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
                # Maintain 'timestamps' as a generic structural field key for consistency across documents
                raw_timestamps = data.get("timestamps", [])
                
                # Enforce clean UTC parsing context on raw database timestamps
                timestamps = [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in raw_timestamps]
            
            # Self-cleaning array logic: Drop keys older than 24 hours to optimize space
            valid_timestamps = [t for t in timestamps if t > twenty_four_hours_ago]
            
            # Enforce capacity
            if len(valid_timestamps) >= max_limit:
                oldest_action = min(valid_timestamps)
                cooldown_end = oldest_action + timedelta(days=1)
                
                # Extract localized local timezone text representation for client UI delivery
                local_cooldown_time = cooldown_end.astimezone() 
                formatted_time = local_cooldown_time.strftime("%I:%M %p")
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"{display_label} limit reached. You can try again at {formatted_time}."
                )
                
            # Append latest successful execution block marker
            valid_timestamps.append(now)
            
            # 2. WRITE phase
            transaction.set(rate_limit_ref, {"timestamps": valid_timestamps})
            
            return max_limit - len(valid_timestamps)

    except HTTPException:
        # Rethrow expected validation errors (like 429 or read failure HTTP exceptions) unmodified
        raise
    except Exception as trans_err:
        logger.error(f"Transaction pipeline failed during feature limit enforcement: {str(trans_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify safety rate metrics."
        )