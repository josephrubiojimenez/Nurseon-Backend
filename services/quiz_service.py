# services/quiz_service.py
import os
import logging
import json
from datetime import datetime, timezone
from fastapi import HTTPException, status
import google.generativeai as genai

from models.quiz_models import QuizStructure

logger = logging.getLogger("quiz_service")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class QuizService:
    @staticmethod
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

    @staticmethod
    def get_user_usage(uid: str):
        from utils.limiters import check_rate_limit_status
        return check_rate_limit_status(uid, "quiz", max_limit=5)

    @staticmethod
    def get_cache_document(doc_id: str):
        from database.firebase import db
        return db.collection("quizzes_cache").document(doc_id).get()

    @staticmethod
    def save_cache_document(doc_id: str, data: dict):
        from database.firebase import db
        db.collection("quizzes_cache").document(doc_id).set(data)

    @staticmethod
    def save_generated_quiz(data: dict):
        from database.firebase import db
        doc_ref = db.collection("generated_quizzes").document()
        doc_ref.set(data)
        return doc_ref.id

    @staticmethod
    def save_user_quiz_record(data: dict):
        from database.firebase import db
        db.collection("generated_quizzes").document().set(data)