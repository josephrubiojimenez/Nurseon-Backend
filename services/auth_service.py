# services/auth_service.py
from typing import Optional
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import auth as firebase_auth
import logging
from fastapi import HTTPException, status

from database.firebase import db

logger = logging.getLogger("auth_service")

class AuthService:
    @staticmethod
    def verify_firebase_token(id_token: str) -> dict:
        try:
            return firebase_auth.verify_id_token(id_token)
        except firebase_admin.auth.ExpiredIdTokenError:
            logger.warning("Verification Failed. Please Try Again!")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Sign in again."
            )
        except firebase_admin.auth.InvalidIdTokenError:
            logger.warning("Verification Failed. Please Try Again!")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication."
            )
        except Exception as e:
            logger.error(f"Error during verification: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication error."
            )

    @staticmethod
    def get_user_email_from_firebase(uid: str) -> Optional[str]:
        try:
            user_record = firebase_auth.get_user(uid)
            return user_record.email
        except Exception as e:
            logger.error(f"User not Found: {str(e)}")
            return None

    @staticmethod
    def get_or_create_user_document(uid: str, email: str, username: Optional[str] = None) -> dict:
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

    @staticmethod
    def update_firebase_password(uid: str, password: str) -> bool:
        try:
            firebase_auth.update_user(uid, password=password)
            return True
        except Exception as e:
            logger.error(f"Error updating password: {str(e)}")
            return False

    @staticmethod
    def delete_firebase_user(uid: str) -> bool:
        try:
            firebase_auth.delete_user(uid)
            return True
        except Exception as e:
            logger.error(f"Cannot delete this account: {str(e)}")
            return False

    @staticmethod
    def get_user_document(uid: str):
        return db.collection("users_auth").document(uid)

    @staticmethod
    def get_user_progress_document(uid: str):
        return db.collection("user_progress").document(uid)