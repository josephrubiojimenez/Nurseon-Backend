# controllers/auth_controller.py
from typing import Optional
from datetime import datetime, timezone
import logging
from fastapi import HTTPException, status

from services.auth_service import AuthService
from database.firebase import db

logger = logging.getLogger("auth_controller")

class AuthController:
    def __init__(self):
        self.service = AuthService()

    def login(self, token: str, name: Optional[str] = None):
        decoded_token = self.service.verify_firebase_token(token)
        uid = decoded_token.get("uid") or decoded_token.get("user_id")
        email = decoded_token.get("email")
        
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Login Failed. Please sign in again."
            )
        
        try:
            self.service.get_or_create_user_document(uid, email or "")
        except Exception as e:
            logger.error(f"Cannot create account: {str(e)}")

        logger.info(f"User {uid} successfully authenticated.")
        return {
            "message": "Authenticated successfully",
            "uid": uid,
            "email": email,
            "success": True
        }

    def register(self, token: str, name: Optional[str] = None):
        decoded_token = self.service.verify_firebase_token(token)
        uid = decoded_token.get("uid") or decoded_token.get("user_id")
        email = decoded_token.get("email")
        
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user found."
            )
        
        try:
            self.service.get_or_create_user_document(uid, email or "", name)
        except Exception as e:
            logger.error(f"Cannot create account: {str(e)}")

        logger.info(f"User {uid} record secured.")
        return {
            "message": "Secure",
            "uid": uid,
            "email": email,
            "success": True
        }

    def get_user_profile(self, uid: str):
        try:
            email = self.service.get_user_email_from_firebase(uid)
            
            user_ref = self.service.get_user_document(uid)
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
            logger.error(f"User not Found: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get user profile"
            )

    def update_user_profile(self, uid: str, username: Optional[str] = None, password: Optional[str] = None):
        try:
            user_ref = self.service.get_user_document(uid)
            doc = user_ref.get()
            
            update_data = {}
            
            if username is not None:
                if len(username) < 3 or len(username) > 30:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Username must be between 3 and 30 characters"
                    )
                if not username.replace('_', '').isalnum():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Username must contain only letters, numbers, and underscores"
                    )
                update_data["username"] = username
            
            if password is not None:
                if len(password) < 6:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Password must be at least 6 characters"
                    )
                try:
                    firebase_auth.update_user(
                        uid,
                        password=password
                    )
                except Exception as e:
                    logger.error(f"Error updating password: {str(e)}")
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
                    email = self.service.get_user_email_from_firebase(uid)
                    update_data["uid"] = uid
                    update_data["email"] = email or ""
                    update_data["created_at"] = datetime.now(timezone.utc)
                    user_ref.set(update_data)
            
            # Get updated user data
            updated_doc = user_ref.get()
            updated_data = updated_doc.to_dict() if updated_doc.exists else {}
            
            # Get email from Firebase
            email = self.service.get_user_email_from_firebase(uid)
            
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
            logger.error(f"Cannot update profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user profile"
            )

    def delete_user_account(self, uid: str):
        try:
            # Delete from Firebase Auth
            try:
                firebase_auth.delete_user(uid)
            except Exception as e:
                logger.error(f"Cannot delete this account: {str(e)}")
            
            # Delete from Firestore
            user_ref = self.service.get_user_document(uid)
            user_ref.delete()
            
            # Also delete user progress
            progress_ref = self.service.get_user_progress_document(uid)
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