# models/case_studies_models.py
from pydantic import BaseModel

class CaseStudyPayload(BaseModel):
    uid: str
    topic: str
    difficulty: str = "Standard"

class EvaluationPayload(BaseModel):
    uid: str
    patient_scenario: str
    student_response: str
    difficulty: str = "Standard"

class CaseStudyStructure(BaseModel):
    """Guaranteed structural layout for generated Clinical Cases."""
    title: str
    patient_name: str
    context: str
    patient_complaint: str

class EvaluationStructure(BaseModel):
    """Guaranteed structural layout for Clinical Case Appraisals."""
    score_percentage: int
    clinical_rating: str
    professional_critique: str
    recommended_response: str
    medical_references: str