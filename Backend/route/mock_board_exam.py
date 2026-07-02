import os
import logging
import json
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import List

from database.firebase import db
from google import genai
from google.genai import types  # Configures structured schema fields
from utils.limiters import enforce_feature_limit
from route.nurseon_ai_chat import limiter

logger = logging.getLogger("mock_board_exam")
mock_board_exam_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai_client = None
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- Pydantic Schemas for Structured AI Generation ---
class QuestionOptionSchema(BaseModel):
    A: str
    B: str
    C: str
    D: str

class QuestionSchema(BaseModel):
    id: str = Field(description="Sequential string index from '1' up to '100'")
    question: str = Field(description="Clear, realistic clinical nursing scenario context")
    options: QuestionOptionSchema
    correct_answer: str = Field(description="Single uppercase character letter: A, B, C, or D")
    rationale: str = Field(description="Clear clinical reason explaining why that answer is correct")

class UnifiedExamResponseSchema(BaseModel):
    questions: List[QuestionSchema]

# --- Request Payloads ---
class StartExamRequest(BaseModel):
    uid: str

class SubmitExamRequest(BaseModel):
    uid: str
    exam_id: str
    answers: dict  # Format: {"1": "A", "2": "C", ...}

class ResetScoreReleaseRequest(BaseModel):
    uid: str
    exam_id: str

class ResetExamEntirelyRequest(BaseModel):
    uid: str


def generate_all_100_questions() -> list:
    if not genai_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Core service unconfigured."
        )

    prompt = (
        "You are an elite Professional Nursing Board Examiner. Generate exactly 100 realistic, high-yield multiple-choice questions "
        "structured sequentially from ID '1' to '100'. NP means Nursing Practice, NP I is about Community Health Nursing, "
        "NP II is about Maternal and Child Nursing, NP III and NP IV are all about Medical-Surgical Nursing. "
        "Lastly, NP V is all about Medical-Surgical Nursing including Psychiatric Nursing concepts. "
        "Do not truncate, abbreviate, or stop short. Follow this distribution strictly:\n\n"
        "1. Questions 1 to 30: EASY difficulty. Coverage: NP I and NP II.\n"
        "2. Questions 31 to 60: MEDIUM difficulty. Coverage: NP III.\n"
        "3. Questions 61 to 100: HARD difficulty. Coverage: NP IV and NP V.\n\n"
        "Ensure every single item contains unique medical contexts with fields matching the requested layout schema."
    )

    try:
        # Enforce structured output via the modern unified genai SDK
        response = genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=UnifiedExamResponseSchema,
            ),
        )
        
        raw_json = json.loads(response.text)
        return raw_json.get("questions", [])
    except Exception as e:
        error_msg = str(e)
        logger.exception("Unified AI Exam Generation Failure")
        
        if "429" in error_msg or "quota" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="The AI generation engine is temporarily saturated. Please try again in 1 minute."
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


def get_cached_exam_questions(uid: str) -> tuple[list, str] | None:
    try:
        exams_ref = db.collection("users").document(uid).collection("mock_exams")
        latest_exam_query = exams_ref.order_by("started_at", direction="DESCENDING").limit(1).get()
        
        if len(latest_exam_query) > 0:
            latest_exam_data = latest_exam_query[0].to_dict()
            started_at = latest_exam_data.get("started_at")
            questions_data = latest_exam_data.get("questions_data")
            exam_id = latest_exam_query[0].id
            
            if started_at and questions_data:
                now = datetime.now(timezone.utc)
                cooldown_expiry = started_at + timedelta(seconds=0)
                
                if now < cooldown_expiry:
                    return questions_data, exam_id
    except Exception as e:
        logger.error(f"Error checking cached exam: {str(e)}")
    
    return None


def cache_exam_questions(uid: str, questions: list, exam_id: str) -> None:
    try:
        exams_ref = db.collection("users").document(uid).collection("mock_exams")
        exam_doc_ref = exams_ref.document(exam_id)
        
        exam_doc_ref.update({
            "questions_data": questions,
            "cached_at": datetime.now(timezone.utc)
        })
    except Exception as e:
        logger.error(f"Error caching exam questions: {str(e)}")


