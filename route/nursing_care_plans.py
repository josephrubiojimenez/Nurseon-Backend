import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import uuid4

from database.firebase import db
from utils.limiters import enforce_feature_limit, check_rate_limit_status
from route.nurseon_ai_chat import limiter

logger = logging.getLogger("nursing_care_plans")
nursing_care_plans_router = APIRouter()

# ==========================================
# SCHEMAS
# ==========================================

class CarePlanData(BaseModel):
    patient_name: str
    assessment: str = ""
    diagnosis: str = ""
    planning: str = ""
    implementation: str = ""
    rationale: str = ""
    evaluation: str = ""
    status: str = "Draft"  # Draft, In Progress, Completed

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

class CarePlanResponse(BaseModel):
    id: str
    patient_name: str
    assessment: str
    diagnosis: str
    planning: str
    implementation: str
    rationale: str
    evaluation: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_opened: datetime
    favorite: bool
    archived: bool

# ==========================================
# HELPERS
# ==========================================

def get_care_plan_collection(uid: str):
    """Get the care plans collection reference for a user."""
    return db.collection("users").document(uid).collection("nursing_care_plans")

def format_care_plan(doc_id: str, data: dict) -> dict:
    """Format a care plan document for response."""
    return {
        "id": doc_id,
        "patient_name": data.get("patient_name", "Untitled"),
        "assessment": data.get("assessment", ""),
        "diagnosis": data.get("diagnosis", ""),
        "planning": data.get("planning", ""),
        "implementation": data.get("implementation", ""),
        "rationale": data.get("rationale", ""),
        "evaluation": data.get("evaluation", ""),
        "status": data.get("status", "Draft"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "last_opened": data.get("last_opened"),
        "favorite": data.get("favorite", False),
        "archived": data.get("archived", False)
    }

# ==========================================
# API ENDPOINTS
# ==========================================

@nursing_care_plans_router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_care_plan(payload: CarePlanCreate):
    """Create a new nursing care plan."""
    uid = payload.uid
    care_plan = payload.care_plan
    
    try:
        # Enforce rate limit (10 per day)
        try:
            slots_remaining = enforce_feature_limit(uid, "nursing_care_plans", max_limit=10)
        except HTTPException as e:
            if e.status_code == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Daily limit reached. You can create up to 10 care plans per day."
                )
            raise e
        
        now = datetime.now(timezone.utc)
        doc_ref = get_care_plan_collection(uid).document()
        
        data = {
            "patient_name": care_plan.patient_name,
            "assessment": care_plan.assessment,
            "diagnosis": care_plan.diagnosis,
            "planning": care_plan.planning,
            "implementation": care_plan.implementation,
            "rationale": care_plan.rationale,
            "evaluation": care_plan.evaluation,
            "status": care_plan.status,
            "created_at": now,
            "updated_at": now,
            "last_opened": now,
            "favorite": False,
            "archived": False
        }
        
        doc_ref.set(data)
        
        return {
            "status": "success",
            "message": "Care plan created successfully",
            "id": doc_ref.id,
            "care_plan": format_care_plan(doc_ref.id, data),
            "slots_remaining": slots_remaining
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating care plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create care plan"
        )


@nursing_care_plans_router.get("/list/{uid}")
async def get_care_plans(uid: str, limit: int = 50, offset: int = 0, search: Optional[str] = None):
    """Get all care plans for a user with optional search."""
    try:
        collection = get_care_plan_collection(uid)
        
        # Base query - not archived
        query = collection.where("archived", "==", False)
        
        # Order by last_opened (most recent first)
        query = query.order_by("last_opened", direction="DESCENDING")
        
        # Execute query
        docs = query.limit(limit).offset(offset).stream()
        
        care_plans = []
        for doc in docs:
            data = doc.to_dict()
            care_plan = format_care_plan(doc.id, data)
            
            # Apply search filter client-side if provided
            if search:
                search_lower = search.lower()
                if (search_lower in care_plan["patient_name"].lower() or
                    search_lower in care_plan["diagnosis"].lower() or
                    search_lower in care_plan["assessment"].lower()):
                    care_plans.append(care_plan)
            else:
                care_plans.append(care_plan)
        
        # Get total count
        total_query = collection.where("archived", "==", False).stream()
        total = sum(1 for _ in total_query)
        
        return {
            "status": "success",
            "care_plans": care_plans,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error getting care plans: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get care plans"
        )


