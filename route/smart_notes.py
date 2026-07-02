import io
import os
import logging
import hashlib
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
import google.generativeai as genai

from database.firebase import db
from utils.limiters import enforce_feature_limit

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
        # 1. Upload the file to Gemini's Native Storage API
        uploaded_gemini_file = genai.upload_file(path=file_path, mime_type=mime_type)
        
        # 2. Pass the file token direct to the model inside the content payload array
        response = model.generate_content([system_prompt + user_prompt, uploaded_gemini_file])
        
        return response.text if response.text else "Failed to deliver structured text. Please upload another file or image."
        
    except Exception as ai_err:
        error_msg = str(ai_err)
        logger.error(f"Gemini API Error: {error_msg}", exc_info=True)
        
        if "429" in error_msg or "quota" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="The AI generation engine is temporarily saturated. Please try again in 1 minute."
            )
        elif "api_key" in error_msg.lower() or "invalid" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI service configuration error. Please contact support."
            )
        elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI platform is taking too long to respond. Please try again."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI platform processing failed: {error_msg[:100]}"
            )
    finally:
        # 3. Always clean up files from Google Storage immediately after the prompt completes
        if uploaded_gemini_file:
            try:
                genai.delete_file(name=uploaded_gemini_file.name)
            except Exception as clean_err:
                logger.warning(f"Failed to delete file {uploaded_gemini_file.name}: {clean_err}")


@smart_notes_router.post("/summarize", status_code=status.HTTP_200_OK)
async def summarize_document(
    uid: str = Form(...), 
    file: UploadFile = File(...),
    instruction: str = Form("")
):
    filename_lower = file.filename.lower()
    
    # Map file extensions directly to their real MIME types for Google's engine
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
    # This will raise HTTPException if limit is exceeded or database error occurs
    slots_remaining = enforce_feature_limit(uid, "smart_notes", max_limit=5)

    try:
        # Read file contents to compute the fingerprint
        file_bytes = await file.read()
        
        # 2. DATABASE CACHE CHECK
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

        # 3. CACHE MISS -> Save to a secure temp file to stream directly to Gemini
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
            # Safely eliminate the temporary file from disk local storage
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)

        # 4. WRITE TO DB
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