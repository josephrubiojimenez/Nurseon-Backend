# routes/nursing_care_plans.py
import logging
from fastapi import APIRouter, HTTPException, status, Request
from typing import Optional

from models.nursing_care_plans_models import CarePlanCreate, CarePlanUpdate, CarePlanRename
from controllers.nursing_care_plans_controller import NursingCarePlansController
from route.nurseon_ai_chat import limiter

logger = logging.getLogger("nursing_care_plans")
nursing_care_plans_router = APIRouter()
controller = NursingCarePlansController()

@nursing_care_plans_router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_care_plan(payload: CarePlanCreate):
    return controller.create_care_plan(payload.uid, payload.care_plan.dict())

@nursing_care_plans_router.get("/list/{uid}")
async def get_care_plans(uid: str, search: Optional[str] = None):
    return controller.get_care_plans(uid, search)

@nursing_care_plans_router.get("/{uid}/{care_plan_id}")
async def get_care_plan(uid: str, care_plan_id: str):
    return controller.get_care_plan(uid, care_plan_id)

@nursing_care_plans_router.put("/{uid}/{care_plan_id}")
async def update_care_plan(uid: str, care_plan_id: str, payload: CarePlanUpdate):
    return controller.update_care_plan(uid, care_plan_id, payload.dict(exclude_unset=True))

@nursing_care_plans_router.post("/auto-save/{uid}/{care_plan_id}")
async def auto_save_care_plan(uid: str, care_plan_id: str, payload: dict):
    return controller.auto_save_care_plan(uid, care_plan_id, payload)

@nursing_care_plans_router.post("/{uid}/{care_plan_id}/rename")
async def rename_care_plan(uid: str, care_plan_id: str, payload: CarePlanRename):
    return controller.rename_care_plan(uid, care_plan_id, payload.patient_name)

@nursing_care_plans_router.post("/{uid}/{care_plan_id}/duplicate")
async def duplicate_care_plan(uid: str, care_plan_id: str):
    return controller.duplicate_care_plan(uid, care_plan_id)

@nursing_care_plans_router.delete("/{uid}/{care_plan_id}")
async def delete_care_plan(uid: str, care_plan_id: str):
    return controller.delete_care_plan(uid, care_plan_id)

@nursing_care_plans_router.post("/{uid}/{care_plan_id}/toggle-favorite")
async def toggle_favorite(uid: str, care_plan_id: str):
    return controller.toggle_favorite(uid, care_plan_id)

@nursing_care_plans_router.get("/recent/{uid}")
async def get_recent_care_plans(uid: str, limit: int = 5):
    return controller.get_recent_care_plans(uid, limit)