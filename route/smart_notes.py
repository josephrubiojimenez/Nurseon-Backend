import io
import os
import logging
import hashlib
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
import google.generativeai as genai

from database.firebase import db
from utils.limiters import enforce_feature_limit, check_rate_limit_status

logger = logging.getLogger("smart_notes")
smart_notes_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.error("Missing API key.")


def run_gemini_ai_summary_native(file_path: str, mime_type: str, custom_instruction: str = "") -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service is currently unconfigured."
        )

    model = genai.GenerativeModel("gemini-2.5-flash")
    
    system_prompt = (
        "You are an expert Nursing and Medical Education Assistant. Your job is to transform "
        "the uploaded medical content, textbook page, or document into beautiful, structured, "
        "high-yield 'Smart Notes' formatted in professional Markdown. Focus on core concepts, "
        "definitions, clinical signs, and nursing interventions where applicable.\n\n"
    )
    
    if custom_instruction.strip():
        system_prompt += f"CRITICAL FOCUS AREA requested by user: \"{custom_instruction}\"\n\n"
        
    user_prompt = "Please process this attached document source file into comprehensive study material."

    uploaded_gemini_file = None
    try:
        uploaded_gemini_file = genai.upload_file(path=file_path, mime_type=mime_type)
        response = model.generate_content([system_prompt + user_prompt, uploaded_gemini_file])
        return response.text if response.text else "Failed to deliver structured text. Please upload another file or image."
    except Exception as ai_err:
        error_msg = str(ai_err)
        logger.error(f"Gemini API Error: {error_msg}", exc_info=True)
        
        if "429" in error_msg or "quota" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests right now. Please wait a minute and try again."
            )
        elif "api_key" in error_msg.lower() or "invalid" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Smart Notes is taking a break. Please try again in a few minutes."
            )
        elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="The AI is thinking too hard. Please try again in a moment."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Oops! Something went wrong. Please try again."
            )
    finally:
        if uploaded_gemini_file:
            try:
                genai.delete_file(name=uploaded_gemini_file.name)
            except Exception as clean_err:
                logger.warning(f"Failed to delete file {uploaded_gemini_file.name}: {clean_err}")


@smart_notes_router.post("/limit-status", status_code=status.HTTP_200_OK)
async def get_smart_notes_limit_status(payload: dict):
    """Get the current rate limit status for smart notes."""
    uid = payload.get("uid")
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


@smart_notes_router.post("/summarize", status_code=status.HTTP_200_OK)
async def summarize_document(
    uid: str = Form(...), 
    file: UploadFile = File(...),
    instruction: str = Form("")
):
    filename_lower = file.filename.lower()
    
    mime_mapping = {
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.jfif': 'image/jpeg'
    }
    
    file_ext = os.path.splitext(filename_lower)[1]
    if file_ext not in mime_mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported extensions for files are (.pdf, .txt) and images are (.png, .jpg, .jpeg, .jfif)."
        )

    # 1. ENFORCE APP RATE LIMITER FIRST
    try:
        slots_remaining = enforce_feature_limit(uid, "smart_notes", max_limit=2)
    except HTTPException as e:
        if e.status_code == 429:
            # Get the reset time from the status check
            limit_status = check_rate_limit_status(uid, "smart_notes", max_limit=2)
            reset_msg = f" at {limit_status['reset_at']}" if limit_status.get("reset_at") else " tomorrow"
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Smart Notes limit reached. You can try again{reset_msg}."
            )
        raise e

    try:
        file_bytes = await file.read()
        
        clean_instruction = instruction.strip().lower()
        content_fingerprint = hashlib.md5(f"{file_bytes[:500000]}_{clean_instruction}".encode('utf-8')).hexdigest()
        
        cache_query = db.collection("smart_notes_cache").document(content_fingerprint).get()
        
        if cache_query.exists:
            cached_data = cache_query.to_dict()
            logger.info(f"Cache Hit! Serving saved summary for fingerprint: {content_fingerprint}")
            
            user_history_data = {
                "user_uid": uid,
                "title": file.filename,
                "summary": cached_data["summary"],
                "custom_instruction": instruction.strip() or None,
                "created_at": datetime.now(timezone.utc),
                "source_type": "cached_delivery"
            }
            db.collection("smart_notes").document().set(user_history_data)
            
            return {
                "status": "success",
                "is_cached": True,
                "title": file.filename,
                "summary": cached_data["summary"],
                "slots_remaining": slots_remaining
            }

        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_file_path = tmp_file.name

        try:
            ai_smart_notes = run_gemini_ai_summary_native(
                file_path=tmp_file_path,
                mime_type=mime_mapping[file_ext],
                custom_instruction=instruction
            )
        finally:
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)

        note_data = {
            "user_uid": uid,
            "title": file.filename,
            "summary": ai_smart_notes,
            "custom_instruction": instruction.strip() or None,
            "created_at": datetime.now(timezone.utc),
            "source_type": "pdf_upload" if filename_lower.endswith('.pdf') else ("text_upload" if filename_lower.endswith('.txt') else "image_upload")
        }
        
        doc_ref = db.collection("smart_notes").document()
        doc_ref.set(note_data)
        
        db.collection("smart_notes_cache").document(content_fingerprint).set({
            "summary": ai_smart_notes,
            "cached_at": datetime.now(timezone.utc)
        })

        logger.info(f"File '{file.filename}' compiled via native Gemini API. Cache updated.")
        
        return {
            "status": "success",
            "is_cached": False,
            "document_id": doc_ref.id,
            "title": note_data["title"],
            "summary": ai_smart_notes,
            "slots_remaining": slots_remaining
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Runtime Processing Failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal system service interruption: {str(e)}"
        )