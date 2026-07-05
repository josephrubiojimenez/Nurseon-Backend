# controllers/smart_notes_controller.py
import os
import logging
import hashlib
from datetime import datetime, timezone
from fastapi import HTTPException, status

from services.smart_notes_service import SmartNotesService
from utils.limiters import enforce_feature_limit, check_rate_limit_status

logger = logging.getLogger("smart_notes_controller")

class SmartNotesController:
    def __init__(self):
        self.service = SmartNotesService()

    def get_limit_status(self, uid: str):
        if not uid:
            raise HTTPException(status_code=400, detail="Missing user UID")
        
        limit_status = check_rate_limit_status(uid, "smart_notes", max_limit=2)
        return {
            "status": "success",
            "slots_remaining": limit_status["remaining"],
            "used": limit_status.get("used", 0),
            "available": limit_status["available"],
            "reset_at": limit_status["reset_at"]
        }

    def summarize_document(self, uid: str, file, instruction: str = ""):
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file uploaded. Please select a file."
            )
        
        filename_lower = file.filename.lower()
        
        try:
            file_bytes = file.file.read()
            file_size = len(file_bytes)
            
            if file_size == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded file is empty."
                )
            
            if file_size > 15 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File size is too large for processing. Please upload a smaller portion or segment."
                )
                
        except HTTPException as explicit_http:
            raise explicit_http
        except Exception as read_err:
            logger.error(f"File read error: {read_err}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to safely read the uploaded file data."
            )
        
        if not self.service.is_supported_file(filename_lower):
            mime_mapping = {
                '.pdf': 'application/pdf',
                '.txt': 'text/plain',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.jfif': 'image/jpeg'
            }
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format. Use: {', '.join(mime_mapping.keys())}"
            )

        limit_status = check_rate_limit_status(uid, "smart_notes", max_limit=2)
        if not limit_status["available"] or limit_status["remaining"] <= 0:
            reset_msg = f" at {limit_status['reset_at']}" if limit_status.get("reset_at") else " tomorrow"
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Smart Notes limit reached. You can try again{reset_msg}."
            )

        try:
            clean_instruction = instruction.strip().lower()
            content_fingerprint = hashlib.md5(f"{file_bytes[:500000]}_{clean_instruction}".encode('utf-8')).hexdigest()
            
            cache_query = self.service.get_cache_document(content_fingerprint)
            
            if cache_query.exists:
                cached_data = cache_query.to_dict()
                logger.info("Smart Notes Cache Hit!")
                
                user_history_data = {
                    "user_uid": uid,
                    "title": file.filename,
                    "summary": cached_data["summary"],
                    "custom_instruction": instruction.strip() or None,
                    "created_at": datetime.now(timezone.utc),
                    "source_type": "cached_delivery"
                }
                self.service.save_user_history(user_history_data)
                
                return {
                    "status": "success",
                    "is_cached": True,
                    "title": file.filename,
                    "summary": cached_data["summary"],
                    "slots_remaining": limit_status["remaining"]
                }

            mime_type = self.service.get_mime_type(filename_lower)
            ai_smart_notes = self.service.run_gemini_ai_summary_native(
                file_bytes=file_bytes,
                mime_type=mime_type,
                custom_instruction=instruction
            )

            slots_remaining = enforce_feature_limit(uid, "smart_notes", max_limit=2)

            note_data = {
                "user_uid": uid,
                "title": file.filename,
                "summary": ai_smart_notes,
                "custom_instruction": instruction.strip() or None,
                "created_at": datetime.now(timezone.utc),
                "source_type": "pdf_upload" if filename_lower.endswith('.pdf') else "image_upload"
            }
            
            doc_id = self.service.save_smart_note(note_data)
            
            self.service.save_cache_document(content_fingerprint, {
                "summary": ai_smart_notes,
                "cached_at": datetime.now(timezone.utc)
            })

            return {
                "status": "success",
                "is_cached": False,
                "document_id": doc_id,
                "title": note_data["title"],
                "summary": ai_smart_notes,
                "slots_remaining": slots_remaining
            }

        except HTTPException as http_err:
            raise http_err
        except Exception as e:
            logger.error(f"Runtime Processing Failure: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to complete your document summary request."
            )