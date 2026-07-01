import os
import logging
import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import List

from database.firebase import db
from google import genai

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
    answers: dict  # Format: {"1": "A", "2": "C", ...} Can accept partials, unshaded counts as blank.

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

    # Hardened prompt instructions to avoid early syntax truncation or missing keys
    prompt = (
        "You are an elite Professional Nursing Board Examiner. Generate exactly 100 realistic, high-yield multiple-choice questions "
        "structured sequentially from ID '1' to '100'. NP means Nursing Practice, NP I is about Community Health Nursing, NP II is about Maternal and Child Nursing, NP III and NP IV are all about Medical-Surgical Nursing. Lastly, NP V is all about Medical-Surgical Nursing including Psychiatric Nursing concepts. Do not truncate, abbreviate, or stop short. Follow this distribution strictly:\n\n"
        "1. Questions 1 to 30: EASY difficulty. Coverage: NP I and NP II.\n"
        "2. Questions 31 to 60: MEDIUM difficulty. Coverage: NP III.\n"
        "3. Questions 61 to 100: HARD difficulty. Coverage: NP IV and NP V.\n\n"
        "Ensure every single item contains unique medical contexts with fields: id, question, options (A, B, C, D), correct_answer, and rationale.\n\n"
        "Return ONLY valid JSON with this structure: {\"questions\": [{\"id\": \"1\", \"question\": \"...\", \"options\": {\"A\": \"...\", \"B\": \"...\", \"C\": \"...\", \"D\": \"...\"}, \"correct_answer\": \"A\", \"rationale\": \"...\"}]}"
    )

    try:
        response = genai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        # Extract JSON from response
        response_text = response.text.strip()
        # Try to parse the JSON
        raw_json = json.loads(response_text)
        return raw_json.get("questions", [])
    except Exception as e:
        logger.exception("Unified AI Exam Generation Failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compile target exam items: {str(e)}"
        )


def get_cached_exam_questions(uid: str) -> tuple[list, str] | None:
    """Check if there's a cached exam for this user that's still valid (within 24 hours)"""
    try:
        exams_ref = db.collection("users").document(uid).collection("unified_board_exams")
        latest_exam_query = exams_ref.order_by("started_at", direction="DESCENDING").limit(1).get()
        
        if len(latest_exam_query) > 0:
            latest_exam_data = latest_exam_query[0].to_dict()
            started_at = latest_exam_data.get("started_at")
            questions_data = latest_exam_data.get("questions_data")
            exam_id = latest_exam_query[0].id
            
            if started_at and questions_data:
                # Check if exam is still within 24-hour window
                now = datetime.now(timezone.utc)
                cooldown_expiry = started_at + timedelta(hours=24)
                
                if now < cooldown_expiry:
                    return questions_data, exam_id
    except Exception as e:
        logger.error(f"Error checking cached exam: {str(e)}")
    
    return None


def cache_exam_questions(uid: str, questions: list, exam_id: str) -> None:
    """Cache generated questions to database for reuse"""
    try:
        exams_ref = db.collection("users").document(uid).collection("unified_board_exams")
        exam_doc_ref = exams_ref.document(exam_id)
        
        # Update the document with questions_data if not already present
        exam_doc_ref.update({
            "questions_data": questions,
            "cached_at": datetime.now(timezone.utc)
        })
    except Exception as e:
        logger.error(f"Error caching exam questions: {str(e)}")


