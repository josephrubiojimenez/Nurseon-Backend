import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import List, Optional

from database.firebase import db
from google import genai
from google.genai import types
from utils.limiters import enforce_feature_limit
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger("nurseon_ai_chat")
nurseon_ai_chat_router = APIRouter()

# Setup rate limiter for safeguarding infrastructure
limiter = Limiter(key_func=get_remote_address)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai_client = None
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- Pydantic Schemas to Match Frontend Contracts ---
class MessageLog(BaseModel):
    role: str  # Frontend uses 'user' or 'model'
    parts: str # Frontend matches Gemini raw layout format string

class ChatPayload(BaseModel):
    uid: str
    message: str
    session_id: Optional[str] = None
    history: List[MessageLog] = []

class RenamePayload(BaseModel):
    title: str

# --- Helper to Format History for Google GenAI SDK ---
def convert_history_to_gemini(frontend_history: List[MessageLog]) -> list:
    gemini_contents = []
    for msg in frontend_history:
        # Maps frontend 'model' role back into GenAI SDK expected 'model' or 'assistant' format seamlessly
        role_type = "model" if msg.role == "model" else "user"
        gemini_contents.append(
            types.Content(
                role=role_type,
                parts=[types.Part.from_text(text=msg.parts)]
            )
        )
    return gemini_contents


@nurseon_ai_chat_router.post("/chat", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def process_nurseon_chat(request: Request, payload: ChatPayload):
    if not genai_client:
        raise HTTPException(status_code=500, detail="AI Core Core Engine offline.")

    # Enforce standard chat limit (10 queries per rolling window baseline)
    try:
        slots_remaining = enforce_feature_limit(payload.uid, "nurseon_ai_chat", max_limit=10)
    except HTTPException as he:
        raise he
    except Exception:
        slots_remaining = 0

    session_id = payload.session_id or f"chat_{int(datetime.now(timezone.utc).timestamp())}"
    user_message = payload.message
    now = datetime.now(timezone.utc)

    # Convert the payload history list into acceptable content objects
    sdk_contents = convert_history_to_gemini(payload.history)
    
    # Append current input question turning step
    sdk_contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
    )

    system_instruction = (
        "You are Nurseon AI, an expert clinical nurse educator and NCLEX board consultant. "
        "Provide evidence-based explanations, rationales, and professional nursing advice."
    )

    try:
        # Call modern content generation framework
        response = genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=sdk_contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
            )
        )

        ai_reply = response.text if response.text else "I am processing your clinical record, please re-submit your inquiry."

        # Save session history block synchronously to Firestore database
        session_ref = db.collection("users").document(payload.uid).collection("chat_sessions").document(session_id)
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
            # Generate auto-title summary based on first prompt cut length
            auto_title = user_message[:30] + "..." if len(user_message) > 30 else user_message
            session_ref.set({
                "id": session_id,
                "title": auto_title,
                "date": now.strftime("%Y-%m-%d"),
                "pinned": False,
                "messages": new_messages,
                "last_active": now
            })

        # Return exact names expected by NurseonAIChat.tsx updates
        return {
            "status": "success",
            "reply": ai_reply,
            "session_id": session_id,
            "limit_remaining": slots_remaining
        }

    except Exception as e:
        logger.error(f"Chat communication fault: {str(e)}")
        raise HTTPException(status_code=500, detail="Transmission failure on neural network processor.")


@nurseon_ai_chat_router.post("/limit-check", status_code=status.HTTP_200_OK)
async def check_chat_limits(payload: dict):
    uid = payload.get("uid")
    if not uid:
        raise HTTPException(status_code=400, detail="Missing user payload reference ID.")
    
    # Check limit without incrementing by mocking a dry transaction sequence or reading state balance parameters
    try:
        slots_remaining = enforce_feature_limit(uid, "nurseon_ai_chat", max_limit=10)
    except Exception:
        slots_remaining = 0
        
    return {"status": "success", "limit_remaining": slots_remaining}


@nurseon_ai_chat_router.get("/history/{uid}", status_code=status.HTTP_200_OK)
async def get_chat_history(uid: str):
    try:
        sessions_ref = db.collection("users").document(uid).collection("chat_sessions")
        # Pull records sorted by interaction timelines
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
            
        return {"status": "success", "sessions": sessions_list}
    except Exception as e:
        logger.error(f"Failed to fetch historical indexing lists: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load chat history threads.")


@nurseon_ai_chat_router.put("/history/{uid}/{session_id}/pin", status_code=status.HTTP_200_OK)
async def toggle_pin_status(uid: str, session_id: str, payload: dict):
    try:
        pinned = payload.get("pinned", False)
        session_ref = db.collection("users").document(uid).collection("chat_sessions").document(session_id)
        session_ref.update({"pinned": pinned})
        return {"status": "success", "pinned": pinned}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to patch pinned metrics: {str(e)}")


@nurseon_ai_chat_router.put("/history/{uid}/{session_id}/rename", status_code=status.HTTP_200_OK)
async def rename_session_thread(uid: str, session_id: str, payload: RenamePayload):
    try:
        session_ref = db.collection("users").document(uid).collection("chat_sessions").document(session_id)
        session_ref.update({"title": payload.title})
        return {"status": "success", "title": payload.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to re-index session mapping: {str(e)}")


@nurseon_ai_chat_router.delete("/history/{uid}/{session_id}", status_code=status.HTTP_200_OK)
async def delete_session_thread(uid: str, session_id: str):
    try:
        session_ref = db.collection("users").document(uid).collection("chat_sessions").document(session_id)
        session_ref.delete()
        return {"status": "success", "message": "Thread deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove thread trace elements: {str(e)}")


@nurseon_ai_chat_router.post("/history/{uid}/{session_id}/restore", status_code=status.HTTP_200_OK)
async def restore_session_thread(uid: str, session_id: str, payload: dict):
    try:
        session_data = payload.get("item", {})
        if not session_data:
            raise HTTPException(status_code=400, detail="Data payload restore backup frame target invalid.")
            
        session_ref = db.collection("users").document(uid).collection("chat_sessions").document(session_id)
        session_ref.set({
            "id": session_id,
            "title": session_data.get("title", "Restored Nursing Session"),
            "date": session_data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "pinned": session_data.get("pinned", False),
            "messages": session_data.get("messages", []),
            "last_active": datetime.now(timezone.utc)
        })
        return {"status": "success", "message": "Thread state context returned cleanly."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rewrite structural state elements: {str(e)}")