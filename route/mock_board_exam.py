import os
import logging
import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from database.firebase import db
from google import genai
from google.genai import types
from utils.limiters import enforce_feature_limit, check_rate_limit_status
from route.nurseon_ai_chat import limiter

logger = logging.getLogger("mock_board_exam")
mock_board_exam_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai_client = None
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# CONSTANTS
# ==========================================

PHASE_CONFIG = {
    1: {"name": "easy", "start": 0, "end": 30, "label": "Easy (NP I & II)", "duration": 5400},  # 90 minutes
    2: {"name": "medium", "start": 30, "end": 60, "label": "Medium (NP III)", "duration": 5400},
    3: {"name": "hard", "start": 60, "end": 100, "label": "Hard (NP IV & V)", "duration": 5400}
}

BREAK_DURATIONS = {
    1: 600,   # 10 minutes after phase 1
    2: 1200,  # 20 minutes after phase 2
    3: 0      # No break after phase 3
}

PASSING_SCORE = 75

# ==========================================
# SCHEMAS
# ==========================================

class QuestionOptionSchema(BaseModel):
    A: str
    B: str
    C: str
    D: str

class QuestionSchema(BaseModel):
    id: str
    question: str
    options: QuestionOptionSchema
    correct_answer: str
    rationale: str

class UnifiedExamResponseSchema(BaseModel):
    questions: List[QuestionSchema]

class StartExamRequest(BaseModel):
    uid: str

class SubmitExamRequest(BaseModel):
    uid: str
    exam_id: str
    answers: Dict[str, str]

class SubmitAnswerRequest(BaseModel):
    uid: str
    exam_id: str
    question_index: int
    answer: str

class AdvancePhaseRequest(BaseModel):
    uid: str
    exam_id: str

# ==========================================
# HELPERS
# ==========================================

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


def get_phase_for_question_index(index: int) -> int:
    """Determine which phase a question index belongs to."""
    if index < 30:
        return 1
    elif index < 60:
        return 2
    else:
        return 3


def get_phase_name(phase: int) -> str:
    """Get the phase name."""
    return PHASE_CONFIG.get(phase, {}).get("name", "unknown")


def create_exam_session(uid: str, questions: list, exam_id: str) -> str:
    """Create a new exam session in Firestore."""
    now = datetime.now(timezone.utc)
    
    session_data = {
        "uid": uid,
        "feature": "mock_board_exam",
        "window_start": now,
        "status": "in_progress",
        "current_phase": 1,
        "current_question_index": 0,
        "phase_start_time": now,
        "phase_end_time": now + timedelta(seconds=5400),  # 90 minutes
        "score": {
            "correct": 0,
            "total": 100,
            "percentage": 0
        },
        "phase_status": {
            "easy": "in_progress",
            "medium": "locked",
            "hard": "locked"
        },
        "break": {
            "active": False,
            "break_end_time": None
        },
        "answers": {
            "easy": [],
            "medium": [],
            "hard": []
        },
        "questions_data": questions,
        "secure_answer_keys": {},
        "weak_areas": [],
        "recommendation": "",
        "created_at": now,
        "updated_at": now,
        "completed_at": None
    }
    
    # Store secure answer keys separately for grading
    secure_keys = {}
    for q in questions:
        secure_keys[str(q.get("id"))] = {
            "correct": q.get("correct_answer"),
            "rationale": q.get("rationale")
        }
    session_data["secure_answer_keys"] = secure_keys
    
    # Store the session
    session_ref = db.collection("exam_sessions").document(exam_id)
    session_ref.set(session_data)
    
    return exam_id


def get_exam_session(exam_id: str) -> Optional[Dict]:
    """Get an exam session from Firestore."""
    try:
        session_ref = db.collection("exam_sessions").document(exam_id)
        doc = session_ref.get()
        if doc.exists:
            return {"id": doc.id, **doc.to_dict()}
        return None
    except Exception as e:
        logger.error(f"Error getting exam session {exam_id}: {str(e)}")
        return None


