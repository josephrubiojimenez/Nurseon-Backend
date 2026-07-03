from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timezone
import logging

from database.firebase import db
from utils.limiters import check_rate_limit_status

logger = logging.getLogger("progress_router")
progress_router = APIRouter()

# Configuration Constants
MAX_CASE_STUDY_POINTS = 100  # Maximum points to reach 100% progress

# Difficulty points mapping
DIFFICULTY_POINTS = {
    "Easy": 10,
    "Standard": 20,
    "Hard": 30
}

@progress_router.get("/{uid}")
async def get_user_progress(uid: str):
    """
    Get user progress metrics including case studies, quizzes, and mock exams.
    """
    try:
        progress_ref = db.collection("user_progress").document(uid)
        doc = progress_ref.get()
        
        if not doc.exists:
            # Return default progress for new users
            return {
                "quizzesAnswered": 0,
                "totalQuizzes": 50,
                "caseStudyPoints": 0,
                "maxCaseStudyPoints": MAX_CASE_STUDY_POINTS,
                "caseProgressPercent": 0,
                "mockExamsTaken": 0,
                "totalMockExams": 5,
                "overallAccuracy": 0,
                "latestBoardScore": 0,
                "overallBoardScore": 0,
                "studyStreak": 0,
                "timeSpentHours": 0,
                "weaknesses": [],
                "weaknessRecommendation": "Complete more activities to get personalized insights"
            }
        
        data = doc.to_dict()
        
        # Get case study points
        case_study_points = data.get("total_case_study_points", 0)
        
        # Calculate progress percentage (cap at 100%)
        case_progress_percent = min(100, round((case_study_points / MAX_CASE_STUDY_POINTS) * 100))
        
        # Get quiz data
        quiz_scores = data.get("quiz_scores", [])
        avg_quiz_score = round(sum(quiz_scores) / len(quiz_scores), 2) if quiz_scores else 0
        
        # Get case study scores for accuracy
        case_study_scores = data.get("case_study_scores", [])
        avg_case_score = round(sum(case_study_scores) / len(case_study_scores), 2) if case_study_scores else 0
        
        # Calculate overall accuracy (weighted average)
        if case_study_scores and quiz_scores:
            overall_accuracy = round((avg_case_score + avg_quiz_score) / 2, 2)
        elif case_study_scores:
            overall_accuracy = avg_case_score
        elif quiz_scores:
            overall_accuracy = avg_quiz_score
        else:
            overall_accuracy = 0
        
        # Get case study limit status using the new limiter
        limit_status = check_rate_limit_status(uid, "case_studies", max_limit=5)
        
        return {
            "quizzesAnswered": data.get("quizzes_answered", 0),
            "totalQuizzes": 50,
            "caseStudyPoints": case_study_points,
            "maxCaseStudyPoints": MAX_CASE_STUDY_POINTS,
            "caseProgressPercent": case_progress_percent,
            "mockExamsTaken": data.get("mock_exams_taken", 0),
            "totalMockExams": 5,
            "overallAccuracy": overall_accuracy,
            "latestBoardScore": data.get("latest_board_score", 0),
            "overallBoardScore": data.get("overall_board_score", 0),
            "studyStreak": data.get("study_streak", 0),
            "timeSpentHours": data.get("time_spent_hours", 0),
            "dailyLimitRemaining": limit_status.get("remaining", 5),
            "weaknesses": data.get("weaknesses", []),
            "weaknessRecommendation": data.get("weakness_recommendation", 
                "Keep studying and complete more case studies to identify weak areas!")
        }
        
    except Exception as e:
        logger.error(f"Error fetching progress for user {uid}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch progress data"
        )


@progress_router.post("/update-case-study")
async def update_case_study_progress(payload: dict):
    """
    Update progress when a case study is completed.
    """
    try:
        uid = payload.get("uid")
        difficulty = payload.get("difficulty", "Standard")
        score = payload.get("score")
        
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User UID is required"
            )
        
        progress_ref = db.collection("user_progress").document(uid)
        doc = progress_ref.get()
        current_data = doc.to_dict() if doc.exists else {}
        
        # Get points for difficulty
        points = DIFFICULTY_POINTS.get(difficulty, 20)
        
        # Calculate new total points
        current_points = current_data.get("total_case_study_points", 0)
        new_points = current_points + points
        
        # Prepare update data
        update_data = {
            "total_case_study_points": new_points,
            "last_updated": datetime.now(timezone.utc)
        }
        
        # Add score if provided
        if score is not None:
            scores = current_data.get("case_study_scores", [])
            scores.append(score)
            update_data["case_study_scores"] = scores
            
            # Update average score
            if scores:
                update_data["average_case_study_score"] = round(sum(scores) / len(scores), 2)
        
        # Update study streak
        last_study_date = current_data.get("last_study_date")
        today_datetime = datetime.now(timezone.utc)
        today_date = today_datetime.date()
        
        if last_study_date:
            last_date = last_study_date.date() if hasattr(last_study_date, 'date') else last_study_date
            if isinstance(last_date, datetime):
                last_date = last_date.date()
            
            days_diff = (today_date - last_date).days
            if days_diff == 1:
                update_data["study_streak"] = current_data.get("study_streak", 0) + 1
            elif days_diff > 1:
                update_data["study_streak"] = 1
        else:
            update_data["study_streak"] = 1
        
        update_data["last_study_date"] = today_datetime
        
        # Update time spent (add 15 minutes per case study)
        update_data["time_spent_hours"] = current_data.get("time_spent_hours", 0) + 0.25
        
        # Commit update
        progress_ref.set(update_data, merge=True)
        
        # Calculate progress percentage
        progress_percent = min(100, round((new_points / MAX_CASE_STUDY_POINTS) * 100))
        
        logger.info(f"✅ Updated case study progress for user {uid}: {new_points} points ({progress_percent}%)")
        
        return {
            "success": True,
            "message": "Progress updated successfully",
            "case_study_points": new_points,
            "case_progress_percent": progress_percent
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating case study progress: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update progress"
        )