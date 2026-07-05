# controllers/nurseon_ai_chat_controller.py
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, status

from services.nurseon_ai_chat_service import NurseonAIChatService
from utils.limiters import enforce_feature_limit, check_rate_limit_status

logger = logging.getLogger("nurseon_ai_chat_controller")

class NurseonAIChatController:
    def __init__(self):
        self.service = NurseonAIChatService()

    def process_chat(self, uid: str, message: str, session_id: str = None, history: list = None):
        try:
            slots_remaining = enforce_feature_limit(uid, "nurseon_ai_chat", max_limit=5)
        except HTTPException as e:
            if e.status_code == 429:
                limit_status = check_rate_limit_status(uid, "nurseon_ai_chat", max_limit=5)
                reset_msg = f" at {limit_status['reset_at']}" if limit_status.get("reset_at") else " tomorrow"
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"AI Chat limit reached. You can try again{reset_msg}."
                )
            raise e

        session_id = session_id or f"chat_{int(datetime.now(timezone.utc).timestamp())}"
        user_message = message
        now = datetime.now(timezone.utc)

        ai_reply = self.service.process_chat_message(uid, user_message, session_id, history or [])

        self.service.save_chat_message(uid, session_id, user_message, ai_reply, now)

        return {
            "status": "success",
            "reply": ai_reply,
            "session_id": session_id,
            "limit_remaining": slots_remaining
        }

    def check_limits(self, uid: str):
        if not uid:
            raise HTTPException(status_code=400, detail="Missing user payload reference ID.")
        
        limit_status = check_rate_limit_status(uid, "nurseon_ai_chat", max_limit=5)
        
        return {
            "status": "success",
            "limit_remaining": limit_status["remaining"],
            "available": limit_status["available"],
            "used": limit_status.get("used", 0),
            "reset_at": limit_status["reset_at"]
        }

    def get_chat_history(self, uid: str):
        sessions_list = self.service.get_chat_history(uid)
        return {"status": "success", "sessions": sessions_list}

    def get_single_session(self, uid: str, session_id: str):
        session_data = self.service.get_single_session(uid, session_id)
        return {"status": "success", **session_data}

    def toggle_pin(self, uid: str, session_id: str, pinned: bool):
        pinned_status = self.service.toggle_pin_status(uid, session_id, pinned)
        return {"status": "success", "pinned": pinned_status}

    def rename_session(self, uid: str, session_id: str, title: str):
        updated_title = self.service.rename_session(uid, session_id, title)
        return {"status": "success", "title": updated_title}

    def delete_session(self, uid: str, session_id: str):
        self.service.delete_session(uid, session_id)
        return {"status": "success", "message": "Thread deleted successfully."}

    def restore_session(self, uid: str, session_id: str, session_data: dict):
        self.service.restore_session(uid, session_id, session_data)
        return {"status": "success", "message": "Thread state context returned cleanly."}