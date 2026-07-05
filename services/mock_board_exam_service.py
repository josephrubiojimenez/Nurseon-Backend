# services/mock_board_exam_service.py
import os
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
from fastapi import HTTPException, status

from database.firebase import db
from google import genai
from google.genai import types
from models.mock_board_exam_models import UnifiedExamResponseSchema

logger = logging.getLogger("mock_board_exam_service")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai_client = None
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)

PHASE_CONFIG = {
    1: {"name": "easy", "start": 0, "end": 30, "label": "Easy (NP I & II)", "duration": 5400},
    2: {"name": "medium", "start": 30, "end": 60, "label": "Medium (NP III)", "duration": 5400},
    3: {"name": "hard", "start": 60, "end": 100, "label": "Hard (NP IV & V)", "duration": 5400}
}

BREAK_DURATIONS = {
    1: 600,
    2: 1200,
    3: 0
}

PASSING_SCORE = 75

class MockBoardExamService:
    @staticmethod
    def generate_all_100_questions() -> list:
        if not genai_client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="System busy."
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
            logger.exception("Failed to generate exam.")

            if "429" in error_msg or "quota" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="System busy. Please try again in 1 minute."
                )
            elif "api_key" in error_msg.lower() or "invalid" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="System busy. Please try again in 1 minute."
                )
            elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="System busy. Please try again in 1 minute."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to process response: {error_msg[:100]}"
                )

    @staticmethod
    def get_phase_for_question_index(index: int) -> int:
        if index < 30:
            return 1
        elif index < 60:
            return 2
        else:
            return 3

    @staticmethod
    def get_phase_name(phase: int) -> str:
        return PHASE_CONFIG.get(phase, {}).get("name", "unknown")

    @staticmethod
    def get_exam_session(exam_id: str) -> Optional[Dict]:
        try:
            session_ref = db.collection("exam_sessions").document(exam_id)
            doc = session_ref.get()
            if doc.exists:
                return {"id": doc.id, **doc.to_dict()}
            return None
        except Exception as e:
            logger.error(f"Error getting exam session {exam_id}: {str(e)}")
            return None

    @staticmethod
    def update_exam_session(exam_id: str, updates: Dict) -> bool:
        try:
            updates["updated_at"] = datetime.now(timezone.utc)
            session_ref = db.collection("exam_sessions").document(exam_id)
            session_ref.update(updates)
            return True
        except Exception as e:
            logger.error(f"Error updating exam session {exam_id}: {str(e)}")
            return False

    @staticmethod
    def create_exam_session(uid: str, questions: list, exam_id: str) -> str:
        now = datetime.now(timezone.utc)

        session_data = {
            "uid": uid,
            "feature": "mock_board_exam",
            "window_start": now,
            "status": "in_progress",
            "current_phase": 1,
            "current_question_index": 0,
            "phase_start_time": now,
            "phase_end_time": now + timedelta(seconds=5400),
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

        secure_keys = {}
        for q in questions:
            secure_keys[str(q.get("id"))] = {
                "correct": q.get("correct_answer"),
                "rationale": q.get("rationale")
            }
        session_data["secure_answer_keys"] = secure_keys

        session_ref = db.collection("exam_sessions").document(exam_id)
        session_ref.set(session_data)

        return exam_id

    @staticmethod
    def calculate_score(exam_data: Dict) -> Dict:
        answers = exam_data.get("answers", {})
        secure_keys = exam_data.get("secure_answer_keys", {})

        correct = 0
        total = 100
        phase_scores = {"easy": {"correct": 0, "total": 30, "wrong": 0},
                        "medium": {"correct": 0, "total": 30, "wrong": 0},
                        "hard": {"correct": 0, "total": 40, "wrong": 0}}

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
                    if i < 30:
                        phase = "easy"
                    elif i < 60:
                        phase = "medium"
                    else:
                        phase = "hard"
                    phase_scores[phase]["wrong"] += 1

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

    @staticmethod
    def process_weak_areas(exam_data: Dict) -> Dict:
        try:
            secure_keys = exam_data.get("secure_answer_keys", {})
            answers = exam_data.get("answers", {})

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
                        rationale = secure_keys[q_id].get("rationale", "")
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

            priority_order = {"critical": 0, "medium": 1, "low": 2}
            weakness_list.sort(key=lambda x: priority_order.get(x["priority"], 3))

            recommendation = MockBoardExamService.generate_recommendation(weakness_list)

            return {
                "weak_areas": weakness_list[:5],
                "recommendation": recommendation
            }
        except Exception as e:
            logger.error(f"Error processing weak areas: {str(e)}")
            return {
                "weak_areas": [],
                "recommendation": "Complete more exams to get personalized insights."
            }

    @staticmethod
    def generate_recommendation(weaknesses: List[Dict]) -> str:
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

    @staticmethod
    def get_existing_session(uid: str) -> Optional[Dict]:
        try:
            sessions_ref = db.collection("exam_sessions")
            query = sessions_ref.where("uid", "==", uid).where("status", "in", ["in_progress", "break"]).limit(1).stream()

            for doc in query:
                return {"id": doc.id, **doc.to_dict()}
            return None
        except Exception as e:
            logger.error(f"Error checking existing session: {str(e)}")
            return None

    @staticmethod
    def get_completed_session(uid: str) -> Optional[Dict]:
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

    @staticmethod
    def auto_advance_phase(uid: str, exam_id: str):
        try:
            exam_data = MockBoardExamService.get_exam_session(exam_id)
            if not exam_data:
                return

            current_phase = exam_data.get("current_phase", 1)
            phase_name = MockBoardExamService.get_phase_name(current_phase)

            phase_status = exam_data.get("phase_status", {})
            phase_status[phase_name] = "completed"

            if current_phase >= 3:
                MockBoardExamService.update_exam_session(exam_id, {
                    "phase_status": phase_status,
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc)
                })

                updated_exam = MockBoardExamService.get_exam_session(exam_id)
                score_data = MockBoardExamService.calculate_score(updated_exam)

                MockBoardExamService.update_exam_session(exam_id, {"score": score_data})

                weak_analysis = MockBoardExamService.process_weak_areas(updated_exam)
                MockBoardExamService.update_exam_session(exam_id, {
                    "weak_areas": weak_analysis["weak_areas"],
                    "recommendation": weak_analysis["recommendation"]
                })
                return

            break_duration = BREAK_DURATIONS.get(current_phase, 600)
            break_end_time = datetime.now(timezone.utc) + timedelta(seconds=break_duration)

            MockBoardExamService.update_exam_session(exam_id, {
                "phase_status": phase_status,
                "status": "break",
                "break": {
                    "active": True,
                    "break_end_time": break_end_time
                }
            })
        except Exception as e:
            logger.error(f"Error auto-advancing phase: {str(e)}")