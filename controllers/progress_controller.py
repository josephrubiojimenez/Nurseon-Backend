# controllers/progress_controller.py
import logging
from datetime import datetime, timezone
from fastapi import HTTPException, status

from services.progress_service import ProgressService
from utils.limiters import check_rate_limit_status

logger = logging.getLogger("progress_controller")

class ProgressController:
    def __init__(self):
        self.service = ProgressService()

    def get_user_progress(self, uid: str):
        try:
            data = self.service.get_user_progress(uid)
            
            if not data:
                return self.service.get_default_progress()
            
            # Get case study points
            case_study_points = data.get("total_case_study_points", 0)
            
            # Calculate progress percentage (cap at 100%)
            case_progress_percent = min(100, round((case_study_points / self.service.MAX_CASE_STUDY_POINTS) * 100))
            
            # Get quiz data
            quiz_scores = data.get("quiz_scores", [])
            avg_quiz_score = round(sum(quiz_scores) / len(quiz_scores), 2) if quiz_scores else 0
            quizzes_answered = data.get("quizzes_answered", 0)
            
            # Get case study scores for accuracy
            case_study_scores = data.get("case_study_scores", [])
            avg_case_score = round(sum(case_study_scores) / len(case_study_scores), 2) if case_study_scores else 0
            
            # Calculate overall accuracy
            overall_accuracy = self.service.calculate_overall_accuracy(case_study_scores, quiz_scores)
            
            # Get case study limit status
            limit_status = check_rate_limit_status(uid, "case_studies", max_limit=5)
            
            # Get weaknesses
            weaknesses = data.get("weaknesses", [])
            if not isinstance(weaknesses, list):
                weaknesses = []
            
            # Get recommendation
            recommendation = data.get("weakness_recommendation", 
                "Keep studying and complete more activities to identify weak areas!")
            
            return {
                "quizzesAnswered": quizzes_answered,
                "totalQuizzes": 50,
                "caseStudyPoints": case_study_points,
                "maxCaseStudyPoints": self.service.MAX_CASE_STUDY_POINTS,
                "caseProgressPercent": case_progress_percent,
                "mockExamsTaken": data.get("mock_exams_taken", 0),
                "totalMockExams": 1,
                "overallAccuracy": overall_accuracy,
                "latestBoardScore": data.get("latest_board_score", 0),
                "overallBoardScore": data.get("overall_board_score", 0),
                "studyStreak": data.get("study_streak", 0),
                "timeSpentHours": data.get("time_spent_hours", 0),
                "slotsRemaining": limit_status.get("remaining", 5),
                "used": limit_status.get("used", 0),
                "available": limit_status.get("available", True),
                "reset_at": limit_status.get("reset_at", None),
                "weaknesses": weaknesses,
                "weaknessRecommendation": recommendation
            }
            
        except Exception as e:
            logger.error(f"Error fetching progress for user {uid}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch progress data"
            )

    def update_case_study_progress(self, uid: str, difficulty: str, score: float):
        try:
            if not uid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User UID is required"
                )
            
            progress_ref = self.service.get_user_progress_document(uid)
            doc = progress_ref.get()
            current_data = doc.to_dict() if doc.exists else {}
            
            points_to_add = self.service.calculate_case_study_points(difficulty, score)
            
            if points_to_add > 0:
                logger.info(f"User passed with {score}%. Awarding {points_to_add} points.")
            else:
                logger.info(f"User failed with {score}%. No points awarded.")
            
            # Calculate new totals
            current_points = current_data.get("total_case_study_points", 0)
            new_points = current_points + points_to_add
            
            # Prepare database update
            update_data = {
                "total_case_study_points": new_points,
                "last_updated": datetime.now(timezone.utc)
            }
            
            # Keep track of all scores
            scores = current_data.get("case_study_scores", [])
            scores.append(score)
            update_data["case_study_scores"] = scores
            update_data["average_case_study_score"] = round(sum(scores) / len(scores), 2)
            
            # Update streak
            today_datetime = datetime.now(timezone.utc)
            update_data["study_streak"] = self.service.calculate_study_streak(current_data, today_datetime)
            update_data["last_study_date"] = today_datetime
            update_data["time_spent_hours"] = current_data.get("time_spent_hours", 0) + 0.25
            
            # Commit to Firestore
            self.service.update_user_progress(uid, update_data)
            
            progress_percent = min(100, round((new_points / self.service.MAX_CASE_STUDY_POINTS) * 100))
            
            return {
                "success": True,
                "message": "Progress calculated successfully",
                "case_study_points": new_points,
                "case_progress_percent": progress_percent
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating case study progress: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process case study results"
            )

    def update_quiz_progress(self, uid: str, score: Optional[float] = None, 
                            correct_count: Optional[int] = None, questions_answered: int = 20):
        try:
            if not uid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User UID is required"
                )
            
            # Determine correct items to add
            if correct_count is not None:
                correct_items_added = int(correct_count)
            else:
                score_val = float(score) if score is not None else 0
                correct_items_added = round((score_val / 100) * questions_answered)
            
            progress_ref = self.service.get_user_progress_document(uid)
            doc = progress_ref.get()
            current_data = doc.to_dict() if doc.exists else {}
            
            # Accumulate correct answers
            current_correct_pool = current_data.get("quizzes_answered", 0)
            new_correct_pool = self.service.calculate_quiz_progress(current_correct_pool, correct_items_added)
            
            # Prepare database payload
            update_data = {
                "quizzes_answered": new_correct_pool,
                "last_updated": datetime.now(timezone.utc)
            }
            
            # Save historical percentages
            if score is not None:
                quiz_scores = current_data.get("quiz_scores", [])
                quiz_scores.append(float(score))
                update_data["quiz_scores"] = quiz_scores
                update_data["average_quiz_score"] = round(sum(quiz_scores) / len(quiz_scores), 2)
            
            # Update streak
            today_datetime = datetime.now(timezone.utc)
            update_data["study_streak"] = self.service.calculate_study_streak(current_data, today_datetime)
            update_data["last_study_date"] = today_datetime
            
            # Commit to Firestore
            self.service.update_user_progress(uid, update_data)
            
            logger.info(f"Added +{correct_items_added} correct items. Global Pool Tracker: {new_correct_pool}/{self.service.MAX_QUIZ_ITEMS}")
            
            return {
                "success": True,
                "message": "Quiz progress pool updated successfully",
                "quizzes_answered": new_correct_pool,
                "max_quiz_items": self.service.MAX_QUIZ_ITEMS
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating quiz progress pool: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process quiz results"
            )

    def update_mock_exam_progress(self, uid: str, score: float, weaknesses: List[Dict], recommendation: str):
        try:
            if not uid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User UID is required"
                )
            
            progress_ref = self.service.get_user_progress_document(uid)
            doc = progress_ref.get()
            current_data = doc.to_dict() if doc.exists else {}
            
            # Prepare update data
            update_data = {
                "mock_exams_taken": current_data.get("mock_exams_taken", 0) + 1,
                "last_updated": datetime.now(timezone.utc)
            }
            
            # Update board scores
            if score > 0:
                update_data["latest_board_score"] = score
                
                board_scores = current_data.get("board_scores", [])
                board_scores.append(score)
                update_data["board_scores"] = board_scores
                
                if board_scores:
                    update_data["overall_board_score"] = round(sum(board_scores) / len(board_scores), 2)
            
            # Update weaknesses
            if weaknesses:
                existing_weaknesses = current_data.get("weaknesses", [])
                update_data["weaknesses"] = self.service.merge_weaknesses(existing_weaknesses, weaknesses)
            
            # Update recommendation
            if recommendation:
                update_data["weakness_recommendation"] = recommendation
            
            # Update streak
            today_datetime = datetime.now(timezone.utc)
            update_data["study_streak"] = self.service.calculate_study_streak(current_data, today_datetime)
            update_data["last_study_date"] = today_datetime
            update_data["time_spent_hours"] = current_data.get("time_spent_hours", 0) + 1
            
            # Commit update
            self.service.update_user_progress(uid, update_data)
            
            logger.info(f"Updated mock exam progress for user {uid}: score: {score}%, weaknesses: {len(weaknesses)} areas")
            
            return {
                "success": True,
                "message": "Mock exam progress updated successfully",
                "mock_exams_taken": update_data["mock_exams_taken"],
                "latest_board_score": update_data.get("latest_board_score", 0),
                "overall_board_score": update_data.get("overall_board_score", 0),
                "weaknesses": update_data.get("weaknesses", []),
                "weakness_recommendation": update_data.get("weakness_recommendation", "")
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating mock exam progress: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update mock exam progress"
            )

    def update_weaknesses(self, uid: str, weaknesses: List[Dict], recommendation: str):
        try:
            if not uid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User UID is required"
                )
            
            progress_ref = self.service.get_user_progress_document(uid)
            doc = progress_ref.get()
            current_data = doc.to_dict() if doc.exists else {}
            
            update_data = {
                "last_updated": datetime.now(timezone.utc)
            }
            
            # Merge weaknesses
            if weaknesses:
                existing_weaknesses = current_data.get("weaknesses", [])
                update_data["weaknesses"] = self.service.merge_weaknesses(existing_weaknesses, weaknesses)
            
            if recommendation:
                update_data["weakness_recommendation"] = recommendation
            
            self.service.update_user_progress(uid, update_data)
            
            logger.info(f"Updated weaknesses for user {uid}: {len(weaknesses)} areas")
            
            return {
                "success": True,
                "message": "Weaknesses updated successfully",
                "weaknesses": update_data.get("weaknesses", []),
                "weakness_recommendation": update_data.get("weakness_recommendation", "")
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating weaknesses: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update weaknesses"
            )