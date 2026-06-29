# FastAPI Router (nurseon_ai_router.py)
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import google.generativeai as genai

from database.firebase import db
from utils.limiters import enforce_feature_limit

logger = logging.getLogger("nurseon_ai_router")
nurseon_ai_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class MessageHistoryItem(BaseModel):
    role: str  
    parts: str

class ChatRequest(BaseModel):
    uid: str
    message: str
    session_id: str | None = None 
    history: list[MessageHistoryItem] = []

class RenameRequest(BaseModel):
    title: str

class PinRequest(BaseModel):
    pinned: bool

class LimitCheckRequest(BaseModel):
    uid: str

def run_gemini_nurseon_ai_chat(message: str, history: list[MessageHistoryItem]) -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service is currently unconfigured."
        )

    system_instruction = (
        "You are NurseonAI, an expert Nursing Professional, Clinical Instructor, and Mentor. "
        "Your user is a nursing student who is seeking guidance, clinical information, or asking 'what to do' in a scenario.\n\n"
        "YOUR ROLE:\n"
        "1. Act as an experienced, supportive, yet highly precise professional nurse practitioner/educator/instructor.\n"
        "2. Provide clear, step-by-step guidance, rationales, and professional critique on their questions or proposed actions.\n"
        "3. Highlight safety priorities (like the ABCs—Airway, Breathing, Circulation), infection control, or patient dignity where relevant.\n"
        "4. Keep your language professional, educational, and structured using medical terminology, helping them think like a real nurse."
    )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )
        
        gemini_history = []
        for item in history:
            gemini_history.append({
                "role": "user" if item.role == "user" else "model",
                "parts": [item.parts]
            })

        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(message)
        
        clean_text = response.text.strip()
        
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
        if clean_text.startswith("json"):
            clean_text = clean_text.split("\n", 1)[1].strip()

        return clean_text
    except Exception as e:
        logger.error(f"AI Failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate AI response."
        )

@nurseon_ai_router.post("/limit-check", status_code=status.HTTP_200_OK)
async def check_ask_limit(payload: LimitCheckRequest):
    try:
        slots_remaining = enforce_feature_limit(payload.uid, "rate_limits", max_limit=10)
        return {"status": "success", "limit_remaining": slots_remaining}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@nurseon_ai_router.post("/chat", status_code=status.HTTP_200_OK)
async def nurseon_ai_chat(payload: ChatRequest):
    slots_remaining = enforce_feature_limit(payload.uid, "rate_limits", max_limit=10)

    try:
        ai_reply = run_gemini_nurseon_ai_chat(payload.message, payload.history)
        user_chats_ref = db.collection("users").document(payload.uid).collection("nurseon_chats")

        if payload.session_id:
            session_doc = user_chats_ref.document(payload.session_id)
        else:
            session_doc = user_chats_ref.document()

        new_messages = [
            {"role": "user", "parts": payload.message},
            {"role": "model", "parts": ai_reply}
        ]

        doc_snapshot = session_doc.get()
        if doc_snapshot.exists:
            current_data = doc_snapshot.to_dict() or {}
            existing_messages = current_data.get("messages", [])
            session_doc.update({
                "messages": existing_messages + new_messages,
                "updated_at": datetime.now(timezone.utc)
            })
            session_id = payload.session_id
        else:
            generated_title = payload.message[:40] + "..." if len(payload.message) > 40 else payload.message
            
            session_doc.set({
                "title": generated_title,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "messages": new_messages,
                "pinned": False
            })
            session_id = session_doc.id

        return {
            "status": "success",
            "session_id": session_id,
            "reply": ai_reply,
            "limit_remaining": slots_remaining
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Nurseon AI crashed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal application error communicating with NurseonAI."
        )

@nurseon_ai_router.get("/history/{uid}", status_code=status.HTTP_200_OK)
async def get_user_chat_sessions(uid: str):
    try:
        sessions_ref = db.collection("users").document(uid).collection("nurseon_chats")
        docs = sessions_ref.order_by("updated_at", direction="DESCENDING").stream()

        sessions_list = []
        for doc in docs:
            data = doc.to_dict()
            formatted_date = data["updated_at"].strftime("%Y-%m-%d") if "updated_at" in data else ""
            
            sessions_list.append({
                "id": doc.id,
                "title": data.get("title", "Untitled Chat Case"),
                "date": formatted_date,
                "pinned": data.get("pinned", False)
            })

        return {"status": "success", "sessions": sessions_list}
    except Exception as e:
        logger.error(f"Failed to fetch chat logs list: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve history logs.")

@nurseon_ai_router.put("/history/{uid}/{session_id}/rename", status_code=status.HTTP_200_OK)
async def rename_chat_session(uid: str, session_id: str, payload: RenameRequest):
    try:
        doc_ref = db.collection("users").document(uid).collection("nurseon_chats").document(session_id)
        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        doc_ref.update({"title": payload.title})
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@nurseon_ai_router.put("/history/{uid}/{session_id}/pin", status_code=status.HTTP_200_OK)
async def pin_chat_session(uid: str, session_id: str, payload: PinRequest):
    try:
        doc_ref = db.collection("users").document(uid).collection("nurseon_chats").document(session_id)
        if not doc_ref.get().exists:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        doc_ref.update({"pinned": payload.pinned})
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@nurseon_ai_router.get("/history/{uid}/{session_id}", status_code=status.HTTP_200_OK)
async def get_single_session_thread(uid: str, session_id: str):
    try:
        doc_ref = db.collection("users").document(uid).collection("nurseon_chats").document(session_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Requested conversation thread was not found.")

        data = doc.to_dict() or {}
        return {
            "status": "success",
            "title": data.get("title", "Untitled Chat Case"),
            "messages": data.get("messages", [])
        }
    except HTTPException as h_err:
        raise h_err
    except Exception as e:
        logger.error(f"Failed to fetch deep message array thread: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to pull conversation metrics.")