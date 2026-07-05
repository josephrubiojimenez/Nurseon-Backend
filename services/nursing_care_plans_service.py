# services/nursing_care_plans_service.py
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status

from database.firebase import db

logger = logging.getLogger("nursing_care_plans_service")

class NursingCarePlansService:
    @staticmethod
    def get_care_plan_collection(uid: str):
        return db.collection("users_auth").document(uid).collection("nursing_care_plans")

    @staticmethod
    def format_care_plan(doc_id: str, data: dict) -> dict:
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

    @staticmethod
    def create_care_plan(uid: str, care_plan_data: dict):
        now = datetime.now(timezone.utc)
        doc_ref = NursingCarePlansService.get_care_plan_collection(uid).document()
        
        data = {
            "patient_name": care_plan_data.get("patient_name"),
            "assessment": care_plan_data.get("assessment", ""),
            "diagnosis": care_plan_data.get("diagnosis", ""),
            "planning": care_plan_data.get("planning", ""),
            "implementation": care_plan_data.get("implementation", ""),
            "rationale": care_plan_data.get("rationale", ""),
            "evaluation": care_plan_data.get("evaluation", ""),
            "status": care_plan_data.get("status", "Draft"),
            "created_at": now,
            "updated_at": now,
            "last_opened": now,
            "favorite": False,
            "archived": False
        }
        
        doc_ref.set(data)
        return doc_ref.id, data

    @staticmethod
    def get_care_plans(uid: str, search: Optional[str] = None):
        collection = NursingCarePlansService.get_care_plan_collection(uid)
        docs = collection.stream()
        
        care_plans = []
        for doc in docs:
            data = doc.to_dict()
            if data.get("archived", False):
                continue
                
            care_plan = NursingCarePlansService.format_care_plan(doc.id, data)
            
            if search:
                search_lower = search.lower()
                if (search_lower in care_plan["patient_name"].lower() or
                    search_lower in care_plan["diagnosis"].lower() or
                    search_lower in care_plan["assessment"].lower()):
                    care_plans.append(care_plan)
            else:
                care_plans.append(care_plan)
        
        care_plans.sort(key=lambda x: x.get("last_opened") or x.get("created_at") or "", reverse=True)
        return care_plans

    @staticmethod
    def get_care_plan(uid: str, care_plan_id: str):
        doc_ref = NursingCarePlansService.get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        doc_ref.update({"last_opened": datetime.now(timezone.utc)})
        
        return data

    @staticmethod
    def update_care_plan(uid: str, care_plan_id: str, update_data: dict):
        doc_ref = NursingCarePlansService.get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        update_data["updated_at"] = datetime.now(timezone.utc)
        doc_ref.update(update_data)
        
        updated_doc = doc_ref.get()
        return updated_doc.to_dict()

    @staticmethod
    def delete_care_plan(uid: str, care_plan_id: str):
        doc_ref = NursingCarePlansService.get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return False
        
        doc_ref.update({
            "archived": True,
            "updated_at": datetime.now(timezone.utc)
        })
        return True

    @staticmethod
    def toggle_favorite(uid: str, care_plan_id: str):
        doc_ref = NursingCarePlansService.get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        current = doc.to_dict().get("favorite", False)
        doc_ref.update({
            "favorite": not current,
            "updated_at": datetime.now(timezone.utc)
        })
        return not current

    @staticmethod
    def rename_care_plan(uid: str, care_plan_id: str, patient_name: str):
        doc_ref = NursingCarePlansService.get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        doc_ref.update({
            "patient_name": patient_name,
            "updated_at": datetime.now(timezone.utc)
        })
        return patient_name

    @staticmethod
    def duplicate_care_plan(uid: str, care_plan_id: str):
        # Get original
        doc_ref = NursingCarePlansService.get_care_plan_collection(uid).document(care_plan_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        
        # Create copy
        now = datetime.now(timezone.utc)
        new_doc_ref = NursingCarePlansService.get_care_plan_collection(uid).document()
        
        # Add "(Copy)" to patient name
        patient_name = data.get("patient_name", "Untitled")
        if " (Copy)" not in patient_name:
            patient_name = f"{patient_name} (Copy)"
        else:
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
        return new_doc_ref.id, new_data

    @staticmethod
    def get_recent_care_plans(uid: str, limit: int = 5):
        collection = NursingCarePlansService.get_care_plan_collection(uid)
        docs = collection.stream()
        
        care_plans = []
        for doc in docs:
            data = doc.to_dict()
            if not data.get("archived", False):
                care_plans.append(NursingCarePlansService.format_care_plan(doc.id, data))
        
        care_plans.sort(key=lambda x: x.get("last_opened") or x.get("created_at") or "", reverse=True)
        return care_plans[:limit]