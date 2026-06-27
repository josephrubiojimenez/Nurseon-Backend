from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from database.firebase import db

def enforce_feature_limit(uid: str, feature_name: str, max_limit: int) -> int:
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(days=1)
    
    rate_limit_ref = db.collection("rate_limits").document(f"{uid}_{feature_name}")
    doc = rate_limit_ref.get()
    
    timestamps = []
    if doc.exists:
        data = doc.to_dict()
        timestamps = [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in data.get("uploads", [])]
    
    valid_timestamps = [t for t in timestamps if t > twenty_four_hours_ago]
    
    if len(valid_timestamps) >= max_limit:
        oldest_upload = min(valid_timestamps)
        cooldown_end = oldest_upload + timedelta(days=1)

        local_cooldown_time = cooldown_end.astimezone() 
        formatted_time = local_cooldown_time.strftime("%I:%M %p")
        
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Upload limit reached. Upload again at {formatted_time}."
        )
        
    valid_timestamps.append(now)
    rate_limit_ref.set({"uploads": valid_timestamps})
    
    return max_limit - len(valid_timestamps)