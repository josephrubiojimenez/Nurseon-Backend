# routes/quiz.py
import logging
from fastapi import APIRouter, HTTPException, status

from models.quiz_models import QuizGenerationPayload
from controllers.quiz_controller import QuizController

logger = logging.getLogger("quiz_router")
quiz_router = APIRouter()
controller = QuizController()

@quiz_router.get("/usage/{uid}")
async def get_user_usage(uid: str):
    """Get the current quiz usage and limits for a user."""
    return controller.get_user_usage(uid)

@quiz_router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_quiz(payload: QuizGenerationPayload):
    return controller.generate_quiz(payload.uid, payload.topic, payload.num_questions)