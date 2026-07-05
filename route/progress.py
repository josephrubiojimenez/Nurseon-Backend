# routes/progress.py
import logging
from fastapi import APIRouter, HTTPException, status

from models.progress_models import UpdateCaseStudyPayload, UpdateQuizPayload, UpdateMockExamPayload, UpdateWeaknessesPayload
from controllers.progress_controller import ProgressController

logger = logging.getLogger("progress_router")
progress_router = APIRouter()
controller = ProgressController()

@progress_router.get("/{uid}")
async def get_user_progress(uid: str):
    return controller.get_user_progress(uid)

@progress_router.post("/update-case-study")
async def update_case_study_progress(payload: UpdateCaseStudyPayload):
    return controller.update_case_study_progress(payload.uid, payload.difficulty, payload.score)

@progress_router.post("/update-quiz")
async def update_quiz_progress(payload: UpdateQuizPayload):
    return controller.update_quiz_progress(
        payload.uid, 
        payload.score, 
        payload.correct_count, 
        payload.questions_answered
    )

@progress_router.post("/update-mock-exam")
async def update_mock_exam_progress(payload: UpdateMockExamPayload):
    return controller.update_mock_exam_progress(
        payload.uid, 
        payload.score, 
        payload.weaknesses, 
        payload.recommendation
    )

@progress_router.post("/update-weaknesses")
async def update_weaknesses(payload: UpdateWeaknessesPayload):
    return controller.update_weaknesses(payload.uid, payload.weaknesses, payload.recommendation)