import os
import logging
import json
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import google.generativeai as genai

from database.firebase import db
from utils.limiters import enforce_feature_limit

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
    """Schema for an individual quiz question."""
    question: str
    options: list[str]
    correct_answer: str
    rationale: str

class QuizStructure(BaseModel):
    """Root container model for Gemini Structured Output."""
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
        # Request native JSON output structurally guaranteed by the Pydantic schema
        response = model.generate_content(
            f"System: {system_prompt}\n\nTopic: {topic}",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=QuizStructure
            )
        )
        
        # Parse the reliable JSON structure safely
        quiz_data = json.loads(response.text)
        return quiz_data["questions"]

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Gemini Quiz Parsing/API Failure: {error_msg}", exc_info=True)
        
        # Provide specific error messages based on the error
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

# ==========================================
# 3. HELPER FUNCTION FOR USER USAGE
# ==========================================

def get_user_quiz_usage(uid: str) -> dict:
    """Get the current quiz usage for a user."""
    try:
        usage_doc = db.collection("user_usage").document(uid).get()
        if usage_doc.exists:
            usage_data = usage_doc.to_dict()
            quiz_count = usage_data.get("quiz", {}).get("count", 0)
            slots_remaining = max(0, 5 - quiz_count)
            return {
                "slots_remaining": get_user_quiz_usage(payload.uid)["slots_remaining"],
                "total_used": quiz_count,
                "max_limit": 5,
                "is_limit_reached": slots_remaining <= 0
            }
        else:
            return {
                "slots_remaining": 5,
                "total_used": 0,
                "max_limit": 5,
                "is_limit_reached": False
            }
    except Exception as e:
        logger.error(f"Failed to get user usage for {uid}: {str(e)}")
        # Return default values if there's an error
        return {
            "slots_remaining": 5,
            "total_used": 0,
            "max_limit": 5,
            "is_limit_reached": False
        }

# ==========================================
# 4. ROUTER ENDPOINTS
# ==========================================

@quiz_router.get("/usage/{uid}")
async def get_user_usage(uid: str):
    """Get the current quiz usage and limits for a user."""
    try:
        usage_info = get_user_quiz_usage(uid)
        return {
            "status": "success",
            **usage_info
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
        # This will raise HTTPException if limit is exceeded
        slots_remaining = enforce_feature_limit(payload.uid, "quiz", max_limit=5)
        is_limit_reached = False
    except HTTPException as http_err:
        # If the limit is exceeded, get the remaining slots
        if http_err.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            usage_info = get_user_quiz_usage(payload.uid)
            
            # Return a custom response with the remaining slots
            return {
                "status": "error",
                "detail": http_err.detail,
                "slots_remaining": usage_info["slots_remaining"],
                "is_limit_reached": True,
                "total_used": usage_info["total_used"],
                "max_limit": usage_info["max_limit"]
            }
        raise http_err

    # ==========================================
    # 2. PROCEED WITH QUIZ GENERATION
    # ==========================================
    try:
        # CREATE A UNIQUE CACHE FINGERPRINT
        clean_topic = payload.topic.strip().lower()
        quiz_fingerprint = hashlib.md5(f"{clean_topic}_{payload.num_questions}".encode('utf-8')).hexdigest()

        # ATTEMPT CACHE QUERY LOOKUP
        cache_doc = db.collection("quizzes_cache").document(quiz_fingerprint).get()

        if cache_doc.exists:
            cached_quiz = cache_doc.to_dict()
            logger.info(f"Quiz Cache Hit! Serving topic: '{payload.topic}' with {payload.num_questions} items.")

            # Record this event in the user's specific generation history
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

        # CACHE MISS -> CALL GEMINI AI
        questions_list = run_gemini_quiz_generation(payload.topic, payload.num_questions)

        quiz_data = {
            "user_uid": payload.uid,
            "topic": payload.topic,
            "questions": questions_list,
            "created_at": datetime.now(timezone.utc),
            "source": "gemini_generation"
        }

        # Save to user collection history
        doc_ref = db.collection("generated_quizzes").document()
        doc_ref.set(quiz_data)

        # Write data to global cache so future matching requests bypass Gemini
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