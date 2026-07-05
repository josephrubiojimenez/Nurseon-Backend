# routes/mock_board_exam.py
from fastapi import APIRouter, HTTPException, status, Request

from models.mock_board_exam_models import StartExamRequest, SubmitExamRequest, SubmitAnswerRequest, AdvancePhaseRequest
from controllers.mock_board_exam_controller import MockBoardExamController
from route.nurseon_ai_chat import limiter

logger = logging.getLogger("mock_board_exam")
mock_board_exam_router = APIRouter()
controller = MockBoardExamController()

@mock_board_exam_router.get("/status/{uid}", status_code=status.HTTP_200_OK)
async def get_exam_status(uid: str):
    return controller.get_exam_status(uid)

@mock_board_exam_router.post("/start", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def start_mock_exam(request: Request, payload: StartExamRequest):
    return controller.start_mock_exam(payload.uid)

@mock_board_exam_router.post("/submit-answer", status_code=status.HTTP_200_OK)
async def submit_answer(payload: SubmitAnswerRequest):
    return controller.submit_answer(payload.uid, payload.exam_id, payload.question_index, payload.answer)

@mock_board_exam_router.post("/advance-phase", status_code=status.HTTP_200_OK)
async def advance_phase(payload: AdvancePhaseRequest):
    return controller.advance_phase(payload.uid, payload.exam_id)

@mock_board_exam_router.post("/resume", status_code=status.HTTP_200_OK)
async def resume_exam(payload: AdvancePhaseRequest):
    return controller.resume_exam(payload.uid, payload.exam_id)

@mock_board_exam_router.post("/submit", status_code=status.HTTP_200_OK)
async def submit_mock_exam(payload: SubmitExamRequest):
    return controller.submit_mock_exam(payload.uid, payload.exam_id, payload.answers)

@mock_board_exam_router.post("/limit-status", status_code=status.HTTP_200_OK)
async def get_mock_exam_limit_status(payload: dict):
    return controller.get_mock_exam_limit_status(payload.get("uid"))

@mock_board_exam_router.get("/results/{uid}/{exam_id}", status_code=status.HTTP_200_OK)
async def get_exam_results(uid: str, exam_id: str):
    return controller.get_exam_results(uid, exam_id)

@mock_board_exam_router.get("/questions/{exam_id}", status_code=status.HTTP_200_OK)
async def get_exam_questions(exam_id: str):
    return controller.get_exam_questions(exam_id)