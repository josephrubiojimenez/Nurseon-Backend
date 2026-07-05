# services/smart_notes_service.py
import os
import logging
import hashlib
from datetime import datetime, timezone
from fastapi import HTTPException, status
import google.generativeai as genai

from database.firebase import db

logger = logging.getLogger("smart_notes_service")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class SmartNotesService:
    @staticmethod
    def run_gemini_ai_summary_native(file_bytes: bytes, mime_type: str, custom_instruction: str = "") -> str:
        if not GEMINI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI Service is currently unconfigured."
            )

        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
        except Exception as model_err:
            logger.error(f"Failed to initialize Gemini model: {model_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI Service initialization failed."
            )

        system_prompt = (
            "You are an expert Nursing and Medical Education Assistant. Your job is to transform "
            "the uploaded medical content, textbook page, or document into beautiful, structured, "
            "high-yield 'Smart Notes' formatted in professional Markdown. Focus on core concepts, "
            "definitions, clinical signs, and nursing interventions where applicable.\n\n"
        )
        
        if custom_instruction.strip():
            system_prompt += f"CRITICAL FOCUS AREA requested by user: \"{custom_instruction}\"\n\n"
            
        user_prompt = "Please process this attached document source file into comprehensive study material."

        try:
            logger.info("Preparing file asset structure in-memory...")
            file_part = {
                "mime_type": mime_type,
                "data": file_bytes
            }
            
            logger.info("Generating content with Gemini...")
            response = model.generate_content([system_prompt + user_prompt, file_part])
            
            if not response.text:
                return "Failed to generate structured text. Please try uploading a different section."
                
            return response.text
            
        except Exception as ai_err:
            error_msg = str(ai_err).lower()
            logger.error(f"Gemini API Error: {str(ai_err)}", exc_info=True)
            
            if "429" in error_msg or "quota" in error_msg or "rate_limit" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="The AI rate limit has been reached. Please wait a moment and try again."
                )
            elif "timeout" in error_msg or "deadline" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="The AI server timed out. Please try again in a moment."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="AI Service encountered an unexpected processing error."
                )

    @staticmethod
    def get_mime_type(filename: str) -> str:
        mime_mapping = {
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.jfif': 'image/jpeg'
        }
        file_ext = os.path.splitext(filename.lower())[1]
        return mime_mapping.get(file_ext)

    @staticmethod
    def is_supported_file(filename: str) -> bool:
        mime_mapping = {
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.jfif': 'image/jpeg'
        }
        file_ext = os.path.splitext(filename.lower())[1]
        return file_ext in mime_mapping

    @staticmethod
    def get_cache_document(fingerprint: str):
        return db.collection("smart_notes_cache").document(fingerprint).get()

    @staticmethod
    def save_cache_document(fingerprint: str, data: dict):
        db.collection("smart_notes_cache").document(fingerprint).set(data)

    @staticmethod
    def save_smart_note(data: dict):
        doc_ref = db.collection("smart_notes").document()
        doc_ref.set(data)
        return doc_ref.id

    @staticmethod
    def save_user_history(data: dict):
        db.collection("smart_notes").document().set(data)