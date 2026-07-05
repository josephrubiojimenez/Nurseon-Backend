# controllers/quiz_controller.py
import logging
import hashlib
from datetime import datetime, timezone
from fastapi import HTTPException, status

from services.quiz_service import QuizService
from utils.limiters import enforce_feature_limit, check_rate_limit_status

logger = logging.getLogger("quiz_controller")

class QuizController:
    def __init__(self):
        self.service = QuizService()

    def get_user_usage(self, uid: str):
        """Get the current quiz usage and limits for a user."""
        try:
            limit_status = self.service.get_user_usage(uid)
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

    def generate_quiz(self, uid: str, topic: str, num_questions: int):
        # Check limits first
        try:
            slots_remaining = enforce_feature_limit(uid, "quiz", max_limit=5)
            is_limit_reached = False
        except HTTPException as e:
            if e.status_code == 429:
                limit_status = check_rate_limit_status(uid, "quiz", max_limit=5)
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

        # Proceed with quiz generation
        try:
            clean_topic = topic.strip().lower()
            quiz_fingerprint = hashlib.md5(f"{clean_topic}_{num_questions}".encode('utf-8')).hexdigest()

            cache_doc = self.service.get_cache_document(quiz_fingerprint)

            if cache_doc.exists:
                cached_quiz = cache_doc.to_dict()
                logger.info(f"Quiz Cache Hit! Serving topic: '{topic}' with {num_questions} items.")

                user_quiz_record = {
                    "user_uid": uid,
                    "topic": topic,
                    "questions": cached_quiz["questions"],
                    "created_at": datetime.now(timezone.utc),
                    "source": "cache"
                }
                self.service.save_user_quiz_record(user_quiz_record)

                return {
                    "status": "success",
                    "is_cached": True,
                    "quiz_id": cache_doc.id,
                    "topic": topic,
                    "questions": cached_quiz["questions"],
                    "slots_remaining": slots_remaining,
                    "is_limit_reached": False
                }

            questions_list = self.service.run_gemini_quiz_generation(topic, num_questions)

            quiz_data = {
                "user_uid": uid,
                "topic": topic,
                "questions": questions_list,
                "created_at": datetime.now(timezone.utc),
                "source": "gemini_generation"
            }

            doc_id = self.service.save_generated_quiz(quiz_data)

            self.service.save_cache_document(quiz_fingerprint, {
                "topic": clean_topic,
                "questions": questions_list,
                "cached_at": datetime.now(timezone.utc)
            })

            return {
                "status": "success",
                "is_cached": False,
                "quiz_id": doc_id,
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