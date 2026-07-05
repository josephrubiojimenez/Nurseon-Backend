# controllers/case_studies_controller.py
import logging
import hashlib
from datetime import datetime, timezone
from fastapi import HTTPException, status

from services.case_studies_service import CaseStudiesService
from utils.limiters import enforce_feature_limit, check_rate_limit_status
from database.firebase import db

logger = logging.getLogger("case_studies_controller")

class CaseStudiesController:
    def __init__(self):
        self.service = CaseStudiesService()

    def get_limit_status(self, uid: str):
        if not uid:
            raise HTTPException(status_code=400, detail="Missing user UID")
        
        limit_status = check_rate_limit_status(uid, "case_studies", max_limit=5)
        return {
            "status": "success",
            "slots_remaining": limit_status["remaining"],
            "used": limit_status.get("used", 0),
            "available": limit_status["available"],
            "reset_at": limit_status["reset_at"]
        }

    def generate_case_study(self, uid: str, topic: str, difficulty: str):
        try:
            slots_remaining = enforce_feature_limit(uid, "case_studies", max_limit=5)
        except HTTPException as e:
            if e.status_code == 429:
                # Get the reset time from the status check
                limit_status = check_rate_limit_status(uid, "case_studies", max_limit=5)
                reset_msg = f" at {limit_status['reset_at']}" if limit_status.get("reset_at") else " tomorrow"
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Case Study limit reached. You can try again{reset_msg}."
                )
            raise e

        try:
            clean_topic = topic.strip().lower()
            clean_difficulty = difficulty.strip().lower()
            case_fingerprint = hashlib.md5(f"{clean_topic}_{clean_difficulty}".encode('utf-8')).hexdigest()

            cache_doc = db.collection("cases_cache").document(case_fingerprint).get()

            if cache_doc.exists:
                cached_case = cache_doc.to_dict()
                logger.info(f"Case Study Cache Hit! Serving topic: '{topic}' [{difficulty}]")

                user_case_record = {
                    "user_uid": uid,
                    "topic": topic,
                    "difficulty": difficulty,
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

            case_data_object = self.service.run_gemini_case_generation(topic, difficulty)

            record = {
                "user_uid": uid,
                "topic": topic,
                "difficulty": difficulty,
                "case_details": case_data_object,
                "created_at": datetime.now(timezone.utc),
                "source": "gemini_generation"
            }

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

    def evaluate_response(self, uid: str, patient_scenario: str, student_response: str, difficulty: str):
        try:
            clean_scenario = patient_scenario.strip().lower()
            clean_response = student_response.strip().lower()
            eval_fingerprint = hashlib.md5(f"{clean_scenario}_{clean_response}".encode('utf-8')).hexdigest()

            cache_doc = db.collection("evaluations_cache").document(eval_fingerprint).get()

            if cache_doc.exists:
                cached_eval = cache_doc.to_dict()
                logger.info("Evaluating score.")

                evaluation_record = {
                    "user_uid": uid,
                    "patient_scenario": patient_scenario,
                    "student_response": student_response,
                    "evaluation_details": cached_eval["evaluation_details"],
                    "evaluated_at": datetime.now(timezone.utc),
                    "source": "cache"
                }
                db.collection("case_evaluations").document().set(evaluation_record)

                return {
                    "status": "success",
                    "evaluation": cached_eval["evaluation_details"],
                    "progress_updated": True
                }

            evaluation_data = self.service.run_gemini_evaluation(patient_scenario, student_response)

            evaluation_record = {
                "user_uid": uid,
                "patient_scenario": patient_scenario,
                "student_response": student_response,
                "evaluation_details": evaluation_data,
                "evaluated_at": datetime.now(timezone.utc),
                "source": "gemini_evaluation"
            }

            db.collection("case_evaluations").document().set(evaluation_record)
            db.collection("evaluations_cache").document(eval_fingerprint).set({
                "evaluation_details": evaluation_data,
                "cached_at": datetime.now(timezone.utc)
            })

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
                detail="Error."
            )