def update_exam_session(exam_id: str, updates: Dict) -> bool:
    """Update an exam session in Firestore."""
    try:
        updates["updated_at"] = datetime.now(timezone.utc)
        session_ref = db.collection("exam_sessions").document(exam_id)
        session_ref.update(updates)
        return True
    except Exception as e:
        logger.error(f"Error updating exam session {exam_id}: {str(e)}")
        return False


def calculate_score(exam_data: Dict) -> Dict:
    """Calculate the score from exam answers."""
    answers = exam_data.get("answers", {})
    secure_keys = exam_data.get("secure_answer_keys", {})
    
    correct = 0
    total = 100
    phase_scores = {"easy": {"correct": 0, "total": 30, "wrong": 0}, 
                    "medium": {"correct": 0, "total": 30, "wrong": 0}, 
                    "hard": {"correct": 0, "total": 40, "wrong": 0}}
    
    # Flatten all answers
    all_answers = []
    for phase in ["easy", "medium", "hard"]:
        all_answers.extend(answers.get(phase, []))
    
    for i, answer in enumerate(all_answers):
        q_id = str(i + 1)
        if q_id in secure_keys:
            correct_answer = secure_keys[q_id].get("correct")
            is_correct = answer == correct_answer if answer else False
            
            if is_correct:
                correct += 1
            else:
                # Track wrong answers for weak areas
                if i < 30:
                    phase = "easy"
                elif i < 60:
                    phase = "medium"
                else:
                    phase = "hard"
                phase_scores[phase]["wrong"] += 1
            
            # Track phase scores
            if i < 30:
                phase = "easy"
            elif i < 60:
                phase = "medium"
            else:
                phase = "hard"
            
            if is_correct:
                phase_scores[phase]["correct"] += 1
    
    percentage = round((correct / total) * 100)
    
    return {
        "correct": correct,
        "total": total,
        "percentage": percentage,
        "phase_scores": phase_scores
    }


def process_weak_areas(exam_data: Dict) -> Dict:
    """Process weak areas from exam results."""
    try:
        secure_keys = exam_data.get("secure_answer_keys", {})
        answers = exam_data.get("answers", {})
        
        # Flatten answers with their phase
        all_answers = []
        for phase in ["easy", "medium", "hard"]:
            phase_answers = answers.get(phase, [])
            for idx, answer in enumerate(phase_answers):
                q_index = 0
                if phase == "easy":
                    q_index = idx
                elif phase == "medium":
                    q_index = 30 + idx
                else:
                    q_index = 60 + idx
                all_answers.append({
                    "index": q_index,
                    "answer": answer,
                    "phase": phase
                })
        
        weak_subjects = {}
        for item in all_answers:
            q_id = str(item["index"] + 1)
            if q_id in secure_keys and item["answer"]:
                correct_answer = secure_keys[q_id].get("correct")
                if item["answer"] != correct_answer:
                    # Extract subject from question/rationale
                    rationale = secure_keys[q_id].get("rationale", "")
                    # Simple subject extraction
                    subjects = ["Pharmacology", "Medical-Surgical", "Maternal & Child", 
                               "Community Health", "Psychiatric", "Nursing Care"]
                    found_subject = "General Knowledge"
                    for subject in subjects:
                        if subject.lower() in rationale.lower():
                            found_subject = subject
                            break
                    
                    if found_subject not in weak_subjects:
                        weak_subjects[found_subject] = 0
                    weak_subjects[found_subject] += 1
        
        # Create weakness list with priority
        weakness_list = []
        total_wrong = sum(weak_subjects.values()) or 1
        for subject, count in weak_subjects.items():
            percent = round((count / total_wrong) * 100)
            if percent >= 30:
                priority = "critical"
            elif percent >= 15:
                priority = "medium"
            else:
                priority = "low"
            
            weakness_list.append({
                "subject": subject,
                "percent": percent,
                "priority": priority,
                "count": count
            })
        
        # Sort by priority
        priority_order = {"critical": 0, "medium": 1, "low": 2}
        weakness_list.sort(key=lambda x: priority_order.get(x["priority"], 3))
        
        # Generate recommendation
        recommendation = generate_recommendation(weakness_list)
        
        return {
            "weak_areas": weakness_list[:5],  # Top 5
            "recommendation": recommendation
        }
    except Exception as e:
        logger.error(f"Error processing weak areas: {str(e)}")
        return {
            "weak_areas": [],
            "recommendation": "Complete more exams to get personalized insights."
        }


