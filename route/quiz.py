import os
import logging
import json
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import google.generativeai as genai

from database.firebase import db
from utils.limiters import enforce_feature_limit, check_rate_limit_status

logger = logging.getLogger("quiz_router")
quiz_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# 1. SCHEMAS & STRUCTURAL PAYLOADS
# ==========================================

class QuizGenerationPayload(BaseModel):
    uid: str
    topic: str
    num_questions: int = Field(default=5, ge=1, le=20)

class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_answer: str
    rationale: str

class QuizStructure(BaseModel):
    questions: list[QuizQuestion]

# ==========================================
# 2. CORE AI GENERATION ENGINE
# ==========================================

def run_gemini_quiz_generation(topic: str, num_questions: int) -> list:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service is currently unconfigured."
        )

    model = genai.GenerativeModel("gemini-2.5-flash")
    
    system_prompt = (
        f"You are an expert Nursing Board Exam (NCLEX) and (PNLE) Quiz Creator. Create a highly accurate "
        f"multiple-choice quiz consisting of exactly {num_questions} questions about the requested topic."
    )

    try:
        response = model.generate_content(
            f"System: {system_prompt}\n\nTopic: {topic}",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=QuizStructure
            )
        )
        
        quiz_data = json.loads(response.text)
        return quiz_data["questions"]

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Gemini Quiz Parsing/API Failure: {error_msg}", exc_info=True)
        
        if "429" in error_msg or "quota" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests right now. Please wait a minute and try again."
            )
        elif "api_key" in error_msg.lower() or "invalid" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Our AI assistant is taking a break. Please try again in a few minutes."
            )
        elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="The AI is thinking too hard. Please try again in a moment."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_520_UNKNOWN_ERROR,
                detail="Oops! Something went wrong. Please try again."
            )


@quiz_router.get("/usage/{uid}")
async def get_user_usage(uid: str):
    """Get the current quiz usage and limits for a user."""
    try:
        limit_status = check_rate_limit_status(uid, "quiz", max_limit=5)
        return {
            "status": "success",
            "slots_remaining": limit_status["remaining"],
            "used": limit_status.get("used", 0),
            "max_limit": 5,
            "is_limit_reached": limit_status["remaining"] <= 0,
            "reset_at": limit_status["reset_at"],
            "available": limit_status["available"]
        }
    except Exception as e:
        logger.error(f"Failed to get usage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage information"
        )


@quiz_router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_quiz(payload: QuizGenerationPayload):
    # ==========================================
    # 1. CHECK LIMITS FIRST
    # ==========================================
    try:
        slots_remaining = enforce_feature_limit(payload.uid, "quiz", max_limit=5)
        is_limit_reached = False
    except HTTPException as e:
        if e.status_code == 429:
            limit_status = check_rate_limit_status(payload.uid, "quiz", max_limit=5)
            reset_msg = f" at {limit_status['reset_at']}" if limit_status.get("reset_at") else " tomorrow"
            return {
                "status": "error",
                "detail": f"Quiz limit reached. You can try again{reset_msg}.",
                "slots_remaining": limit_status["remaining"],
                "is_limit_reached": True,
                "used": limit_status.get("used", 0),
                "max_limit": 5,
                "reset_at": limit_status["reset_at"],
                "available": limit_status["available"]
            }
        raise e

    # ==========================================
    # 2. PROCEED WITH QUIZ GENERATION
    # ==========================================
    try:
        clean_topic = payload.topic.strip().lower()
        quiz_fingerprint = hashlib.md5(f"{clean_topic}_{payload.num_questions}".encode('utf-8')).hexdigest()

        cache_doc = db.collection("quizzes_cache").document(quiz_fingerprint).get()

        if cache_doc.exists:
            cached_quiz = cache_doc.to_dict()
            logger.info(f"Quiz Cache Hit! Serving topic: '{payload.topic}' with {payload.num_questions} items.")

            user_quiz_record = {
                "user_uid": payload.uid,
                "topic": payload.topic,
                "questions": cached_quiz["questions"],
                "created_at": datetime.now(timezone.utc),
                "source": "cache"
            }
            db.collection("generated_quizzes").document().set(user_quiz_record)

            return {
                "status": "success",
                "is_cached": True,
                "quiz_id": cache_doc.id,
                "topic": payload.topic,
                "questions": cached_quiz["questions"],
                "slots_remaining": slots_remaining,
                "is_limit_reached": False
            }

        questions_list = run_gemini_quiz_generation(payload.topic, payload.num_questions)

        quiz_data = {
            "user_uid": payload.uid,
            "topic": payload.topic,
            "questions": questions_list,
            "created_at": datetime.now(timezone.utc),
            "source": "gemini_generation"
        }

        doc_ref = db.collection("generated_quizzes").document()
        doc_ref.set(quiz_data)

        db.collection("quizzes_cache").document(quiz_fingerprint).set({
            "topic": clean_topic,
            "questions": questions_list,
            "cached_at": datetime.now(timezone.utc)
        })

        return {
            "status": "success",
            "is_cached": False,
            "quiz_id": doc_ref.id,
            "topic": quiz_data["topic"],
            "questions": questions_list,
            "slots_remaining": slots_remaining,
            "is_limit_reached": False
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Quiz runtime crash: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal application error generating the quiz layout."
        )