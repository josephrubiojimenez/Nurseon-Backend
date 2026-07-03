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

logger = logging.getLogger("case_studies_router")
case_studies_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# 1. SCHEMAS & STRUCTURAL PAYLOADS
# ==========================================

class CaseStudyPayload(BaseModel):
    uid: str
    topic: str
    difficulty: str = "Standard"

class EvaluationPayload(BaseModel):
    uid: str
    patient_scenario: str
    student_response: str
    difficulty: str = "Standard"  # Added to track difficulty for points

# --- Gemini Structured Output Definitions ---

class CaseStudyStructure(BaseModel):
    """Guaranteed structural layout for generated Clinical Cases."""
    title: str
    patient_name: str
    context: str
    patient_complaint: str

class EvaluationStructure(BaseModel):
    """Guaranteed structural layout for Clinical Case Appraisals."""
    score_percentage: int
    clinical_rating: str
    professional_critique: str
    recommended_response: str
    medical_references: str

# ==========================================
# 2. CORE AI ENGINES (STRUCTURED)
# ==========================================

difficulty_points = {
    "Easy": 10,
    "Standard": 20,
    "Hard": 30
}

def run_gemini_case_generation(topic: str, difficulty: str) -> dict:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service is currently unconfigured."
        )

    model = genai.GenerativeModel("gemini-2.5-flash")
    
    system_prompt = (
        "You are an expert Nursing Clinical Simulation Instructor.\n"
        f"Generate a realistic patient case scenario centered around this disease/topic: '{topic}' at a '{difficulty}' level.\n\n"
        "The scenario must represent a direct clinical floor interaction where a patient speaks directly to the nurse."
    )

    try:
        response = model.generate_content(
            system_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=CaseStudyStructure
            )
        )
        return json.loads(response.text)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Gemini Case Study Generation Failure: {error_msg}", exc_info=True)
        
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
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Oops! Something went wrong. Please try again."
            )


def run_gemini_evaluation(scenario: str, response_text: str) -> dict:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service is currently unconfigured."
        )

    model = genai.GenerativeModel("gemini-2.5-flash")
    
    system_prompt = (
        f"You are an advanced Clinical Case Evaluator. Analyze this clinical patient scenario and background context:\n\"{scenario}\"\n\n"
        f"Critically evaluate the user's intervention response:\n\"{response_text}\"\n\n"
        "CRITICAL ROLEPLAY RULE:\n"
        "Treat the user as the primary Professional Registered Nurse fully in charge of this patient's care. "
        "Do NOT address them as a nursing student, do NOT evaluate them as a student, and NEVER suggest that they 'help the registered nurse' or 'defer to a senior nurse' for basic independent nursing processes. "
        "Evaluate their actions as an autonomous, practicing professional nurse exercising independent or dependent nursing scope of practice.\n\n"
        "Determine if their action is safe, professional, and correct according to current nursing care protocols."
    )

    try:
        response = model.generate_content(
            system_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=EvaluationStructure
            )
        )
        return json.loads(response.text)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Gemini Evaluation Pipeline Failure: {error_msg}", exc_info=True)
        
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
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Oops! Something went wrong. Please try again."
            )


def update_user_progress(uid: str, difficulty: str, score: int = None):
    """
    Update user progress for case studies with points-based system.
    Easy = 10 points, Standard = 20 points, Hard = 30 points
    Max points = 100
    """
    try:
        progress_ref = db.collection("user_progress").document(uid)
        
        # Get current progress
        doc = progress_ref.get()
        current_data = doc.to_dict() if doc.exists else {}
        
        # Calculate points based on difficulty
        points = difficulty_points.get(difficulty, 20)
        
        # Calculate new total points
        current_points = current_data.get("total_case_study_points", 0)
        new_points = current_points + points
        
        # Update the document
        update_data = {
            "total_case_study_points": new_points,
            "last_updated": datetime.now(timezone.utc)
        }
        
        # If score is provided, update accuracy
        if score is not None:
            total_scores = current_data.get("case_study_scores", [])
            total_scores.append(score)
            update_data["case_study_scores"] = total_scores
            
            # Calculate average score
            if total_scores:
                avg_score = sum(total_scores) / len(total_scores)
                update_data["overall_case_study_accuracy"] = round(avg_score, 2)
        
        progress_ref.set(update_data, merge=True)
        logger.info(f"✅ Updated progress for user {uid}: +{points} points (Total: {new_points})")
        
        return new_points
        
    except Exception as e:
        logger.error(f"Failed to update progress for user {uid}: {str(e)}", exc_info=True)
        # Don't raise - this is non-critical


# ==========================================
# 3. ROUTER ENDPOINTS
# ==========================================

