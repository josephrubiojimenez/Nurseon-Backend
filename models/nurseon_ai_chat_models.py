# models/nurseon_ai_chat_models.py
from pydantic import BaseModel
from typing import List, Optional

class MessageLog(BaseModel):
    role: str
    parts: str

class ChatPayload(BaseModel):
    uid: str
    message: str
    session_id: Optional[str] = None
    history: List[MessageLog] = []

class RenamePayload(BaseModel):
    title: str