@mock_board_exam_router.post("/start", status_code=status.HTTP_200_OK)
async def start_mock_exam(request: Request, payload: StartExamRequest):
    # Rate limit: 1 exam generation per hour per IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Simple in-memory rate limiting check
    current_time = datetime.now(timezone.utc)
    rate_limit_key = f"rate_limit:{client_ip}"
    
    # Check rate limit (1 hour cooldown)
    try:
        last_request_str = db.collection("rate_limits").document(rate_limit_key).get()
        if last_request_str.exists:
            last_request_data = last_request_str.to_dict()
            last_request_time = last_request_data.get("timestamp")
            
            if last_request_time:
                time_since_last = (current_time - last_request_time.replace(tzinfo=timezone.utc)).total_seconds()
                if time_since_last < 3600:  # Less than 1 hour
                    minutes_remaining = int((3600 - time_since_last) / 60)
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"You are generating exams too quickly. Please wait {minutes_remaining} minutes before trying again.",
                        headers={"Retry-After": str(3600 - int(time_since_last))}
                    )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limit check error: {str(e)}")
    
    # Record this request
    try:
        db.collection("rate_limits").document(rate_limit_key).set({
            "timestamp": current_time,
            "ip": client_ip
        })
    except Exception as e:
        logger.error(f"Rate limit recording error: {str(e)}")
    try:
        uid = payload.uid
        exams_ref = db.collection("users").document(uid).collection("unified_board_exams")
        now = datetime.now(timezone.utc)
        
        # --- Check for cached exam questions first ---
        cached_result = get_cached_exam_questions(uid)
        if cached_result:
            cached_questions, cached_exam_id = cached_result
            
            # Create new exam session with cached questions
            exam_doc = exams_ref.document()
            new_exam_id = exam_doc.id
            
            # Prepare secure keys (we need to get them from the cached exam)
            cached_exam_ref = db.collection("users").document(uid).collection("unified_board_exams").document(cached_exam_id)
            cached_exam_data = cached_exam_ref.get().to_dict()
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
                "slots_remaining": 0,
                "cached": True
            }
        
        # --- Rolling 24-Hour Feature Lockout Guard ---
        latest_exam_query = exams_ref.order_by("started_at", direction="DESCENDING").limit(1).get()
        
        if len(latest_exam_query) > 0:
            latest_exam_data = latest_exam_query[0].to_dict()
            started_at = latest_exam_data.get("started_at")
            
            if started_at:
                cooldown_expiry = started_at + timedelta(hours=24)
                if now < cooldown_expiry:
                    time_remaining = cooldown_expiry - now
                    hours_left = int(time_remaining.total_seconds() // 3600)
                    minutes_left = int((time_remaining.total_seconds() % 3600) // 60)
                    
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Feature Locked: You can only use the Mock Board Exam feature once every 24 hours. Please return in {hours_left}h {minutes_left}m.",
                        headers={"X-Slots-Remaining": "0"}
                    )

        # Generate complete 100 question matrix if cooldown has passed
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
        
        # Cache the questions for future use
        cache_exam_questions(uid, client_questions, exam_id)
        
        logger.info(f"Generated new exam questions for user {uid}")
        
        return {
            "status": "success",
            "exam_id": exam_id,
            "questions": client_questions,
            "slots_remaining": 0,
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
        exams_ref = db.collection("users").document(payload.uid).collection("unified_board_exams")
        
        # Delete all exam documents for this user
        exams = exams_ref.get()
        batch = db.batch()
        
        for exam_doc in exams:
            batch.delete(exam_doc.reference)
        
        batch.commit()
        
        return {
            "status": "success",
            "message": "All exam data has been reset. You can now start a new exam."
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Full exam reset failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset exam data.")

@mock_board_exam_router.post("/reset-score-release", status_code=status.HTTP_200_OK)
async def reset_score_release(payload: ResetScoreReleaseRequest):
    try:
        exam_doc_ref = db.collection("users").document(payload.uid).collection("unified_board_exams").document(payload.exam_id)
        doc = exam_doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Exam not found.")
        
        # Reset score release to now (immediate access)
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
        exam_doc_ref = db.collection("users").document(payload.uid).collection("unified_board_exams").document(payload.exam_id)
        doc = exam_doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Target exam snapshot missing.")
            
        exam_data = doc.to_dict() or {}
        secure_keys = exam_data.get("secure_answer_keys", {})
        
        score = 0
        total_items = len(secure_keys)  # Will be exactly 100
        breakdown = {}
        
        # Iterates through all 100 securely stored correct answers
        for q_id, keys in secure_keys.items():
            user_ans = payload.answers.get(q_id)  # Returns None if frontend skipped it or ran out of time
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
        
        # Saves evaluation metrics for the entire unified compilation
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