def generate_recommendation(weaknesses: List[Dict]) -> str:
    """Generate a personalized recommendation based on weak areas."""
    if not weaknesses:
        return "Excellent performance! Continue reviewing all topics to maintain your knowledge."
    
    priority = weaknesses[0]
    
    if priority["priority"] == "critical":
        return f"Focus on {priority['subject']} ({priority['percent']}% of your mistakes). Review clinical concepts and Smart Notes in this area before your next exam."
    elif len(weaknesses) >= 2:
        subjects = " and ".join([w["subject"] for w in weaknesses[:2]])
        return f"Priority areas: {subjects}. These topics need more attention. Review the clinical concepts and rationales for missed questions."
    else:
        return f"Consider reviewing {weaknesses[0]['subject']} to strengthen your clinical knowledge."


def get_existing_session(uid: str) -> Optional[Dict]:
    """Check if user has an existing active session."""
    try:
        sessions_ref = db.collection("exam_sessions")
        query = sessions_ref.where("uid", "==", uid).where("status", "in", ["in_progress", "break"]).limit(1).stream()
        
        for doc in query:
            return {"id": doc.id, **doc.to_dict()}
        return None
    except Exception as e:
        logger.error(f"Error checking existing session: {str(e)}")
        return None


def get_completed_session(uid: str) -> Optional[Dict]:
    """Check if user has a completed session within the last 24 hours."""
    try:
        sessions_ref = db.collection("exam_sessions")
        query = sessions_ref.where("uid", "==", uid).where("status", "==", "completed").limit(1).stream()
        
        for doc in query:
            data = doc.to_dict()
            completed_at = data.get("completed_at")
            if completed_at:
                completed_at = completed_at if completed_at.tzinfo else completed_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - completed_at < timedelta(days=1):
                    return {"id": doc.id, **data}
        return None
    except Exception as e:
        logger.error(f"Error checking completed session: {str(e)}")
        return None

# ==========================================
# API ENDPOINTS
# ==========================================

@mock_board_exam_router.get("/status/{uid}", status_code=status.HTTP_200_OK)
async def get_exam_status(uid: str):
    """Get the current exam status for a user."""
    try:
        # Check for existing active session
        existing = get_existing_session(uid)
        
        if existing:
            # Check if phase timer expired
            phase_end_time = existing.get("phase_end_time")
            if phase_end_time and existing.get("status") == "in_progress":
                phase_end_time = phase_end_time if phase_end_time.tzinfo else phase_end_time.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > phase_end_time:
                    # Phase expired - auto-advance
                    await auto_advance_phase(uid, existing["id"])
                    # Re-fetch the updated session
                    existing = get_existing_session(uid)
                    if not existing:
                        return {"status": "success", "exam_status": "available"}
            
            return {
                "status": "success",
                "exam_id": existing["id"],
                "exam_status": existing["status"],
                "current_phase": existing.get("current_phase", 1),
                "current_question_index": existing.get("current_question_index", 0),
                "phase_status": existing.get("phase_status", {}),
                "break_active": existing.get("break", {}).get("active", False),
                "break_end_time": existing.get("break", {}).get("break_end_time"),
                "window_start": existing.get("window_start"),
                "score": existing.get("score", {"correct": 0, "total": 100, "percentage": 0}),
                "weak_areas": existing.get("weak_areas", []),
                "recommendation": existing.get("recommendation", "")
            }
        
        # Check for completed session (locked state)
        completed = get_completed_session(uid)
        if completed:
            return {
                "status": "success",
                "exam_id": completed["id"],
                "exam_status": "locked",
                "current_phase": completed.get("current_phase", 3),
                "current_question_index": completed.get("current_question_index", 100),
                "phase_status": completed.get("phase_status", {}),
                "break_active": False,
                "break_end_time": None,
                "window_start": completed.get("window_start"),
                "score": completed.get("score", {"correct": 0, "total": 100, "percentage": 0}),
                "weak_areas": completed.get("weak_areas", []),
                "recommendation": completed.get("recommendation", "")
            }
        
        # Check if limit is reached
        limit_status = check_rate_limit_status(uid, "mock_board_exam", max_limit=1)
        if not limit_status["available"]:
            return {
                "status": "success",
                "exam_status": "locked",
                "reset_at": limit_status["reset_at"],
                "slots_remaining": limit_status["remaining"]
            }
        
        return {
            "status": "success",
            "exam_status": "available",
            "slots_remaining": limit_status["remaining"]
        }
        
    except Exception as e:
        logger.error(f"Error getting exam status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get exam status")


