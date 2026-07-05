import io
import os
import time
import logging
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
import google.generativeai as genai
from dotenv import load_dotenv

from database.firebase import db
from utils.limiters import enforce_feature_limit, check_rate_limit_status

load_dotenv()

logger = logging.getLogger("smart_notes")
smart_notes_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


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
        # Direct structural byte layout matching Google's generation signature
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


@smart_notes_router.post("/limit-status", status_code=status.HTTP_200_OK)
async def get_smart_notes_limit_status(payload: dict):
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
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded. Please select a file."
        )
    
    filename_lower = file.filename.lower()
    
    try:
        file_bytes = await file.read()
        file_size = len(file_bytes)
        
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )
        
        # Guard rail down to 15MB for direct in-memory passing optimization
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
        
        cache_query = db.collection("smart_notes_cache").document(content_fingerprint).get()
        
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
            db.collection("smart_notes").document().set(user_history_data)
            
            return {
                "status": "success",
                "is_cached": True,
                "title": file.filename,
                "summary": cached_data["summary"],
                "slots_remaining": limit_status["remaining"]
            }

        # Run direct in-memory layout engine
        ai_smart_notes = run_gemini_ai_summary_native(
            file_bytes=file_bytes,
            mime_type=mime_mapping[file_ext],
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
        
        doc_ref = db.collection("smart_notes").document()
        doc_ref.set(note_data)
        
        db.collection("smart_notes_cache").document(content_fingerprint).set({
            "summary": ai_smart_notes,
            "cached_at": datetime.now(timezone.utc)
        })

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
        logger.error(f"Runtime Processing Failure: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete your document summary request."
        )