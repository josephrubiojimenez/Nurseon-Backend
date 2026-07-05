# routes/auth.py
from fastapi import APIRouter, HTTPException, status, Request
import logging

from models.auth_models import AuthPayload, AuthResponse, UserUpdate
from controllers.auth_controller import AuthController
from route.nurseon_ai_chat import limiter

logger = logging.getLogger("auth")
auth_router = APIRouter()
controller = AuthController()

@auth_router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(request: Request, payload: AuthPayload):
    result = controller.login(payload.token, payload.name)
    return AuthResponse(**result)

@auth_router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register(request: Request, payload: AuthPayload):
    result = controller.register(payload.token, payload.name)
    return AuthResponse(**result)

@auth_router.get("/profile/{uid}")
async def get_user_profile(uid: str):
    return controller.get_user_profile(uid)

@auth_router.put("/profile/{uid}")
async def update_user_profile(uid: str, payload: UserUpdate):
    return controller.update_user_profile(uid, payload.username, payload.password)

@auth_router.delete("/profile/{uid}")
async def delete_user_account(uid: str):
    return controller.delete_user_account(uid)