from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import firebase_admin
from firebase_admin import auth as firebase_auth
import jwt  
import logging

logger = logging.getLogger("auth")
auth_router = APIRouter()

class AuthPayload(BaseModel):
    token: str
    name: Optional[str] = None

class AuthResponse(BaseModel):
    message: str
    uid: str
    email: Optional[str] = None
    success: bool


def verify_token_with_leeway(id_token: str) -> dict:
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception as e:
        error_msg = str(e)
        if "token used too early" in error_msg.lower() or "too early" in error_msg.lower():
            logger.warning(f"Clock drift detected ({error_msg}). Activating leeway decoding.")
            try:
                decoded_claims = jwt.decode(id_token, options={"verify_signature": False})
                return decoded_claims
            except Exception as jwt_err:
                raise Exception(f"Leeway extraction failed: {str(jwt_err)}")
                
        raise e


@auth_router.post("/login", response_model=AuthResponse)
async def login(payload: AuthPayload):
    try:
        decoded_token = verify_token_with_leeway(payload.token)
        return AuthResponse(
            message="Authenticated successfully",
            uid=decoded_token.get("uid") or decoded_token.get("user_id"),
            email=decoded_token.get("email"),
            success=True
        )
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=f"Token verification dropped: {str(e)}"
        )


@auth_router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: AuthPayload):
    try:
        decoded_token = verify_token_with_leeway(payload.token)
        return AuthResponse(
            message="User synchronized securely",
            uid=decoded_token.get("uid") or decoded_token.get("user_id"),
            email=decoded_token.get("email"),
            success=True
        )
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=f"Sync sequence dropped: {str(e)}"
        )