@mock_board_exam_router.post("/start", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def start_mock_exam(request: Request, payload: StartExamRequest):
    uid = payload.uid
    now = datetime.now(timezone.utc)
    exams_ref = db.collection("users").document(uid).collection("mock_exams")

    # --- Check for cached exam questions first ---
    cached_result = get_cached_exam_questions(uid)
    if cached_result:
        cached_questions, cached_exam_id = cached_result
        
        exam_doc = exams_ref.document()
        new_exam_id = exam_doc.id
        
        cached_exam_ref = exams_ref.document(cached_exam_id)
        cached_exam_data = cached_exam_ref.get().to_dict() or {}
        secure_keys = cached_exam_data.get("secure_answer_keys", {})
        
        exam_doc.set({
            "exam_id": new_exam_id,
            "started_at": now,
            "status": "ongoing",
            "questions_data": cached_questions,
            "secure_answer_keys": secure_keys,
            "from_cache": True
        })
        
        logger.info(f"Using cached exam questions for user {uid}")
        
        return {
            "status": "success",
            "exam_id": new_exam_id,
            "questions": cached_questions,
            "limit_remaining": 0,
            "cached": True
        }
    
    # --- Enforce Feature Limit (Strictly 1 Attempt Maximum Per 24 Hours) ---
    # This will raise HTTPException if limit is exceeded or database error occurs
    slots_remaining = enforce_feature_limit(uid, "mock_board_exam", max_limit=1)

    try:
        questions = generate_all_100_questions()
        exam_doc = exams_ref.document()
        exam_id = exam_doc.id
        
        client_questions = []
        secure_keys = {}
        
        for q in questions:
            client_questions.append({
                "id": q.get("id"),
                "question": q.get("question"),
                "options": q.get("options")
            })
            secure_keys[str(q.get("id"))] = {
                "correct": q.get("correct_answer"),
                "rationale": q.get("rationale")
            }
            
        exam_doc.set({
            "exam_id": exam_id,
            "started_at": now,
            "status": "ongoing",
            "questions_data": client_questions,
            "secure_answer_keys": secure_keys
        })
        
        cache_exam_questions(uid, client_questions, exam_id)
        logger.info(f"Generated new exam questions for user {uid}")
        
        return {
            "status": "success",
            "exam_id": exam_id,
            "questions": client_questions,
            "limit_remaining": slots_remaining,
            "cached": False
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error starting workspace session: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not initialize board workspace.")


@mock_board_exam_router.post("/reset-exam-entirely", status_code=status.HTTP_200_OK)
async def reset_exam_entirely(payload: ResetExamEntirelyRequest):
    try:
        exams_ref = db.collection("users").document(payload.uid).collection("mock_exams")
        exams = exams_ref.get()
        batch = db.batch()
        
        for exam_doc in exams:
            batch.delete(exam_doc.reference)
        
        batch.commit()
        
        return {
            "status": "success",
            "message": "All exam data has been reset. You can now start a new exam."
        }
    except Exception as e:
        logger.error(f"Full exam reset failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset exam data.")


@mock_board_exam_router.post("/reset-score-release", status_code=status.HTTP_200_OK)
async def reset_score_release(payload: ResetScoreReleaseRequest):
    try:
        exam_doc_ref = db.collection("users").document(payload.uid).collection("mock_exams").document(payload.exam_id)
        doc = exam_doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Exam not found.")
        
        immediate_release = datetime.now(timezone.utc)
        exam_doc_ref.update({
            "score_release_at": immediate_release
        })
        
        return {
            "status": "success",
            "message": "Score countdown reset. Results are now available.",
            "release_at": immediate_release.isoformat()
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Score reset failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset score countdown.")


@mock_board_exam_router.post("/submit", status_code=status.HTTP_200_OK)
async def submit_mock_exam(payload: SubmitExamRequest):
    try:
        exam_doc_ref = db.collection("users").document(payload.uid).collection("mock_exams").document(payload.exam_id)
        doc = exam_doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Target exam snapshot missing.")
            
        exam_data = doc.to_dict() or {}
        secure_keys = exam_data.get("secure_answer_keys", {})
        
        score = 0
        total_items = len(secure_keys)
        breakdown = {}
        
        for q_id, keys in secure_keys.items():
            user_ans = payload.answers.get(q_id)
            correct_ans = keys.get("correct")
            is_correct = user_ans == correct_ans if user_ans else False
            
            if is_correct:
                score += 1
                
            breakdown[q_id] = {
                "user_answer": user_ans if user_ans else "Unanswered (Locked Out)",
                "correct_answer": correct_ans,
                "rationale": keys.get("rationale"),
                "is_correct": is_correct
            }
            
        submission_time = datetime.now(timezone.utc)
        release_time = submission_time + timedelta(seconds=0)
        
        exam_doc_ref.update({
            "status": "submitted",
            "user_submissions": payload.answers,
            "submitted_at": submission_time,
            "score_release_at": release_time,
            "calculated_score": score,
            "total_items": total_items,
            "evaluation_breakdown": breakdown
        })
        
        return {
            "status": "success",
            "release_at": release_time.isoformat()
        }
    except Exception as e:
        logger.error(f"Submission pipeline crashed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to secure your exam choices.")