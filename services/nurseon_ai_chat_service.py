# services/nurseon_ai_chat_service.py
import os
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, status
from typing import List, Optional

from database.firebase import db
from google import genai
from google.genai import types
from models.nurseon_ai_chat_models import MessageLog

logger = logging.getLogger("nurseon_ai_chat_service")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai_client = None
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)

class NurseonAIChatService:
    @staticmethod
    def convert_history_to_gemini(frontend_history: List[MessageLog]) -> list:
        gemini_contents = []
        for msg in frontend_history:
            role_type = "model" if msg.role == "model" else "user"
            gemini_contents.append(
                types.Content(
                    role=role_type,
                    parts=[types.Part.from_text(text=msg.parts)]
                )
            )
        return gemini_contents

    @staticmethod
    def get_chat_session(uid: str, session_id: str):
        return db.collection("users").document(uid).collection("chat_sessions").document(session_id)

    @staticmethod
    def get_chat_sessions_collection(uid: str):
        return db.collection("users").document(uid).collection("chat_sessions")

    @staticmethod
    def process_chat_message(uid: str, user_message: str, session_id: str, history: List[MessageLog]):
        if not genai_client:
            raise HTTPException(status_code=500, detail="AI Core Core Engine offline.")

        sdk_contents = NurseonAIChatService.convert_history_to_gemini(history)
        sdk_contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )

        system_instruction = (
            "You are Nurseon AI, an expert clinical nurse educator and NCLEX board consultant. "
            "Provide evidence-based explanations, rationales, and professional nursing advice."
        )

        try:
            response = genai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=sdk_contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                )
            )

            ai_reply = response.text if response.text else "I am processing your clinical record, please re-submit your inquiry."
            return ai_reply

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Chat communication fault: {error_msg}", exc_info=True)
            
            if "429" in error_msg or "quota" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"AI Chat limit reached. Please try again later."
                )
            elif "api_key" in error_msg.lower() or "invalid" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="AI service configuration error. Please contact support."
                )
            elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="AI platform is taking too long to respond. Please try again."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"AI platform processing failed: {error_msg[:100]}"
                )

    @staticmethod
    def save_chat_message(uid: str, session_id: str, user_message: str, ai_reply: str, now: datetime):
        session_ref = NurseonAIChatService.get_chat_session(uid, session_id)
        session_snap = session_ref.get()

        new_messages = [
            {"role": "user", "parts": user_message},
            {"role": "model", "parts": ai_reply}
        ]

        if session_snap.exists:
            current_data = session_snap.to_dict() or {}
            updated_messages = current_data.get("messages", []) + new_messages
            session_ref.update({
                "messages": updated_messages,
                "last_active": now
            })
        else:
            auto_title = user_message[:30] + "..." if len(user_message) > 30 else user_message
            session_ref.set({
                "id": session_id,
                "title": auto_title,
                "date": now.strftime("%Y-%m-%d"),
                "pinned": False,
                "messages": new_messages,
                "last_active": now
            })

    @staticmethod
    def get_chat_history(uid: str):
        try:
            sessions_ref = NurseonAIChatService.get_chat_sessions_collection(uid)
            docs = sessions_ref.order_by("last_active", direction="DESCENDING").stream()
            
            sessions_list = []
            for doc in docs:
                data = doc.to_dict()
                sessions_list.append({
                    "id": data.get("id", doc.id),
                    "title": data.get("title", "Untitled Case Study Thread"),
                    "date": data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                    "pinned": data.get("pinned", False),
                    "messages": data.get("messages", [])
                })
                
            return sessions_list
        except Exception as e:
            logger.error(f"Failed to fetch historical indexing lists: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to load chat history threads.")

    @staticmethod
    def get_single_session(uid: str, session_id: str):
        try:
            session_ref = NurseonAIChatService.get_chat_session(uid, session_id)
            doc = session_ref.get()

            if not doc.exists:
                raise HTTPException(status_code=404, detail="Session not found.")

            data = doc.to_dict()
            return {
                "id": data.get("id", doc.id),
                "title": data.get("title", "Untitled"),
                "date": data.get("date", ""),
                "pinned": data.get("pinned", False),
                "messages": data.get("messages", [])
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch session {session_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Could not pull your conversation log right now.")

    @staticmethod
    def toggle_pin_status(uid: str, session_id: str, pinned: bool):
        try:
            session_ref = NurseonAIChatService.get_chat_session(uid, session_id)
            session_ref.update({"pinned": pinned})
            return pinned
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to patch pinned metrics: {str(e)}")

    @staticmethod
    def rename_session(uid: str, session_id: str, title: str):
        try:
            session_ref = NurseonAIChatService.get_chat_session(uid, session_id)
            session_ref.update({"title": title})
            return title
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to re-index session mapping: {str(e)}")

    @staticmethod
    def delete_session(uid: str, session_id: str):
        try:
            session_ref = NurseonAIChatService.get_chat_session(uid, session_id)
            session_ref.delete()
            return True
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to remove thread trace elements: {str(e)}")

    @staticmethod
    def restore_session(uid: str, session_id: str, session_data: dict):
        try:
            if not session_data:
                raise HTTPException(status_code=400, detail="Data payload restore backup frame target invalid.")
                
            session_ref = NurseonAIChatService.get_chat_session(uid, session_id)
            session_ref.set({
                "id": session_id,
                "title": session_data.get("title", "Restored Nursing Session"),
                "date": session_data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                "pinned": session_data.get("pinned", False),
                "messages": session_data.get("messages", []),
                "last_active": datetime.now(timezone.utc)
            })
            return True
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to rewrite structural state elements: {str(e)}")