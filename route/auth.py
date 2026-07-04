from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import auth as firebase_auth
import logging


from route.nurseon_ai_chat import limiter
from database.firebase import db

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

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None

class UserProfileResponse(BaseModel):
    status: str
    user: dict


def verify_firebase_token(id_token: str) -> dict:
    try:
        return firebase_auth.verify_id_token(id_token)
    except firebase_admin.auth.ExpiredIdTokenError:
        logger.warning("Token verification failed: ExpiredIdTokenError")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Sign in again."
        )
    except firebase_admin.auth.InvalidIdTokenError:
        logger.warning("Token verification failed: InvalidIdTokenError")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication."
        )
    except Exception as e:
        logger.error(f"Error during token verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication error."
        )


def get_user_email_from_firebase(uid: str) -> Optional[str]:
    """Get user email from Firebase Auth."""
    try:
        user_record = firebase_auth.get_user(uid)
        return user_record.email
    except Exception as e:
        logger.error(f"Error getting user from Firebase: {str(e)}")
        return None


def get_or_create_user_document(uid: str, email: str, username: Optional[str] = None) -> dict:
    """Get or create user document in Firestore."""
    user_ref = db.collection("users_auth").document(uid)
    doc = user_ref.get()
    
    if doc.exists:
        data = doc.to_dict()
        return data
    else:
        # Create user document
        user_data = {
            "uid": uid,
            "username": username or email.split('@')[0] if email else uid[:8],
            "email": email or "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        user_ref.set(user_data)
        return user_data


@auth_router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(request: Request, payload: AuthPayload):
    decoded_token = verify_firebase_token(payload.token)
    uid = decoded_token.get("uid") or decoded_token.get("user_id")
    email = decoded_token.get("email")
    
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User identification failed. Please sign in again."
        )
    
    # Ensure user document exists
    try:
        get_or_create_user_document(uid, email or "")
    except Exception as e:
        logger.error(f"Error creating user document: {str(e)}")

    logger.info(f"User {uid} successfully authenticated.")
    return AuthResponse(
        message="Authenticated successfully",
        uid=uid,
        email=email,
        success=True
    )


@auth_router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register(request: Request, payload: AuthPayload):
    decoded_token = verify_firebase_token(payload.token)
    uid = decoded_token.get("uid") or decoded_token.get("user_id")
    email = decoded_token.get("email")
    name = payload.name
    
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user found."
        )
    
    # Create user document with name if provided
    try:
        get_or_create_user_document(uid, email or "", name)
    except Exception as e:
        logger.error(f"Error creating user document: {str(e)}")

    logger.info(f"User {uid} record secured.")
    return AuthResponse(
        message="Secure",
        uid=uid,
        email=email,
        success=True
    )


@auth_router.get("/profile/{uid}")
async def get_user_profile(uid: str):
    """Get user profile by UID."""
    try:
        # Get email from Firebase Auth
        email = get_user_email_from_firebase(uid)
        
        # Get user data from Firestore
        user_ref = db.collection("users_auth").document(uid)
        doc = user_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            return {
                "status": "success",
                "user": {
                    "uid": uid,
                    "username": data.get("username", email or ""),
                    "email": email or data.get("email", ""),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at")
                }
            }
        else:
            # Create user document if it doesn't exist
            user_data = {
                "uid": uid,
                "username": email.split('@')[0] if email else uid[:8],
                "email": email or "",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            user_ref.set(user_data)
            return {
                "status": "success",
                "user": {
                    "uid": uid,
                    "username": user_data["username"],
                    "email": email or "",
                    "created_at": user_data["created_at"],
                    "updated_at": user_data["updated_at"]
                }
            }
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )


@auth_router.put("/profile/{uid}")
async def update_user_profile(uid: str, payload: UserUpdate):
    """Update user profile."""
    try:
        user_ref = db.collection("users_auth").document(uid)
        doc = user_ref.get()
        
        update_data = {}
        
        # Update username if provided
        if payload.username is not None:
            # Validate username
            if len(payload.username) < 3 or len(payload.username) > 30:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username must be between 3 and 30 characters"
                )
            if not payload.username.replace('_', '').isalnum():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username must contain only letters, numbers, and underscores"
                )
            update_data["username"] = payload.username
        
        # Update password in Firebase Auth if provided
        if payload.password is not None:
            if len(payload.password) < 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password must be at least 6 characters"
                )
            try:
                firebase_auth.update_user(
                    uid,
                    password=payload.password
                )
            except Exception as e:
                logger.error(f"Error updating Firebase password: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update password. Please try again."
                )
        
        if update_data:
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            if doc.exists:
                user_ref.update(update_data)
            else:
                # Create document if it doesn't exist
                email = get_user_email_from_firebase(uid)
                update_data["uid"] = uid
                update_data["email"] = email or ""
                update_data["created_at"] = datetime.now(timezone.utc)
                user_ref.set(update_data)
        
        # Get updated user data
        updated_doc = user_ref.get()
        updated_data = updated_doc.to_dict() if updated_doc.exists else {}
        
        # Get email from Firebase
        email = get_user_email_from_firebase(uid)
        
        return {
            "status": "success",
            "user": {
                "uid": uid,
                "username": updated_data.get("username", email.split('@')[0] if email else uid[:8]),
                "email": email or updated_data.get("email", ""),
                "created_at": updated_data.get("created_at"),
                "updated_at": updated_data.get("updated_at")
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user profile"
        )


@auth_router.delete("/profile/{uid}")
async def delete_user_account(uid: str):
    """Delete user account."""
    try:
        # Delete from Firebase Auth
        try:
            firebase_auth.delete_user(uid)
        except Exception as e:
            logger.error(f"Error deleting user from Firebase: {str(e)}")
            # Continue with Firestore deletion even if Firebase deletion fails
        
        # Delete from Firestore
        user_ref = db.collection("users_auth").document(uid)
        user_ref.delete()
        
        # Also delete user progress
        progress_ref = db.collection("user_progress").document(uid)
        progress_ref.delete()
        
        return {
            "status": "success",
            "message": "Account deleted successfully"
        }
    except Exception as e:
        logger.error(f"Error deleting account: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )