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
                "slotsRemaining": 5,
                "used": 0,
                "available": True,
                "reset_at": None,
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
        quizzes_answered = data.get("quizzes_answered", 0)
        
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
        
        # Get weaknesses from data, ensure it's a list
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
            "maxCaseStudyPoints": MAX_CASE_STUDY_POINTS,
            "caseProgressPercent": case_progress_percent,
            "mockExamsTaken": data.get("mock_exams_taken", 0),
            "totalMockExams": 5,
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


@progress_router.post("/update-quiz")
async def update_quiz_progress(payload: dict):
    """
    Update progress when a quiz is completed.
    """
    try:
        uid = payload.get("uid")
        score = payload.get("score", 0)
        questions_answered = payload.get("questions_answered", 0)
        
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User UID is required"
            )
        
        progress_ref = db.collection("user_progress").document(uid)
        doc = progress_ref.get()
        current_data = doc.to_dict() if doc.exists else {}
        
        # Prepare update data
        current_answered = current_data.get("quizzes_answered", 0)
        update_data = {
            "quizzes_answered": current_answered + questions_answered,
            "last_updated": datetime.now(timezone.utc)
        }
        
        # Add quiz score
        if score > 0:
            quiz_scores = current_data.get("quiz_scores", [])
            quiz_scores.append(score)
            update_data["quiz_scores"] = quiz_scores
            
            # Update average quiz score
            if quiz_scores:
                update_data["average_quiz_score"] = round(sum(quiz_scores) / len(quiz_scores), 2)
        
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
        
        # Update time spent (10 minutes per quiz)
        update_data["time_spent_hours"] = current_data.get("time_spent_hours", 0) + 0.17
        
        # Commit update
        progress_ref.set(update_data, merge=True)
        
        logger.info(f"✅ Updated quiz progress for user {uid}: +{questions_answered} questions, score: {score}%")
        
        return {
            "success": True,
            "message": "Quiz progress updated successfully",
            "quizzes_answered": update_data["quizzes_answered"],
            "average_quiz_score": update_data.get("average_quiz_score", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating quiz progress: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update quiz progress"
        )


@progress_router.post("/update-mock-exam")
async def update_mock_exam_progress(payload: dict):
    """
    Update progress when a mock exam is completed.
    Also updates weaknesses and recommendations.
    """
    try:
        uid = payload.get("uid")
        score = payload.get("score", 0)
        weaknesses = payload.get("weaknesses", [])
        recommendation = payload.get("recommendation", "")
        
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User UID is required"
            )
        
        progress_ref = db.collection("user_progress").document(uid)
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
            
            # Update overall board score (average)
            board_scores = current_data.get("board_scores", [])
            board_scores.append(score)
            update_data["board_scores"] = board_scores
            
            if board_scores:
                update_data["overall_board_score"] = round(sum(board_scores) / len(board_scores), 2)
        
        # Update weaknesses if provided
        if weaknesses:
            # Merge with existing weaknesses or replace
            existing_weaknesses = current_data.get("weaknesses", [])
            if existing_weaknesses:
                # Combine and deduplicate by subject
                subject_map = {}
                for w in existing_weaknesses:
                    subject_map[w.get("subject")] = w
                for w in weaknesses:
                    subject_map[w.get("subject")] = w
                update_data["weaknesses"] = list(subject_map.values())
            else:
                update_data["weaknesses"] = weaknesses
        
        # Update recommendation if provided
        if recommendation:
            update_data["weakness_recommendation"] = recommendation
        
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
        
        # Update time spent (1 hour per mock exam)
        update_data["time_spent_hours"] = current_data.get("time_spent_hours", 0) + 1
        
        # Commit update
        progress_ref.set(update_data, merge=True)
        
        logger.info(f"✅ Updated mock exam progress for user {uid}: score: {score}%, weaknesses: {len(weaknesses)} areas")
        
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


@progress_router.post("/update-weaknesses")
async def update_weaknesses(payload: dict):
    """
    Update weaknesses and recommendations for a user.
    This can be called separately after exam analysis.
    """
    try:
        uid = payload.get("uid")
        weaknesses = payload.get("weaknesses", [])
        recommendation = payload.get("recommendation", "")
        
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User UID is required"
            )
        
        progress_ref = db.collection("user_progress").document(uid)
        doc = progress_ref.get()
        current_data = doc.to_dict() if doc.exists else {}
        
        update_data = {
            "last_updated": datetime.now(timezone.utc)
        }
        
        # Merge weaknesses
        if weaknesses:
            existing_weaknesses = current_data.get("weaknesses", [])
            if existing_weaknesses:
                # Combine and deduplicate by subject
                subject_map = {}
                for w in existing_weaknesses:
                    subject_map[w.get("subject")] = w
                for w in weaknesses:
                    subject_map[w.get("subject")] = w
                update_data["weaknesses"] = list(subject_map.values())
            else:
                update_data["weaknesses"] = weaknesses
        
        if recommendation:
            update_data["weakness_recommendation"] = recommendation
        
        progress_ref.set(update_data, merge=True)
        
        logger.info(f"✅ Updated weaknesses for user {uid}: {len(weaknesses)} areas")
        
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