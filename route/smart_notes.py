import io
import os
import logging
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pypdf import PdfReader
from PIL import Image
import pytesseract
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

if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def run_gemini_ai_summary(full_text: str, custom_instruction: str = "") -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service is currently unconfigured."
        )

    model = genai.GenerativeModel("gemini-2.5-flash")
    
    system_prompt = (
        "You are an expert Nursing and Medical Education Assistant. Your job is to transform "
        "raw medical content or textbook text into beautiful, structured, high-yield 'Smart Notes' "
        "formatted in professional Markdown. Focus on core concepts, definitions, clinical signs, "
        "and nursing interventions where applicable.\n\n"
    )
    
    if custom_instruction.strip():
        system_prompt += f"CRITICAL FOCUS AREA requested by user: \"{custom_instruction}\"\n\n"
        
    user_prompt = f"Please process this source text into comprehensive study material:\n\n{full_text}"

    try:
        response = model.generate_content(system_prompt + user_prompt)
        return response.text if response.text else "Failed to deliver structured text. Please upload another file or image."
    except Exception as ai_err:
        logger.error(f"Gemini API Error: {str(ai_err)}")
        if "429" in str(ai_err) or "quota" in str(ai_err).lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="The AI generation engine is temporarily saturated. Please try again in 1 minute."
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI platform processing failed. Please try again later."
        )


@smart_notes_router.post("/summarize", status_code=status.HTTP_200_OK)
async def summarize_document(
    uid: str = Form(...), 
    file: UploadFile = File(...),
    instruction: str = Form("")
):
    filename_lower = file.filename.lower()
    text_extensions = {'.pdf', '.txt'}
    image_extensions = {'.png', '.jpg', '.jpeg', '.jfif'}
    allowed_extensions = text_extensions.union(image_extensions)
    
    if not any(filename_lower.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported extensions for files are (.pdf, .txt) and images are (.png, .jpg, .jpeg, .jfif)."
        )

    # 1. ENFORCE APP RATE LIMITER FIRST
    slots_remaining = enforce_feature_limit(uid, "smart_notes", max_limit=5)

    try:
        # 2. EXTRACT TEXT FROM DOCUMENT/IMAGE
        extracted_text = ""
        if filename_lower.endswith(('.pdf', '.txt')):
            if filename_lower.endswith('.pdf'):
                pdf_reader = PdfReader(file.file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        extracted_text += page_text + " "
            else:
                text_bytes = await file.read()
                extracted_text = text_bytes.decode("utf-8", errors="ignore")
        else:
            image_bytes = await file.read()
            image_object = Image.open(io.BytesIO(image_bytes))
            extracted_text = pytesseract.image_to_string(image_object)

        if not extracted_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No readable text found. Please upload a clearer file or image."
            )

        # 3. DATABASE CACHE CHECK (Step 3: Cache Common Content)
        # Create a unique fingerprint hash of the combined text and custom prompt
        clean_instruction = instruction.strip().lower()
        content_fingerprint = hashlib.md5(f"{extracted_text.strip()}_{clean_instruction}".encode('utf-8')).hexdigest()
        
        cache_query = db.collection("smart_notes_cache").document(content_fingerprint).get()
        
        if cache_query.exists:
            cached_data = cache_query.to_dict()
            logger.info(f"Cache Hit! Serving saved summary for fingerprint: {content_fingerprint}")
            
            # Save a log of this user interaction to their personal history
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

        # 4. CACHE MISS -> CALL GOOGLE GEMINI API
        ai_smart_notes = run_gemini_ai_summary(extracted_text, custom_instruction=instruction)

        # 5. WRITE TO DB (Save to user history AND update global Cache document)
        note_data = {
            "user_uid": uid,
            "title": file.filename,
            "summary": ai_smart_notes,
            "custom_instruction": instruction.strip() or None,
            "created_at": datetime.now(timezone.utc),
            "source_type": "pdf_upload" if filename_lower.endswith('.pdf') else ("text_upload" if filename_lower.endswith('.txt') else "image_upload")
        }
        
        # Save user record
        doc_ref = db.collection("smart_notes").document()
        doc_ref.set(note_data)
        
        # Write to global cache so the next user doesn't hit Gemini for this exact document
        db.collection("smart_notes_cache").document(content_fingerprint).set({
            "summary": ai_smart_notes,
            "cached_at": datetime.now(timezone.utc)
        })

        logger.info(f"File '{file.filename}' compiled via Gemini. Cache updated.")
        
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