async def auto_advance_phase(uid: str, exam_id: str):
    """Auto-advance phase when timer expires."""
    try:
        exam_data = get_exam_session(exam_id)
        if not exam_data:
            return
        
        current_phase = exam_data.get("current_phase", 1)
        phase_name = get_phase_name(current_phase)
        
        # Mark current phase as completed
        phase_status = exam_data.get("phase_status", {})
        phase_status[phase_name] = "completed"
        
        # Check if this is the last phase
        if current_phase >= 3:
            # Exam is complete
            update_exam_session(exam_id, {
                "phase_status": phase_status,
                "status": "completed",
                "completed_at": datetime.now(timezone.utc)
            })
            
            # Calculate score
            updated_exam = get_exam_session(exam_id)
            score_data = calculate_score(updated_exam)
            
            # Update score
            update_exam_session(exam_id, {"score": score_data})
            
            # Process weak areas
            weak_analysis = process_weak_areas(updated_exam)
            update_exam_session(exam_id, {
                "weak_areas": weak_analysis["weak_areas"],
                "recommendation": weak_analysis["recommendation"]
            })
            return
        
        # Start break
        break_duration = BREAK_DURATIONS.get(current_phase, 600)
        break_end_time = datetime.now(timezone.utc) + timedelta(seconds=break_duration)
        
        update_exam_session(exam_id, {
            "phase_status": phase_status,
            "status": "break",
            "break": {
                "active": True,
                "break_end_time": break_end_time
            }
        })
    except Exception as e:
        logger.error(f"Error auto-advancing phase: {str(e)}")


@mock_board_exam_router.post("/start", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def start_mock_exam(request: Request, payload: StartExamRequest):
    """Start a new mock exam session."""
    uid = payload.uid
    
    # Check if user already has an active session
    existing = get_existing_session(uid)
    if existing:
        # Return existing session
        return {
            "status": "success",
            "exam_id": existing["id"],
            "message": "Continuing existing exam",
            "exam_status": existing["status"],
            "current_phase": existing.get("current_phase", 1),
            "current_question_index": existing.get("current_question_index", 0)
        }
    
    # Enforce limit (1 attempt per 24-hour window)
    try:
        slots_remaining = enforce_feature_limit(uid, "mock_board_exam", max_limit=1)
    except HTTPException as e:
        if e.status_code == 429:
            limit_status = check_rate_limit_status(uid, "mock_board_exam", max_limit=1)
            reset_msg = f" at {limit_status['reset_at']}" if limit_status.get("reset_at") else " tomorrow"
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Mock Board Exam limit reached. You can try again{reset_msg}."
            )
        raise e
    
    # Generate questions
    try:
        questions = generate_all_100_questions()
        exam_id = f"exam_{uid}_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Create session
        create_exam_session(uid, questions, exam_id)
        
        # Prepare client-side questions (without correct answers)
        client_questions = []
        for q in questions:
            client_questions.append({
                "id": q.get("id"),
                "question": q.get("question"),
                "options": q.get("options")
            })
        
        return {
            "status": "success",
            "exam_id": exam_id,
            "questions": client_questions,
            "limit_remaining": slots_remaining,
            "exam_status": "in_progress"
        }
    except Exception as e:
        logger.error(f"Error starting exam: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start exam")