@nursing_care_plans_router.get("/{uid}/{care_plan_id}")
async def get_care_plan(uid: str, care_plan_id: str):
    """Get a specific care plan by ID."""
    try:
        doc_ref = get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care plan not found"
            )
        
        data = doc.to_dict()
        
        # Update last_opened
        doc_ref.update({"last_opened": datetime.now(timezone.utc)})
        
        return {
            "status": "success",
            "care_plan": format_care_plan(care_plan_id, data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting care plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get care plan"
        )


@nursing_care_plans_router.put("/{uid}/{care_plan_id}")
async def update_care_plan(uid: str, care_plan_id: str, payload: CarePlanUpdate):
    """Update a care plan."""
    try:
        doc_ref = get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care plan not found"
            )
        
        # Build update data
        update_data = {}
        fields = ["patient_name", "assessment", "diagnosis", "planning", 
                  "implementation", "rationale", "evaluation", "status", 
                  "favorite", "archived"]
        
        for field in fields:
            value = getattr(payload, field, None)
            if value is not None:
                update_data[field] = value
        
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        doc_ref.update(update_data)
        
        # Get updated doc
        updated_doc = doc_ref.get()
        data = updated_doc.to_dict()
        
        return {
            "status": "success",
            "message": "Care plan updated successfully",
            "care_plan": format_care_plan(care_plan_id, data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating care plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update care plan"
        )


@nursing_care_plans_router.post("/auto-save/{uid}/{care_plan_id}")
async def auto_save_care_plan(uid: str, care_plan_id: str, payload: dict):
    """Auto-save endpoint for real-time updates."""
    try:
        doc_ref = get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care plan not found"
            )
        
        # Only update specific fields
        allowed_fields = ["assessment", "diagnosis", "planning", 
                         "implementation", "rationale", "evaluation"]
        update_data = {}
        
        for field in allowed_fields:
            if field in payload:
                update_data[field] = payload[field]
        
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        doc_ref.update(update_data)
        
        return {
            "status": "success",
            "message": "Care plan saved successfully",
            "updated_at": update_data["updated_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error auto-saving care plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to auto-save care plan"
        )


@nursing_care_plans_router.post("/{uid}/{care_plan_id}/rename")
async def rename_care_plan(uid: str, care_plan_id: str, payload: CarePlanRename):
    """Rename a care plan (update patient name)."""
    try:
        doc_ref = get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care plan not found"
            )
        
        doc_ref.update({
            "patient_name": payload.patient_name,
            "updated_at": datetime.now(timezone.utc)
        })
        
        return {
            "status": "success",
            "message": "Care plan renamed successfully",
            "patient_name": payload.patient_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming care plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rename care plan"
        )


@nursing_care_plans_router.post("/{uid}/{care_plan_id}/duplicate")
async def duplicate_care_plan(uid: str, care_plan_id: str):
    """Duplicate a care plan."""
    try:
        # Get original
        doc_ref = get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care plan not found"
            )
        
        data = doc.to_dict()
        
        # Create copy
        now = datetime.now(timezone.utc)
        new_doc_ref = get_care_plan_collection(uid).document()
        
        # Add "(Copy)" to patient name
        patient_name = data.get("patient_name", "Untitled")
        if " (Copy)" not in patient_name:
            patient_name = f"{patient_name} (Copy)"
        else:
            # If already has copy, add number
            import re
            match = re.search(r'\(Copy\)(\d+)?$', patient_name)
            if match:
                num = int(match.group(1) or 1)
                patient_name = re.sub(r'\(Copy\)\d*$', f'(Copy){num + 1}', patient_name)
            else:
                patient_name = f"{patient_name} (Copy)"
        
        new_data = {
            "patient_name": patient_name,
            "assessment": data.get("assessment", ""),
            "diagnosis": data.get("diagnosis", ""),
            "planning": data.get("planning", ""),
            "implementation": data.get("implementation", ""),
            "rationale": data.get("rationale", ""),
            "evaluation": data.get("evaluation", ""),
            "status": "Draft",
            "created_at": now,
            "updated_at": now,
            "last_opened": now,
            "favorite": False,
            "archived": False
        }
        
        new_doc_ref.set(new_data)
        
        return {
            "status": "success",
            "message": "Care plan duplicated successfully",
            "id": new_doc_ref.id,
            "care_plan": format_care_plan(new_doc_ref.id, new_data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating care plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to duplicate care plan"
        )


@nursing_care_plans_router.delete("/{uid}/{care_plan_id}")
async def delete_care_plan(uid: str, care_plan_id: str):
    """Delete a care plan (soft delete by archiving)."""
    try:
        doc_ref = get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care plan not found"
            )
        
        # Soft delete - archive instead
        doc_ref.update({
            "archived": True,
            "updated_at": datetime.now(timezone.utc)
        })
        
        return {
            "status": "success",
            "message": "Care plan deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting care plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete care plan"
        )


@nursing_care_plans_router.post("/{uid}/{care_plan_id}/toggle-favorite")
async def toggle_favorite(uid: str, care_plan_id: str):
    """Toggle favorite status of a care plan."""
    try:
        doc_ref = get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Care plan not found"
            )
        
        current = doc.to_dict().get("favorite", False)
        doc_ref.update({
            "favorite": not current,
            "updated_at": datetime.now(timezone.utc)
        })
        
        return {
            "status": "success",
            "message": f"Favorite {'enabled' if not current else 'disabled'}",
            "favorite": not current
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling favorite: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle favorite"
        )


@nursing_care_plans_router.get("/recent/{uid}")
async def get_recent_care_plans(uid: str, limit: int = 5):
    """Get most recent care plans for dashboard."""
    try:
        collection = get_care_plan_collection(uid)
        
        query = collection.where("archived", "==", False)
        query = query.order_by("last_opened", direction="DESCENDING")
        docs = query.limit(limit).stream()
        
        care_plans = []
        for doc in docs:
            data = doc.to_dict()
            care_plans.append(format_care_plan(doc.id, data))
        
        return {
            "status": "success",
            "care_plans": care_plans
        }
        
    except Exception as e:
        logger.error(f"Error getting recent care plans: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get recent care plans"
        )