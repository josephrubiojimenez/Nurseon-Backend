# models/progress_models.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class UpdateCaseStudyPayload(BaseModel):
    uid: str
    difficulty: str = "Standard"
    score: Optional[float] = 0

class UpdateQuizPayload(BaseModel):
    uid: str
    score: Optional[float] = None
    correct_count: Optional[int] = None
    questions_answered: int = 20

class UpdateMockExamPayload(BaseModel):
    uid: str
    score: float = 0
    weaknesses: List[Dict[str, Any]] = []
    recommendation: str = ""

class UpdateWeaknessesPayload(BaseModel):
    uid: str
    weaknesses: List[Dict[str, Any]] = []
    recommendation: str = ""