import io
import os
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pypdf import PdfReader
from PIL import Image
import pytesseract
import google.generativeai as genai

from database.firebase import db

logger = logging.getLogger("smart_notes")
smart_notes_router = APIRouter()

# Initialize Gemini AI
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.error("GEMINI_API_KEY missing from environment variables.")

if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def run_gemini_ai_summary(full_text: str, custom_instruction: str = "") -> str:
    """
    Sends the extracted text along with instructions to Gemini to generate 
    highly accurate, professional Nursing/Medical Smart Study Notes.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service is currently unconfigured."
        )

    # Use gemini-2.5-flash for rapid, cost-effective, and smart text operations
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
        return response.text if response.text else "AI failed to deliver structured text."
    except Exception as ai_err:
        logger.error(f"Gemini API Error: {str(ai_err)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to get a response from the AI Engine."
        )


def enforce_firestore_rate_limit(uid: str) -> int:
    """
    Checks Firestore tracking records to enforce a maximum of 5 uploads per 24 hours.
    Returns the number of remaining upload slots.
    """
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(days=1)
    
    rate_limit_ref = db.collection("rate_limits").document(uid)
    doc = rate_limit_ref.get()
    
    timestamps = []
    if doc.exists:
        data = doc.to_dict()
        # Parse firestore timestamps into timezone-aware datetimes
        timestamps = [t if t.tzinfo else t.replace(tzinfo=timezone.utc) for t in data.get("uploads", [])]
    
    # Filter out historical items older than 24 hours
    valid_timestamps = [t for t in timestamps if t > twenty_four_hours_ago]
    
    if len(valid_timestamps) >= 5:
        # Find when oldest slots clear out to give user a clean cooldown timer
        oldest_upload = min(valid_timestamps)
        cooldown_end = oldest_upload + timedelta(days=1)
        time_left = cooldown_end - now
        hours_left = round(time_left.total_seconds() / 3600, 1)
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily AI upload limit reached. Your next upload slot opens in {hours_left} hours."
        )
        
    # Append contemporary timestamp and update records
    valid_timestamps.append(now)
    rate_limit_ref.set({"uploads": valid_timestamps})
    
    return 5 - len(valid_timestamps)


@smart_notes_router.post("/summarize", status_code=status.HTTP_200_OK)
async def summarize_document(
    uid: str = Form(...),  # Received securely via multipart/form-data
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

    # 1. Evaluate rate limits in Firestore prior to processing documents
    slots_remaining = enforce_firestore_rate_limit(uid)

    try:
        extracted_text = ""

        # 2. Text extraction mechanics
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

        # 3. Optical Character Recognition (OCR) for image items
        else:
            image_bytes = await file.read()
            image_object = Image.open(io.BytesIO(image_bytes))
            extracted_text = pytesseract.image_to_string(image_object)

        if not extracted_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No readable text found. Please upload a clearer file or document."
            )

        # 4. Process text with Gemini
        ai_smart_notes = run_gemini_ai_summary(extracted_text, custom_instruction=instruction)

        # 5. Save generated notes to Firestore
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

        logger.info(f"File '{file.filename}' processed via Gemini. Document ID: {doc_ref.id}")
        return {
            "status": "success",
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
            detail=f"Internal script crash: {str(e)}"
        )