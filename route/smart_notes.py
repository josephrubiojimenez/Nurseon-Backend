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
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini API configured successfully")
    except Exception as config_err:
        logger.error(f"Failed to configure Gemini API: {config_err}")
else:
    logger.error("GEMINI_API_KEY environment variable is not set")


def run_gemini_ai_summary_native(file_path: str, mime_type: str, custom_instruction: str = "") -> str:
    if not GEMINI_API_KEY:
        logger.error("Gemini API key is missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service is currently unconfigured. Please contact support."
        )

    try:
        # Test the API key by making a simple call
        model = genai.GenerativeModel("gemini-1.5-flash")
        # Try gemini-1.5-flash instead of gemini-2.5-flash as it might be more stable
    except Exception as model_err:
        logger.error(f"Failed to initialize Gemini model: {model_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service initialization failed. Please try again later."
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

    uploaded_gemini_file = None
    try:
        # Upload file to Gemini
        logger.info(f"Uploading file to Gemini: {file_path} with mime_type: {mime_type}")
        uploaded_gemini_file = genai.upload_file(path=file_path, mime_type=mime_type)
        
        # Wait for file to be processed
        import time
        time.sleep(1)
        
        logger.info("Generating content with Gemini...")
        response = model.generate_content([system_prompt + user_prompt, uploaded_gemini_file])
        
        if not response.text:
            logger.warning("Gemini returned empty response")
            return "Failed to generate structured text. Please try uploading a different file or image."
            
        logger.info("Successfully generated smart notes")
        return response.text
        
    except genai.types.generation_types.BlockedPromptException as blocked_err:
        logger.error(f"Content blocked by Gemini: {blocked_err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The content was blocked by the AI service. Please try a different document."
        )
    except Exception as ai_err:
        error_msg = str(ai_err)
        logger.error(f"Gemini API Error: {error_msg}", exc_info=True)
        
        # Check for specific error types
        if "429" in error_msg or "quota" in error_msg.lower() or "rate_limit" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests right now. Please wait a minute and try again."
            )
        elif "api_key" in error_msg.lower() or "invalid" in error_msg.lower() or "permission" in error_msg.lower():
            logger.error(f"API Key issue detected: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI Service authentication failed. Please contact support."
            )
        elif "timeout" in error_msg.lower() or "deadline" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="The AI is currently busy. Please try again in a moment."
            )
        elif "file" in error_msg.lower() and "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File upload failed. Please try uploading the file again."
            )
        else:
            # Return more specific error message for debugging
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI Service error: {error_msg[:100]}"
            )
    finally:
        if uploaded_gemini_file:
            try:
                genai.delete_file(name=uploaded_gemini_file.name)
                logger.info(f"Deleted temporary file: {uploaded_gemini_file.name}")
            except Exception as clean_err:
                logger.warning(f"Failed to delete file {uploaded_gemini_file.name}: {clean_err}")


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
    # Validate file
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded. Please select a file."
        )
    
    filename_lower = file.filename.lower()
    file_size = 0
    
    try:
        # Check file size before processing
        file_bytes = await file.read()
        file_size = len(file_bytes)
        
        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty. Please upload a valid file."
            )
        
        if file_size > 20 * 1024 * 1024:  # 20MB limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 20MB limit. Please upload a smaller file."
            )
            
    except Exception as read_err:
        logger.error(f"File read error: {read_err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read the uploaded file. Please try again."
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
            detail=f"Unsupported file format: {file_ext}. Supported formats are: {', '.join(mime_mapping.keys())}"
        )

    # 1. Check current limit status
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
        
        # Check cache
        cache_query = db.collection("smart_notes_cache").document(content_fingerprint).get()
        
        if cache_query.exists:
            cached_data = cache_query.to_dict()
            logger.info(f"Cache Hit for fingerprint: {content_fingerprint}")
            
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

        # 2. Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_file_path = tmp_file.name
            logger.info(f"Temporary file created: {tmp_file_path}")

        try:
            # 3. Process with Gemini
            ai_smart_notes = run_gemini_ai_summary_native(
                file_path=tmp_file_path,
                mime_type=mime_mapping[file_ext],
                custom_instruction=instruction
            )
            
            # Validate response
            if not ai_smart_notes or len(ai_smart_notes.strip()) < 10:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="The AI returned an empty or incomplete response. Please try again."
                )
                
        finally:
            # Clean up temp file
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
                logger.info(f"Temporary file deleted: {tmp_file_path}")

        # 4. Deduct the slot only after successful AI response
        slots_remaining = enforce_feature_limit(uid, "smart_notes", max_limit=2)

        # 5. Save to database
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
        
        # 6. Cache the response
        db.collection("smart_notes_cache").document(content_fingerprint).set({
            "summary": ai_smart_notes,
            "cached_at": datetime.now(timezone.utc)
        })

        logger.info(f"Successfully processed file: {file.filename}")
        
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
            detail=f"Failed to process your request: {str(e)}"
        )