@mock_board_exam_router.post("/submit-answer", status_code=status.HTTP_200_OK)
async def submit_answer(payload: SubmitAnswerRequest):
    """Submit a single answer for the exam."""
    uid = payload.uid
    exam_id = payload.exam_id
    question_index = payload.question_index
    answer = payload.answer
    
    if not all([uid, exam_id, question_index is not None, answer]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Get exam session
    exam_data = get_exam_session(exam_id)
    if not exam_data:
        raise HTTPException(status_code=404, detail="Exam session not found")
    
    if exam_data.get("uid") != uid:
        raise HTTPException(status_code=403, detail="Unauthorized access to exam")
    
    # Determine phase
    phase = get_phase_for_question_index(question_index)
    phase_name = get_phase_name(phase)
    
    # Update answers
    answers = exam_data.get("answers", {})
    phase_answers = answers.get(phase_name, [])
    
    # Ensure the phase answers list is long enough
    phase_start_index = (phase - 1) * 30
    local_index = question_index - phase_start_index
    
    while len(phase_answers) <= local_index:
        phase_answers.append(None)
    
    phase_answers[local_index] = answer
    answers[phase_name] = phase_answers
    
    # Update session
    update_exam_session(exam_id, {"answers": answers, "status": "in_progress"})
    
    return {
        "status": "success",
        "message": "Answer saved",
        "question_index": question_index
    }


@mock_board_exam_router.post("/advance-phase", status_code=status.HTTP_200_OK)
async def advance_phase(payload: AdvancePhaseRequest):
    """Advance to the next phase or start a break."""
    uid = payload.uid
    exam_id = payload.exam_id
    
    if not all([uid, exam_id]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Get exam session
    exam_data = get_exam_session(exam_id)
    if not exam_data:
        raise HTTPException(status_code=404, detail="Exam session not found")
    
    if exam_data.get("uid") != uid:
        raise HTTPException(status_code=403, detail="Unauthorized access to exam")
    
    current_phase = exam_data.get("current_phase", 1)
    phase_name = get_phase_name(current_phase)
    
    # Mark current phase as completed
    phase_status = exam_data.get("phase_status", {})
    phase_status[phase_name] = "completed"
    
    # Check if this is the last phase
    if current_phase >= 3:
        # Exam is complete
        update_exam_session(exam_id, {
            "phase_status": phase_status,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc)
        })
        
        # Calculate score
        updated_exam = get_exam_session(exam_id)
        score_data = calculate_score(updated_exam)
        
        # Update score
        update_exam_session(exam_id, {"score": score_data})
        
        # Process weak areas
        weak_analysis = process_weak_areas(updated_exam)
        update_exam_session(exam_id, {
            "weak_areas": weak_analysis["weak_areas"],
            "recommendation": weak_analysis["recommendation"]
        })
        
        # Update user_progress with weaknesses
        try:
            from services.progressService import updateMockExamProgress
            await updateMockExamProgress(uid, score_data["percentage"])
        except Exception as e:
            logger.error(f"Failed to update progress: {str(e)}")
        
        return {
            "status": "success",
            "message": "Exam completed!",
            "exam_status": "completed",
            "score": score_data
        }
    
    # Start break
    break_duration = BREAK_DURATIONS.get(current_phase, 600)
    break_end_time = datetime.now(timezone.utc) + timedelta(seconds=break_duration)
    
    update_exam_session(exam_id, {
        "phase_status": phase_status,
        "status": "break",
        "break": {
            "active": True,
            "break_end_time": break_end_time
        }
    })
    
    # Return break info
    phase_display = {1: "Easy", 2: "Medium", 3: "Hard"}
    
    return {
        "status": "success",
        "message": f"Phase {phase_display.get(current_phase, '')} completed. Break started.",
        "exam_status": "break",
        "break_end_time": break_end_time.isoformat(),
        "next_phase": current_phase + 1,
        "break_duration_seconds": break_duration
    }


@mock_board_exam_router.post("/resume", status_code=status.HTTP_200_OK)
async def resume_exam(payload: AdvancePhaseRequest):
    """Resume from break to the next phase."""
    uid = payload.uid
    exam_id = payload.exam_id
    
    if not all([uid, exam_id]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Get exam session
    exam_data = get_exam_session(exam_id)
    if not exam_data:
        raise HTTPException(status_code=404, detail="Exam session not found")
    
    if exam_data.get("uid") != uid:
        raise HTTPException(status_code=403, detail="Unauthorized access to exam")
    
    # Check if break is over
    break_data = exam_data.get("break", {})
    break_end_time = break_data.get("break_end_time")
    
    if break_end_time:
        break_end_time = break_end_time if break_end_time.tzinfo else break_end_time.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) < break_end_time:
            return {
                "status": "waiting",
                "message": "Break not finished yet",
                "break_end_time": break_end_time.isoformat()
            }
    
    # Advance to next phase
    current_phase = exam_data.get("current_phase", 1)
    next_phase = current_phase + 1
    
    phase_name = get_phase_name(next_phase)
    phase_status = exam_data.get("phase_status", {})
    phase_status[phase_name] = "in_progress"
    
    now = datetime.now(timezone.utc)
    phase_duration = PHASE_CONFIG.get(next_phase, {}).get("duration", 5400)
    
    update_exam_session(exam_id, {
        "current_phase": next_phase,
        "phase_status": phase_status,
        "status": "in_progress",
        "phase_start_time": now,
        "phase_end_time": now + timedelta(seconds=phase_duration),
        "break": {
            "active": False,
            "break_end_time": None
        }
    })
    
    return {
        "status": "success",
        "message": f"Resumed to Phase {next_phase}",
        "exam_status": "in_progress",
        "current_phase": next_phase
    }


@mock_board_exam_router.post("/submit", status_code=status.HTTP_200_OK)
async def submit_mock_exam(payload: SubmitExamRequest):
    """Submit the entire exam and get results."""
    uid = payload.uid
    exam_id = payload.exam_id
    answers = payload.answers
    
    # Get exam session
    exam_data = get_exam_session(exam_id)
    if not exam_data:
        raise HTTPException(status_code=404, detail="Exam session not found")
    
    if exam_data.get("uid") != uid:
        raise HTTPException(status_code=403, detail="Unauthorized access to exam")
    
    # Process answers - convert from flat object to phase-based structure
    secure_keys = exam_data.get("secure_answer_keys", {})
    
    # Build answers by phase
    phase_answers = {
        "easy": [],
        "medium": [],
        "hard": []
    }
    
    for i in range(1, 101):
        q_id = str(i)
        user_ans = answers.get(q_id, "")
        if i <= 30:
            phase_answers["easy"].append(user_ans)
        elif i <= 60:
            phase_answers["medium"].append(user_ans)
        else:
            phase_answers["hard"].append(user_ans)
    
    # Calculate score
    score = 0
    total_items = 100
    breakdown = {}
    
    for i in range(1, 101):
        q_id = str(i)
        if q_id in secure_keys:
            correct_ans = secure_keys[q_id].get("correct")
            user_ans = answers.get(q_id, "")
            is_correct = user_ans == correct_ans if user_ans else False
            
            if is_correct:
                score += 1
            
            breakdown[q_id] = {
                "user_answer": user_ans if user_ans else "Unanswered",
                "correct_answer": correct_ans,
                "rationale": secure_keys[q_id].get("rationale"),
                "is_correct": is_correct
            }
    
    submission_time = datetime.now(timezone.utc)
    score_percentage = round((score / total_items) * 100)
    
    # Update exam session
    update_exam_session(exam_id, {
        "status": "completed",
        "submitted_at": submission_time,
        "completed_at": submission_time,
        "user_submissions": answers,
        "answers": phase_answers,
        "calculated_score": score,
        "total_items": total_items,
        "evaluation_breakdown": breakdown,
        "score": {
            "correct": score,
            "total": total_items,
            "percentage": score_percentage
        }
    })
    
    # Process weak areas
    updated_exam = get_exam_session(exam_id)
    weak_analysis = process_weak_areas(updated_exam)
    
    update_exam_session(exam_id, {
        "weak_areas": weak_analysis["weak_areas"],
        "recommendation": weak_analysis["recommendation"]
    })
    
    # Update progress in user_progress
    try:
        progress_ref = db.collection("user_progress").document(uid)
        progress_ref.set({
            "mock_exams_taken": firestore.Increment(1),
            "latest_board_score": score_percentage,
            "weaknesses": weak_analysis["weak_areas"],
            "weakness_recommendation": weak_analysis["recommendation"],
            "last_updated": datetime.now(timezone.utc)
        }, merge=True)
    except Exception as e:
        logger.error(f"Failed to update progress: {str(e)}")
    
    return {
        "status": "success",
        "exam_id": exam_id,
        "score": score,
        "total_items": total_items,
        "percentage": score_percentage,
        "passed": score_percentage >= PASSING_SCORE,
        "weak_areas": weak_analysis["weak_areas"],
        "recommendation": weak_analysis["recommendation"],
        "release_at": submission_time.isoformat()
    }


@mock_board_exam_router.post("/limit-status", status_code=status.HTTP_200_OK)
async def get_mock_exam_limit_status(payload: dict):
    """Get the current rate limit status for mock board exam."""
    uid = payload.get("uid")
    if not uid:
        raise HTTPException(status_code=400, detail="Missing user UID")
    
    limit_status = check_rate_limit_status(uid, "mock_board_exam", max_limit=1)
    return {
        "status": "success",
        "slots_remaining": limit_status["remaining"],
        "used": limit_status.get("used", 0),
        "available": limit_status["available"],
        "reset_at": limit_status["reset_at"]
    }


@mock_board_exam_router.get("/results/{uid}/{exam_id}", status_code=status.HTTP_200_OK)
async def get_exam_results(uid: str, exam_id: str):
    """Get the results of a completed exam."""
    exam_data = get_exam_session(exam_id)
    if not exam_data:
        raise HTTPException(status_code=404, detail="Exam session not found")
    
    if exam_data.get("uid") != uid:
        raise HTTPException(status_code=403, detail="Unauthorized access to exam")
    
    if exam_data.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Exam not completed yet")
    
    return {
        "status": "success",
        "exam_id": exam_id,
        "score": exam_data.get("score", {}),
        "weak_areas": exam_data.get("weak_areas", []),
        "recommendation": exam_data.get("recommendation", ""),
        "completed_at": exam_data.get("completed_at")
    }


@mock_board_exam_router.get("/questions/{exam_id}", status_code=status.HTTP_200_OK)
async def get_exam_questions(exam_id: str):
    """Get the questions for an exam."""
    exam_data = get_exam_session(exam_id)
    if not exam_data:
        raise HTTPException(status_code=404, detail="Exam session not found")
    
    questions = exam_data.get("questions_data", [])
    
    # Remove correct answers for client
    client_questions = []
    for q in questions:
        client_questions.append({
            "id": q.get("id"),
            "question": q.get("question"),
            "options": q.get("options")
        })
    
    return {
        "status": "success",
        "questions": client_questions,
        "current_phase": exam_data.get("current_phase", 1),
        "current_question_index": exam_data.get("current_question_index", 0)
    }