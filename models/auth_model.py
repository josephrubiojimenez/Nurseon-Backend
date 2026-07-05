# models/auth_models.py
from pydantic import BaseModel, EmailStr
from typing import Optional

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