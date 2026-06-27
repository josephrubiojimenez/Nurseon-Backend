from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
import firebase_admin
from firebase_admin import auth as firebase_auth
import logging

logger = logging.getLogger("auth")
auth_router = APIRouter()

class AuthPayload(BaseModel):
    token: str
    name: Optional[str] = None

class AuthResponse(BaseModel):
    message: str
    uid: str
    email: Optional[EmailStr] = None
    success: bool


def verify_firebase_token(id_token: str) -> dict:
    try:
        return firebase_auth.verify_id_token(id_token)
    except firebase_admin.auth.ExpiredIdTokenError:
        logger.warning("Failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Sign in again."
        )
    except firebase_admin.auth.InvalidIdTokenError:
        logger.warning("Failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication."
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication error."
        )

@auth_router.post("/login", response_model=AuthResponse)
async def login(payload: AuthPayload):
    decoded_token = verify_firebase_token(payload.token)
    
    uid = decoded_token.get("uid") or decoded_token.get("user_id")
    email = decoded_token.get("email")
    
    if not uid:
       raise HTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           detail="User identification failed. Please sign in again."
       )

    logger.info(f"User {uid} successfully authenticated.")
    return AuthResponse(
        message="Authenticated successfully",
        uid=uid,
        email=email,
        success=True
    )


@auth_router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: AuthPayload):
    decoded_token = verify_firebase_token(payload.token)
    
    uid = decoded_token.get("uid") or decoded_token.get("user_id")
    email = decoded_token.get("email")
    
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user found."
        )

    logger.info(f"User {uid} record secured.")
    return AuthResponse(
        message="Secure",
        uid=uid,
        email=email,
        success=True
    )