# services/case_studies_service.py
import os
import logging
import json
from datetime import datetime, timezone
from fastapi import HTTPException, status
import google.generativeai as genai

from models.case_studies_models import CaseStudyStructure, EvaluationStructure
from database.firebase import db

logger = logging.getLogger("case_studies_service")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

difficulty_points = {
    "Easy": 10,
    "Standard": 20,
    "Hard": 30
}

class CaseStudiesService:
    @staticmethod
    def run_gemini_case_generation(topic: str, difficulty: str) -> dict:
        if not GEMINI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="System is Busy."
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
            logger.error(f"Cannnot generate case study: {error_msg}", exc_info=True)
            
            if "429" in error_msg or "quota" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests right now. Please wait a minute and try again."
                )
            elif "api_key" in error_msg.lower() or "invalid" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Our system is taking a break. Please try again in a few minutes."
                )
            elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Our system is taking a break. Please try again in a few minutes."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Oops! Something went wrong. Please try again."
                )

    @staticmethod
    def run_gemini_evaluation(scenario: str, response_text: str) -> dict:
        if not GEMINI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="System is busy."
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
            logger.error(f"System error: {error_msg}", exc_info=True)
            
            if "429" in error_msg or "quota" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests right now. Please wait a minute and try again."
                )
            elif "api_key" in error_msg.lower() or "invalid" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Our system is taking a break. Please try again in a few minutes."
                )
            elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Our system is taking a break. Please try again in a few minutes."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Oops! Something went wrong. Please try again."
                )

    @staticmethod
    def update_user_progress(uid: str, difficulty: str, score: int = None):
        try:
            progress_ref = db.collection("user_progress").document(uid)
            doc = progress_ref.get()
            current_data = doc.to_dict() if doc.exists else {}
            
            points = difficulty_points.get(difficulty, 20)
            current_points = current_data.get("total_case_study_points", 0)
            new_points = current_points + points
            
            update_data = {
                "total_case_study_points": new_points,
                "last_updated": datetime.now(timezone.utc)
            }
            
            if score is not None:
                total_scores = current_data.get("case_study_scores", [])
                total_scores.append(score)
                update_data["case_study_scores"] = total_scores
                if total_scores:
                    avg_score = sum(total_scores) / len(total_scores)
                    update_data["overall_case_study_accuracy"] = round(avg_score, 2)
            
            progress_ref.set(update_data, merge=True)
            logger.info(f"Updated progress for user {uid}: +{points} points (Total: {new_points})")
            return new_points
        except Exception as e:
            logger.error(f"Failed to update progress for user {uid}: {str(e)}", exc_info=True)