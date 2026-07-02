import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from database.firebase import db

logger = logging.getLogger("feature_limiters")

def enforce_feature_limit(uid: str, feature_name: str, max_limit: int) -> int:
    """
    Enforces a rolling 24-hour request/action limit for a specific user and feature.
    
    Uses Firestore transactions to prevent simultaneous request race conditions,
    automatically evicts timestamps older than 24 hours to keep document sizes small,
    and returns dynamically tailored error feedback based on the feature type.
    """
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(days=1)
    
    rate_limit_ref = db.collection("rate_limits").document(f"{uid}_{feature_name}")
    
    # Context-aware user messages to prevent mixed "Upload/Message" terminology bugs
    feature_labels = {
        "rate_limits": "Message",
        "uploads": "Upload",
        "mock_board_exam": "Exam generation"
    }
    display_label = feature_labels.get(feature_name, "Feature request")

    # Define the transactional operation block to enforce execution isolation
    @db.transaction
    def run_in_transaction(transaction):
        try:
            doc = rate_limit_ref.get(transaction=transaction)
        except Exception as read_err:
            logger.error(f"Failed to read limit state for user {uid}: {str(read_err)}")
            # Fallback defensively: reject the action if database state cannot be trusted
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Temporary database congestion. Please try again in a few moments."
            )
            
        timestamps = []
        if doc.exists:
            data = doc.to_dict() or {}
            raw_uploads = data.get("uploads", [])
            # Enforce clean UTC parsing context on raw database timestamps
            timestamps = [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in raw_uploads]
        
        # Self-cleaning array logic: Permanently drop keys older than 24 hours to optimize space
        valid_timestamps = [t for t in timestamps if t > twenty_four_hours_ago]
        
        if len(valid_timestamps) >= max_limit:
            oldest_upload = min(valid_timestamps)
            cooldown_end = oldest_upload + timedelta(days=1)
            
            # Extract localized local timezone text representation for client UI delivery
            local_cooldown_time = cooldown_end.astimezone() 
            formatted_time = local_cooldown_time.strftime("%I:%M %p")
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"{display_label} limit reached. You can try again at {formatted_time}."
            )
            
        # Append latest successful execution block marker
        valid_timestamps.append(now)
        
        # Commit back cleaned array data safely to Firebase
        transaction.set(rate_limit_ref, {"uploads": valid_timestamps})
        
        return max_limit - len(valid_timestamps)

    try:
        # Instantiate a transaction batch pipeline thread
        transaction_instance = db.transaction()
        return run_in_transaction(transaction_instance)
    except HTTPException:
        # Rethrow expected validation errors (like 429 Too Many Requests) unmodified
        raise
    except Exception as trans_err:
        logger.error(f"Transaction pipeline failed during feature limit enforcement: {str(trans_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify safety rate metrics."
        )