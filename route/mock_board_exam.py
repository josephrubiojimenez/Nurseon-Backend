import os
import logging
import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List

from database.firebase import db
import google.generativeai as genai

logger = logging.getLogger("mock_board_exam")
mock_board_exam_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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


def generate_all_100_questions() -> list:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Core service unconfigured."
        )

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": UnifiedExamResponseSchema
        }
    )

    # Hardened prompt instructions to avoid early syntax truncation or missing keys
    prompt = (
        "You are an elite Professional Nursing Board Examiner. Generate exactly 100 realistic, high-yield multiple-choice questions "
        "structured sequentially from ID '1' to '100'. NP means Nursing Practice, NP I is about Community Health Nursing, NP II is about Maternal and Child Nursing, NP III and NP IV are all about Medical-Surgical Nursing. Lastly, NP V is all about Medical-Surgical Nursing including Psychiatric Nursing concepts. Do not truncate, abbreviate, or stop short. Follow this distribution strictly:\n\n"
        "1. Questions 1 to 30: EASY difficulty. Coverage: NP I and NP II.\n"
        "2. Questions 31 to 60: MEDIUM difficulty. Coverage: NP III.\n"
        "3. Questions 61 to 100: HARD difficulty. Coverage: NP IV and NP V.\n\n"
        "Ensure every single item contains unique medical contexts with fields: id, question, options (A, B, C, D), correct_answer, and rationale."
    )

    try:
        response = model.generate_content(prompt)
        raw_json = json.loads(response.text.strip())
        return raw_json.get("questions", [])
    except Exception as e:
        logger.exception("Unified AI Exam Generation Failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compile target exam items: {str(e)}"
        )


@mock_board_exam_router.post("/start", status_code=status.HTTP_200_OK)
async def start_mock_exam(payload: StartExamRequest):
    try:
        exams_ref = db.collection("users").document(payload.uid).collection("unified_board_exams")
        
        # --- Rolling 24-Hour Feature Lockout Guard ---
        latest_exam_query = exams_ref.order_by("started_at", direction="DESCENDING").limit(1).get()
        now = datetime.now(timezone.utc)
        
        if len(latest_exam_query) > 0:
            latest_exam_data = latest_exam_query[0].to_dict()
            started_at = latest_exam_data.get("started_at")
            
            if started_at:
                cooldown_expiry = started_at + timedelta(seconds=0)  # hours 24
                if now < cooldown_expiry:
                    time_remaining = cooldown_expiry - now
                    hours_left = int(time_remaining.total_seconds() // 3600)
                    minutes_left = int((time_remaining.total_seconds() % 3600) // 60)
                    
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Feature Locked: You can only use the Mock Board Exam feature once every 24 hours. Please return in {hours_left}h {minutes_left}m."
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
        
        return {
            "status": "success",
            "exam_id": exam_id,
            "questions": client_questions
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error starting workspace session: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not initialize board workspace.")


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
        release_time = submission_time + timedelta(hours=24)
        
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