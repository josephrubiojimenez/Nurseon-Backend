# controllers/mock_board_exam_controller.py
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, status

from services.mock_board_exam_service import MockBoardExamService
from utils.limiters import enforce_feature_limit, check_rate_limit_status
from database.firebase import db

logger = logging.getLogger("mock_board_exam_controller")

class MockBoardExamController:
    def __init__(self):
        self.service = MockBoardExamService()

    def get_exam_status(self, uid: str):
        try:
            existing = self.service.get_existing_session(uid)

            if existing:
                phase_end_time = existing.get("phase_end_time")
                if phase_end_time and existing.get("status") == "in_progress":
                    phase_end_time = phase_end_time if phase_end_time.tzinfo else phase_end_time.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > phase_end_time:
                        self.service.auto_advance_phase(uid, existing["id"])
                        existing = self.service.get_existing_session(uid)
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
                    "phase_start_time": existing.get("phase_start_time"),
                    "score": existing.get("score", {"correct": 0, "total": 100, "percentage": 0}),
                    "weak_areas": existing.get("weak_areas", []),
                    "recommendation": existing.get("recommendation", "")
                }

            completed = self.service.get_completed_session(uid)
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
                    "phase_start_time": completed.get("phase_start_time"),
                    "score": completed.get("score", {"correct": 0, "total": 100, "percentage": 0}),
                    "weak_areas": completed.get("weak_areas", []),
                    "recommendation": completed.get("recommendation", "")
                }

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

    def start_mock_exam(self, uid: str):
        existing = self.service.get_existing_session(uid)
        if existing:
            return {
                "status": "success",
                "exam_id": existing["id"],
                "message": "Continuing existing exam",
                "exam_status": existing["status"],
                "current_phase": existing.get("current_phase", 1),
                "current_question_index": existing.get("current_question_index", 0)
            }

        limit_status = check_rate_limit_status(uid, "mock_board_exam", max_limit=1)
        if not limit_status["available"]:
            reset_msg = f" at {limit_status['reset_at']}" if limit_status.get("reset_at") else " tomorrow"
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Mock Board Exam limit reached. You can try again{reset_msg}."
            )

        try:
            questions = self.service.generate_all_100_questions()
            exam_id = f"exam_{uid}_{int(datetime.now(timezone.utc).timestamp())}"

            self.service.create_exam_session(uid, questions, exam_id)

            slots_remaining = enforce_feature_limit(uid, "mock_board_exam", max_limit=1)

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
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error starting exam: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to start exam")

    def submit_answer(self, uid: str, exam_id: str, question_index: int, answer: str):
        if not all([uid, exam_id, question_index is not None, answer]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        exam_data = self.service.get_exam_session(exam_id)
        if not exam_data:
            raise HTTPException(status_code=404, detail="Exam session not found")

        if exam_data.get("uid") != uid:
            raise HTTPException(status_code=403, detail="Unauthorized access to exam")

        phase = self.service.get_phase_for_question_index(question_index)
        phase_name = self.service.get_phase_name(phase)

        answers = exam_data.get("answers", {})
        phase_answers = answers.get(phase_name, [])

        phase_start_index = (phase - 1) * 30
        local_index = question_index - phase_start_index

        while len(phase_answers) <= local_index:
            phase_answers.append(None)

        phase_answers[local_index] = answer
        answers[phase_name] = phase_answers

        self.service.update_exam_session(exam_id, {"answers": answers, "status": "in_progress"})

        return {
            "status": "success",
            "message": "Answer saved",
            "question_index": question_index
        }

    def advance_phase(self, uid: str, exam_id: str):
        if not all([uid, exam_id]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        exam_data = self.service.get_exam_session(exam_id)
        if not exam_data:
            raise HTTPException(status_code=404, detail="Exam session not found")

        if exam_data.get("uid") != uid:
            raise HTTPException(status_code=403, detail="Unauthorized access to exam")

        current_phase = exam_data.get("current_phase", 1)
        phase_name = self.service.get_phase_name(current_phase)

        phase_status = exam_data.get("phase_status", {})
        phase_status[phase_name] = "completed"

        if current_phase >= 3:
            self.service.update_exam_session(exam_id, {
                "phase_status": phase_status,
                "status": "completed",
                "completed_at": datetime.now(timezone.utc)
            })

            updated_exam = self.service.get_exam_session(exam_id)
            score_data = self.service.calculate_score(updated_exam)

            self.service.update_exam_session(exam_id, {"score": score_data})

            weak_analysis = self.service.process_weak_areas(updated_exam)
            self.service.update_exam_session(exam_id, {
                "weak_areas": weak_analysis["weak_areas"],
                "recommendation": weak_analysis["recommendation"]
            })

            try:
                from services.progressService import updateMockExamProgress
                import asyncio
                asyncio.create_task(updateMockExamProgress(uid, score_data["percentage"]))
            except Exception as e:
                logger.error(f"Failed to update progress: {str(e)}")

            return {
                "status": "success",
                "message": "Exam completed!",
                "exam_status": "completed",
                "score": score_data
            }

        break_duration = BREAK_DURATIONS.get(current_phase, 600)
        break_end_time = datetime.now(timezone.utc) + timedelta(seconds=break_duration)

        self.service.update_exam_session(exam_id, {
            "phase_status": phase_status,
            "status": "break",
            "break": {
                "active": True,
                "break_end_time": break_end_time
            }
        })

        phase_display = {1: "Easy", 2: "Medium", 3: "Hard"}

        return {
            "status": "success",
            "message": f"Phase {phase_display.get(current_phase, '')} completed. Break started.",
            "exam_status": "break",
            "break_end_time": break_end_time.isoformat(),
            "next_phase": current_phase + 1,
            "break_duration_seconds": break_duration
        }

    def resume_exam(self, uid: str, exam_id: str):
        if not all([uid, exam_id]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        exam_data = self.service.get_exam_session(exam_id)
        if not exam_data:
            raise HTTPException(status_code=404, detail="Exam session not found")

        if exam_data.get("uid") != uid:
            raise HTTPException(status_code=403, detail="Unauthorized access to exam")

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

        current_phase = exam_data.get("current_phase", 1)
        next_phase = current_phase + 1

        phase_name = self.service.get_phase_name(next_phase)
        phase_status = exam_data.get("phase_status", {})
        phase_status[phase_name] = "in_progress"

        now = datetime.now(timezone.utc)
        phase_duration = PHASE_CONFIG.get(next_phase, {}).get("duration", 5400)

        self.service.update_exam_session(exam_id, {
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

    def submit_mock_exam(self, uid: str, exam_id: str, answers: dict):
        exam_data = self.service.get_exam_session(exam_id)
        if not exam_data:
            raise HTTPException(status_code=404, detail="Exam session not found")

        if exam_data.get("uid") != uid:
            raise HTTPException(status_code=403, detail="Unauthorized access to exam")

        secure_keys = exam_data.get("secure_answer_keys", {})

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

        self.service.update_exam_session(exam_id, {
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

        updated_exam = self.service.get_exam_session(exam_id)
        weak_analysis = self.service.process_weak_areas(updated_exam)

        self.service.update_exam_session(exam_id, {
            "weak_areas": weak_analysis["weak_areas"],
            "recommendation": weak_analysis["recommendation"]
        })

        try:
            from google.cloud import firestore
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

    def get_mock_exam_limit_status(self, uid: str):
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

    def get_exam_results(self, uid: str, exam_id: str):
        exam_data = self.service.get_exam_session(exam_id)
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

    def get_exam_questions(self, exam_id: str):
        exam_data = self.service.get_exam_session(exam_id)
        if not exam_data:
            raise HTTPException(status_code=404, detail="Exam session not found")

        questions = exam_data.get("questions_data", [])

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