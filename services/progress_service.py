# services/progress_service.py
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status

from database.firebase import db

logger = logging.getLogger("progress_service")

# Configuration Constants
MAX_CASE_STUDY_POINTS = 100
MAX_QUIZ_ITEMS = 50

# Difficulty points mapping
DIFFICULTY_POINTS = {
    "Easy": 10,
    "Standard": 20,
    "Hard": 30
}

class ProgressService:
    @staticmethod
    def get_user_progress_document(uid: str):
        return db.collection("user_progress").document(uid)

    @staticmethod
    def get_default_progress():
        return {
            "quizzesAnswered": 0,
            "totalQuizzes": 50,
            "caseStudyPoints": 0,
            "maxCaseStudyPoints": MAX_CASE_STUDY_POINTS,
            "caseProgressPercent": 0,
            "mockExamsTaken": 0,
            "totalMockExams": 1,
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

    @staticmethod
    def calculate_study_streak(current_data: dict, today_datetime: datetime) -> int:
        last_study_date = current_data.get("last_study_date")
        today_date = today_datetime.date()
        
        if last_study_date:
            last_date = last_study_date.date() if hasattr(last_study_date, 'date') else last_study_date
            if isinstance(last_date, datetime):
                last_date = last_date.date()
            
            days_diff = (today_date - last_date).days
            if days_diff == 1:
                return current_data.get("study_streak", 0) + 1
            elif days_diff > 1:
                return 1
        return 1

    @staticmethod
    def calculate_quiz_progress(current_correct_pool: int, correct_items_added: int) -> int:
        new_correct_pool = current_correct_pool + correct_items_added
        if new_correct_pool > MAX_QUIZ_ITEMS:
            new_correct_pool = MAX_QUIZ_ITEMS
        return new_correct_pool

    @staticmethod
    def merge_weaknesses(existing_weaknesses: List[Dict], new_weaknesses: List[Dict]) -> List[Dict]:
        if not existing_weaknesses:
            return new_weaknesses
        
        subject_map = {}
        for w in existing_weaknesses:
            subject_map[w.get("subject")] = w
        for w in new_weaknesses:
            subject_map[w.get("subject")] = w
        return list(subject_map.values())

    @staticmethod
    def get_user_progress(uid: str):
        progress_ref = ProgressService.get_user_progress_document(uid)
        doc = progress_ref.get()
        
        if not doc.exists:
            return None
        
        return doc.to_dict()

    @staticmethod
    def update_user_progress(uid: str, update_data: dict):
        progress_ref = ProgressService.get_user_progress_document(uid)
        progress_ref.set(update_data, merge=True)

    @staticmethod
    def calculate_case_study_points(difficulty: str, score: float) -> int:
        if score >= 75:
            return DIFFICULTY_POINTS.get(difficulty, 20)
        return 0

    @staticmethod
    def calculate_overall_accuracy(case_study_scores: List[float], quiz_scores: List[float]) -> float:
        avg_case_score = round(sum(case_study_scores) / len(case_study_scores), 2) if case_study_scores else 0
        avg_quiz_score = round(sum(quiz_scores) / len(quiz_scores), 2) if quiz_scores else 0
        
        if case_study_scores and quiz_scores:
            return round((avg_case_score + avg_quiz_score) / 2, 2)
        elif case_study_scores:
            return avg_case_score
        elif quiz_scores:
            return avg_quiz_score
        return 0