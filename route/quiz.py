import os
import logging
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Form, status
from pydantic import BaseModel, Field
import google.generativeai as genai

from database.firebase import db
from utils.limiters import enforce_feature_limit

logger = logging.getLogger("quiz_router")
quiz_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class QuizGenerationPayload(BaseModel):
    uid: str
    topic: str
    num_questions: int = Field(default=5, ge=1, le=50)

def run_gemini_quiz_generation(topic: str, num_questions: int) -> list:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service is currently unconfigured."
        )

    model = genai.GenerativeModel("gemini-2.5-flash")
    
    system_prompt = (
        "You are an expert Nursing Board Exam (NCLEX) Quiz Creator. Create a highly accurate "
        f"multiple-choice quiz consisting of exactly {num_questions} questions about the requested topic.\n\n"
        "You MUST return ONLY a clean JSON array (no markdown code blocks, no ```json formatting wrappers). "
        "Each object in the array must follow this exact schema:\n"
        "{\n"
        '  "question": "The question string here?",\n'
        '  "options": ["Option A", "Option B", "Option C", "Option D"],\n'
        '  "correct_answer": "The exact string match of the correct option",\n'
        '  "rationale": "Clinical rationale explaining why this answer is correct."\n'
        "}"
    )

    try:
        response = model.generate_content(system_prompt + f"\n\nTopic: {topic}")
        clean_text = response.text.strip()
        
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
        if clean_text.startswith("json"):
            clean_text = clean_text.split("\n", 1)[1].strip()

        return json.loads(clean_text)
    except Exception as e:
        logger.error(f"Gemini Quiz Parsing Failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate a cleanly structured quiz layout."
        )

@quiz_router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_quiz(payload: QuizGenerationPayload):
    slots_remaining = enforce_feature_limit(payload.uid, "quiz", max_limit=5)

    try:
        
        questions_list = run_gemini_quiz_generation(payload.topic, payload.num_questions)

        quiz_data = {
            "user_uid": payload.uid,
            "topic": payload.topic,
            "questions": questions_list,
            "created_at": datetime.now(timezone.utc)
        }

        doc_ref = db.collection("generated_quizzes").document()
        doc_ref.set(quiz_data)

        return {
            "status": "success",
            "quiz_id": doc_ref.id,
            "topic": quiz_data["topic"],
            "questions": questions_list,
            "slots_remaining": slots_remaining
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Quiz runtime crash: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal application error generating the quiz."
        )