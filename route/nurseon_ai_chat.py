import os
import logging
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

# Define standard chat item for incoming structured thread histories
class MessageHistoryItem(BaseModel):
    role: str  # Must map to "user" or "model" for Gemini SDK
    parts: str

class ChatRequest(BaseModel):
    uid: str
    message: str
    history: list[MessageHistoryItem] = []  # Added to track conversational context

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
        
        # Structure the historical records into format required by SDK
        gemini_history = []
        for item in history:
            gemini_history.append({
                "role": "user" if item.role == "user" else "model",
                "parts": [item.parts]
            })

        # Start multi-turn session with historical context
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

@nurseon_ai_router.post("/chat", status_code=status.HTTP_200_OK)
async def nurseon_ai_chat(payload: ChatRequest):
    slots_remaining = enforce_feature_limit(payload.uid, "rate_limits", max_limit=10)

    try:
        # Pass conversation history along with current text line 
        ai_reply = run_gemini_nurseon_ai_chat(payload.message, payload.history)

        return {
            "status": "success",
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