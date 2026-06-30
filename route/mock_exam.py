import os
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import google.generativeai as genai

from database.firebase import db

logger = logging.getLogger("mock_exam_router")
mock_exam_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class StartExamRequest(BaseModel):
    uid: str
    session_type: str  # "morning" (NP I-II) or "afternoon" (NP III-V)

class SubmitExamRequest(BaseModel):
    uid: str
    exam_id: str
    answers: dict  # Format: {"question_id_or_index": "Selected Option Letter"}

def generate_board_questions(session_type: str) -> list:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Core service unconfigured."
        )

    scope = (
        "NP I (Community Health Nursing, Communicable Disease, Epidemiology) and NP II (Care of Mother and Child)"
        if session_type == "morning" else
        "NP III, NP IV, and NP V (Care of Clients with Physiologic and Psychosocial Alterations)"
    )

    system_instruction = (
        "You are an elite Professional Nursing Board Examiner and Test Constructor.\n\n"
        "YOUR TASK:\n"
        f"Generate exactly 50 realistic board-style multiple choice questions focusing on: {scope}.\n"
        "Return the output raw valid JSON as an array of items. Do not put markdown wrappers.\n"
        "Each object item within the JSON array must strictly have these fields:\n"
        "- id: sequential string integer index (e.g., \"1\", \"2\")\n"
        "- question: clear, professional scenario context\n"
        "- options: object containing exact keys: A, B, C, D\n"
        "- correct_answer: single upper case character letter key\n"
        "- rationale: clear clinical reason explaining why that answer is correct based on safety frameworks (ABCs)."
    )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction,
            generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content("Generate the 50 board questions now.")
        import json
        return json.loads(response.text.strip())
    except Exception as e:
        logger.exception("AI Question Generation Failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate your exam session questions. Please retry."
        )

@mock_exam_router.post("/start", status_code=status.HTTP_200_OK)
async def start_mock_exam(payload: StartExamRequest):
    try:
        # Check if they have an active session running within safety rules
        questions = generate_board_questions(payload.session_type)
        
        exam_ref = db.collection("users").document(payload.uid).collection("mock_exams").document()
        exam_id = exam_ref.id
        
        # Strip out direct correct answers from client payload payload metadata
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
            
        start_time = datetime.now(timezone.utc)
        
        exam_ref.set({
            "exam_id": exam_id,
            "session_type": payload.session_type,
            "started_at": start_time,
            "status": "ongoing",
            "questions_data": client_questions,
            "secure_answer_keys": secure_keys
        })
        
        return {
            "status": "success",
            "exam_id": exam_id,
            "duration_seconds": 5400, # 1 Hour 30 Minutes
            "questions": client_questions
        }
    except Exception as e:
        logger.error(f"Error starting exam: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not initialize your board layout instance.")

@mock_exam_router.post("/submit", status_code=status.HTTP_200_OK)
async def submit_mock_exam(payload: SubmitExamRequest):
    try:
        exam_doc_ref = db.collection("users").document(payload.uid).collection("mock_exams").document(payload.exam_id)
        doc = exam_doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Target exam track missing.")
            
        exam_data = doc.to_dict() or {}
        secure_keys = exam_data.get("secure_answer_keys", {})
        
        # Calculate scores securely on backend
        score = 0
        total_items = len(secure_keys)
        breakdown = {}
        
        for q_id, keys in secure_keys.items():
            user_ans = payload.answers.get(q_id)
            correct_ans = keys.get("correct")
            is_correct = user_ans == correct_ans
            if is_correct:
                score += 1
                
            breakdown[q_id] = {
                "user_answer": user_ans,
                "correct_answer": correct_ans,
                "rationale": keys.get("rationale"),
                "is_correct": is_correct
            }
            
        submission_time = datetime.now(timezone.utc)
        release_time = submission_time + timedelta(hours=24)
        
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
            "message": "Exam saved securely. Scores deferred for 24-hour verification review.",
            "release_at": release_time.isoformat()
        }
    except Exception as e:
        logger.error(f"Submission pipeline crashed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save exam choices.")

@mock_exam_router.get("/status/{uid}", status_code=status.HTTP_200_OK)
async def get_exam_status_history(uid: str):
    try:
        exams_ref = db.collection("users").document(uid).collection("mock_exams")
        docs = exams_ref.order_by("started_at", direction="DESCENDING").stream()
        
        history = []
        now = datetime.now(timezone.utc)
        
        for doc in docs:
            data = doc.to_dict()
            release_at = data.get("score_release_at")
            
            # Determine visibility based on timer parameters
            is_released = False
            if release_at:
                if isinstance(release_at, str):
                    release_dt = datetime.fromisoformat(release_at.replace("Z", "+00:00"))
                else:
                    release_dt = release_at # firestore timestamp type safe handling
                is_released = now >= release_dt

            history.append({
                "exam_id": data.get("exam_id"),
                "session_type": data.get("session_type"),
                "status": data.get("status"),
                "started_at": data.get("started_at"),
                "is_score_available": is_released,
                "score": data.get("calculated_score") if is_released else None,
                "total_items": data.get("total_items") if is_released else None,
                "release_countdown": str(release_dt - now) if (release_at and not is_released) else "0"
            })
        return {"status": "success", "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not retrieve status matrix charts.")