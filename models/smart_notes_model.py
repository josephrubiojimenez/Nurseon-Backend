# models/smart_notes_models.py
from pydantic import BaseModel
from typing import Optional

class SmartNotesLimitStatusPayload(BaseModel):
    uid: str

class SmartNotesSummarizePayload(BaseModel):
    uid: str
    instruction: str = ""