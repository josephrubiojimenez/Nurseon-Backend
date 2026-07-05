# routes/smart_notes.py
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status

from controllers.smart_notes_controller import SmartNotesController

logger = logging.getLogger("smart_notes")
smart_notes_router = APIRouter()
controller = SmartNotesController()

@smart_notes_router.post("/limit-status", status_code=status.HTTP_200_OK)
async def get_smart_notes_limit_status(payload: dict):
    return controller.get_limit_status(payload.get("uid"))

@smart_notes_router.post("/summarize", status_code=status.HTTP_200_OK)
async def summarize_document(
    uid: str = Form(...), 
    file: UploadFile = File(...),
    instruction: str = Form("")
):
    return controller.summarize_document(uid, file, instruction)