import os
import logging
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import google.generativeai as genai

from database.firebase import db
from utils.limiters import enforce_feature_limit

logger = logging.getLogger("case_studies_router")
case_studies_router = APIRouter()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class CaseStudyPayload(BaseModel):
    uid: str
    topic: str
    difficulty: str = "Standard"

class EvaluationPayload(BaseModel):
    uid: str
    patient_scenario: str
    student_response: str

def run_gemini_case_generation(topic: str, difficulty: str) -> dict:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unconfigured."
        )

    model = genai.GenerativeModel("gemini-2.5-flash")
    
    system_prompt = (
        "You are an expert Nursing Clinical Simulation Instructor.\n"
        f"Generate a realistic patient case scenario centered around this disease/topic: '{topic}' at a '{difficulty}' level.\n\n"
        "The scenario must represent a direct clinical floor interaction where a patient speaks directly to the nurse.\n"
        "You MUST return ONLY a clean JSON object (no markdown, no ```json decorators). "
        "Follow this exact schema layout:\n"
        "{\n"
        '  "title": "Clinical Vignette Title",\n'
        '  "patient_name": "Patient (give them a realistic name e.g. Joseph Jimenez, Lexine Magabo)",\n'
        '  "context": "Brief clinical background context, admitting details, and current baseline vitals.",\n'
        '  "patient_complaint": "Write what the patient literally states out loud to the student here (e.g., Nurse, my vision is cloudy or I have a splitting headache.)"\n'
        "}"
    )

    try:
        response = model.generate_content(system_prompt)
        clean_text = response.text.strip()
        
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
        if clean_text.startswith("json"):
            clean_text = clean_text.split("\n", 1)[1].strip()

        return json.loads(clean_text)
    except Exception as e:
        logger.error(f"Gemini Case Study Generation Failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate a cleanly structured clinical case layout."
        )

def run_gemini_evaluation(scenario: str, response_text: str) -> dict:
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Service is currently unconfigured."
        )

    model = genai.GenerativeModel("gemini-2.5-flash")
    
    system_prompt = (
        f"You are an advanced Clinical Case Evaluator. Analyze this clinical patient scenario and background context: '{scenario}'\n"
        f"Critically evaluate the user's intervention response: '{response_text}'.\n\n"
        "CRITICAL ROLEPLAY RULE:\n"
        "Treat the user as the primary Professional Registered Nurse fully in charge of this patient's care. "
        "Do NOT address them as a nursing student, do NOT evaluate them as a student, and NEVER suggest that they 'help the registered nurse' or 'defer to a senior nurse' for basic independent nursing processes. "
        "Evaluate their actions as an autonomous, practicing professional nurse exercising independent or dependent nursing scope of practice.\n\n"
        "Determine if their action is safe, professional, and correct according to current nursing care protocols. "
        "You MUST return ONLY a clean JSON object (no markdown formatting, no ```json codeblocks). Follow this exact schema layout:\n"
        "{\n"
        '  "score_percentage": 85,\n'
        '  "clinical_rating": "Critical Safety Violation / Needs Improvement / Competent / Excellent",\n'
        '  "professional_critique": "Detailed professional evaluation explaining why this score was given based on advanced clinical assessment, pathophysiological rationale, and protocol delegation.",\n'
        '  "recommended_response": "Write exactly what an expert professional registered nurse should have stated or executed instead in this high-fidelity setup.",\n'
        '  "medical_references": "Provide specific textbook reference citations to help the nurse improve (e.g., Saunders Comprehensive Review for the NCLEX Examination and PNLE Examination exclusively in the philippines, Lippincott Manual of Nursing Practice)."\n'
        "}"
    )

    
    #Cleaning JSON Text
    try:
        response = model.generate_content(system_prompt)
        clean_text = response.text.strip()
        
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
        if clean_text.startswith("json"):
            clean_text = clean_text.split("\n", 1)[1].strip()

        return json.loads(clean_text)
    except Exception as e:
        logger.error(f"Failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed."
        )

@case_studies_router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_case_study(payload: CaseStudyPayload):
    slots_remaining = enforce_feature_limit(payload.uid, "case_studies", max_limit=5)

    try:
        case_data_object = run_gemini_case_generation(payload.topic, payload.difficulty)

        record = {
            "user_uid": payload.uid,
            "topic": payload.topic,
            "difficulty": payload.difficulty,
            "case_details": case_data_object,
            "created_at": datetime.now(timezone.utc)
        }

        doc_ref = db.collection("generated_cases").document()
        doc_ref.set(record)

        return {
            "status": "success",
            "case_id": doc_ref.id,
            "case": case_data_object,
            "slots_remaining": slots_remaining
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Case runtime crash: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal application error compiling case files."
        )

@case_studies_router.post("/evaluate", status_code=status.HTTP_200_OK)
async def evaluate_response(payload: EvaluationPayload):
    try:
        evaluation_data = run_gemini_evaluation(payload.patient_scenario, payload.student_response)

        evaluation_record = {
            "user_uid": payload.uid,
            "patient_scenario": payload.patient_scenario,
            "student_response": payload.student_response,
            "evaluation_details": evaluation_data,
            "evaluated_at": datetime.now(timezone.utc)
        }

        db.collection("case_evaluations").document().set(evaluation_record)

        return {
            "status": "success",
            "evaluation": evaluation_data
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error(f"Evaluation pipeline crash: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal application error analyzing student response."
        )