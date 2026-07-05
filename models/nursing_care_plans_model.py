# models/nursing_care_plans_models.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class CarePlanData(BaseModel):
    patient_name: str
    assessment: str = ""
    diagnosis: str = ""
    planning: str = ""
    implementation: str = ""
    rationale: str = ""
    evaluation: str = ""
    status: str = "Draft"

class CarePlanCreate(BaseModel):
    uid: str
    care_plan: CarePlanData

class CarePlanUpdate(BaseModel):
    patient_name: Optional[str] = None
    assessment: Optional[str] = None
    diagnosis: Optional[str] = None
    planning: Optional[str] = None
    implementation: Optional[str] = None
    rationale: Optional[str] = None
    evaluation: Optional[str] = None
    status: Optional[str] = None
    favorite: Optional[bool] = None
    archived: Optional[bool] = None

class CarePlanRename(BaseModel):
    patient_name: str