# models/quiz_models.py
from pydantic import BaseModel, Field
from typing import List

class QuizGenerationPayload(BaseModel):
    uid: str
    topic: str
    num_questions: int = Field(default=5, ge=1, le=20)

class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    rationale: str

class QuizStructure(BaseModel):
    questions: List[QuizQuestion]