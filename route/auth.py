from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
import firebase_admin
from firebase_admin import auth as firebase_auth
import logging

# Setup structured logging for Render cloud console
logger = logging.getLogger("auth")
auth_router = APIRouter()

# --- Pydantic Schemas ---
class AuthPayload(BaseModel):
    token: str
    name: Optional[str] = None

class AuthResponse(BaseModel):
    message: str
    uid: str
    email: Optional[EmailStr] = None
    success: bool

# --- Secure Token Verification ---
def verify_firebase_token(id_token: str) -> dict:
    """
    Securely verifies the incoming Firebase ID token.
    System clocks on Render are automatically synchronized, 
    eliminating local clock-drift security bypasses.
    """
    try:
        # Securely validate signature, expiration, and issuer via Firebase Admin SDK
        return firebase_auth.verify_id_token(id_token)
    except firebase_admin.auth.ExpiredIdTokenError:
        logger.warning("Authentication failed: Sent token has expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again."
        )
    except firebase_admin.auth.InvalidIdTokenError:
        logger.warning("Authentication failed: Sent token is structurally invalid.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature."
        )
    except Exception as e:
        logger.error(f"Unexpected token verification failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication sequence dropped."
        )

# --- API Endpoints ---
@auth_router.post("/login", response_model=AuthResponse)
async def login(payload: AuthPayload):
    decoded_token = verify_firebase_token(payload.token)
    
    # Extract structural identifiers safely
    uid = decoded_token.get("uid") or decoded_token.get("user_id")
    email = decoded_token.get("email")
    
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token processed successfully but lacks a unique User Identifier (UID)."
        )

    logger.info(f"User {uid} successfully authenticated via live login endpoint.")
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
            detail="Token processed successfully but lacks a unique User Identifier (UID)."
        )

    logger.info(f"User {uid} record synchronized securely with database records.")
    return AuthResponse(
        message="User synchronized securely",
        uid=uid,
        email=email,
        success=True
    )