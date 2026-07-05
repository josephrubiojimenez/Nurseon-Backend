# routes/case_studies.py
from fastapi import APIRouter, HTTPException, status
import logging

from models.case_studies_models import CaseStudyPayload, EvaluationPayload
from controllers.case_studies_controller import CaseStudiesController

logger = logging.getLogger("case_studies_router")
case_studies_router = APIRouter()
controller = CaseStudiesController()

@case_studies_router.post("/limit-status", status_code=status.HTTP_200_OK)
async def get_case_study_limit_status(payload: dict):
    return controller.get_limit_status(payload.get("uid"))

@case_studies_router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_case_study(payload: CaseStudyPayload):
    return controller.generate_case_study(payload.uid, payload.topic, payload.difficulty)

@case_studies_router.post("/evaluate", status_code=status.HTTP_200_OK)
async def evaluate_response(payload: EvaluationPayload):
    return controller.evaluate_response(payload.uid, payload.patient_scenario, payload.student_response, payload.difficulty)