@case_studies_router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_case_study(payload: CaseStudyPayload):
    # 1. Enforce regional limiter bounds
    slots_remaining = enforce_feature_limit(payload.uid, "case_studies", max_limit=5)

    try:
        # 2. Build Cache Fingerprint
        clean_topic = payload.topic.strip().lower()
        clean_difficulty = payload.difficulty.strip().lower()
        case_fingerprint = hashlib.md5(f"{clean_topic}_{clean_difficulty}".encode('utf-8')).hexdigest()

        # 3. Cache Query Check
        cache_doc = db.collection("cases_cache").document(case_fingerprint).get()

        if cache_doc.exists:
            cached_case = cache_doc.to_dict()
            logger.info(f"Case Study Cache Hit! Serving topic: '{payload.topic}' [{payload.difficulty}]")

            # Save user log history event
            user_case_record = {
                "user_uid": payload.uid,
                "topic": payload.topic,
                "difficulty": payload.difficulty,
                "case_details": cached_case["case_details"],
                "created_at": datetime.now(timezone.utc),
                "source": "cache"
            }
            db.collection("generated_cases").document().set(user_case_record)

            return {
                "status": "success",
                "case_id": cache_doc.id,
                "case": cached_case["case_details"],
                "slots_remaining": slots_remaining
            }

        # 4. Cache Miss -> Process New AI Data
        case_data_object = run_gemini_case_generation(payload.topic, payload.difficulty)

        record = {
            "user_uid": payload.uid,
            "topic": payload.topic,
            "difficulty": payload.difficulty,
            "case_details": case_data_object,
            "created_at": datetime.now(timezone.utc),
            "source": "gemini_generation"
        }

        # Write record history and seed regional cache map
        doc_ref = db.collection("generated_cases").document()
        doc_ref.set(record)

        db.collection("cases_cache").document(case_fingerprint).set({
            "topic": clean_topic,
            "difficulty": clean_difficulty,
            "case_details": case_data_object,
            "cached_at": datetime.now(timezone.utc)
        })

        return {
            "status": "success",
            "case_id": doc_ref.id,
            "case": case_data_object,
            "slots_remaining": slots_remaining
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Case runtime crash: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal application error compiling case files."
        )


@case_studies_router.post("/evaluate", status_code=status.HTTP_200_OK)
async def evaluate_response(payload: EvaluationPayload):
    try:
        # 1. Build Evaluation Cache Fingerprint
        clean_scenario = payload.patient_scenario.strip().lower()
        clean_response = payload.student_response.strip().lower()
        eval_fingerprint = hashlib.md5(f"{clean_scenario}_{clean_response}".encode('utf-8')).hexdigest()

        # 2. Check for matching Evaluation Cache
        cache_doc = db.collection("evaluations_cache").document(eval_fingerprint).get()

        if cache_doc.exists:
            cached_eval = cache_doc.to_dict()
            logger.info("Evaluation Cache Hit! Instantly serving computed clinical appraisal score.")

            # Save evaluation record for cache hit
            evaluation_record = {
                "user_uid": payload.uid,
                "patient_scenario": payload.patient_scenario,
                "student_response": payload.student_response,
                "evaluation_details": cached_eval["evaluation_details"],
                "evaluated_at": datetime.now(timezone.utc),
                "source": "cache"
            }
            db.collection("case_evaluations").document().set(evaluation_record)
            
            # Update progress for cached evaluation
            score = cached_eval["evaluation_details"].get("score_percentage")
            update_user_progress(payload.uid, payload.difficulty, score)

            return {
                "status": "success",
                "evaluation": cached_eval["evaluation_details"],
                "progress_updated": True
            }

        # 3. Cache Miss -> Evaluate with Gemini
        evaluation_data = run_gemini_evaluation(payload.patient_scenario, payload.student_response)

        # Save evaluation record for cache miss
        evaluation_record = {
            "user_uid": payload.uid,
            "patient_scenario": payload.patient_scenario,
            "student_response": payload.student_response,
            "evaluation_details": evaluation_data,
            "evaluated_at": datetime.now(timezone.utc),
            "source": "gemini_evaluation"
        }

        # 4. Commit to database and update cache mapping
        db.collection("case_evaluations").document().set(evaluation_record)
        
        db.collection("evaluations_cache").document(eval_fingerprint).set({
            "evaluation_details": evaluation_data,
            "cached_at": datetime.now(timezone.utc)
        })

        # 5. Update user progress
        score = evaluation_data.get("score_percentage")
        update_user_progress(payload.uid, payload.difficulty, score)

        return {
            "status": "success",
            "evaluation": evaluation_data,
            "progress_updated": True
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Evaluation pipeline crash: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal application error analyzing student response."
        )