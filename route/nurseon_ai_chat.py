# routes/nurseon_ai_chat.py
import logging
from fastapi import APIRouter, HTTPException, status, Request

from models.nurseon_ai_chat_models import ChatPayload, RenamePayload
from controllers.nurseon_ai_chat_controller import NurseonAIChatController
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger("nurseon_ai_chat")
nurseon_ai_chat_router = APIRouter()
controller = NurseonAIChatController()

limiter = Limiter(key_func=get_remote_address)

@nurseon_ai_chat_router.post("/chat", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def process_nurseon_chat(request: Request, payload: ChatPayload):
    return controller.process_chat(payload.uid, payload.message, payload.session_id, payload.history)

@nurseon_ai_chat_router.post("/limit-check", status_code=status.HTTP_200_OK)
async def check_chat_limits(payload: dict):
    return controller.check_limits(payload.get("uid"))

@nurseon_ai_chat_router.get("/history/{uid}", status_code=status.HTTP_200_OK)
async def get_chat_history(uid: str):
    return controller.get_chat_history(uid)

@nurseon_ai_chat_router.get("/history/{uid}/{session_id}", status_code=status.HTTP_200_OK)
async def get_single_session(uid: str, session_id: str):
    return controller.get_single_session(uid, session_id)

@nurseon_ai_chat_router.put("/history/{uid}/{session_id}/pin", status_code=status.HTTP_200_OK)
async def toggle_pin_status(uid: str, session_id: str, payload: dict):
    return controller.toggle_pin(uid, session_id, payload.get("pinned", False))

@nurseon_ai_chat_router.put("/history/{uid}/{session_id}/rename", status_code=status.HTTP_200_OK)
async def rename_session_thread(uid: str, session_id: str, payload: RenamePayload):
    return controller.rename_session(uid, session_id, payload.title)

@nurseon_ai_chat_router.delete("/history/{uid}/{session_id}", status_code=status.HTTP_200_OK)
async def delete_session_thread(uid: str, session_id: str):
    return controller.delete_session(uid, session_id)

@nurseon_ai_chat_router.post("/history/{uid}/{session_id}/restore", status_code=status.HTTP_200_OK)
async def restore_session_thread(uid: str, session_id: str, payload: dict):
    return controller.restore_session(uid, session_id, payload.get("item", {}))