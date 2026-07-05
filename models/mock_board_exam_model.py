# models/mock_board_exam_models.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class QuestionOptionSchema(BaseModel):
    A: str
    B: str
    C: str
    D: str

class QuestionSchema(BaseModel):
    id: str
    question: str
    options: QuestionOptionSchema
    correct_answer: str
    rationale: str

class UnifiedExamResponseSchema(BaseModel):
    questions: List[QuestionSchema]

class StartExamRequest(BaseModel):
    uid: str

class SubmitExamRequest(BaseModel):
    uid: str
    exam_id: str
    answers: Dict[str, str]

class SubmitAnswerRequest(BaseModel):
    uid: str
    exam_id: str
    question_index: int
    answer: str

class AdvancePhaseRequest(BaseModel):
    uid: str
    exam_id: str