# controllers/nursing_care_plans_controller.py
import logging
from fastapi import HTTPException, status

from services.nursing_care_plans_service import NursingCarePlansService

logger = logging.getLogger("nursing_care_plans_controller")

class NursingCarePlansController:
    def __init__(self):
        self.service = NursingCarePlansService()

    def create_care_plan(self, uid: str, care_plan_data: dict):
        try:
            doc_id, data = self.service.create_care_plan(uid, care_plan_data)
            
            return {
                "status": "success",
                "message": "Care plan created successfully",
                "id": doc_id,
                "care_plan": self.service.format_care_plan(doc_id, data),
                "slots_remaining": None
            }
        except Exception as e:
            logger.error(f"Error creating care plan: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create care plan: {str(e)}"
            )

    def get_care_plans(self, uid: str, search: Optional[str] = None):
        try:
            care_plans = self.service.get_care_plans(uid, search)
            return {
                "status": "success",
                "care_plans": care_plans,
                "total": len(care_plans)
            }
        except Exception as e:
            logger.error(f"Error getting care plans: {str(e)}")
            return {
                "status": "success",
                "care_plans": [],
                "total": 0
            }

    def get_care_plan(self, uid: str, care_plan_id: str):
        try:
            data = self.service.get_care_plan(uid, care_plan_id)
            if not data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Care plan not found"
                )
            
            return {
                "status": "success",
                "care_plan": self.service.format_care_plan(care_plan_id, data)
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting care plan: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get care plan: {str(e)}"
            )

    def update_care_plan(self, uid: str, care_plan_id: str, update_data: dict):
        try:
            data = self.service.update_care_plan(uid, care_plan_id, update_data)
            if not data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Care plan not found"
                )
            
            return {
                "status": "success",
                "message": "Care plan updated successfully",
                "care_plan": self.service.format_care_plan(care_plan_id, data)
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating care plan: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update care plan: {str(e)}"
            )

    def auto_save_care_plan(self, uid: str, care_plan_id: str, payload: dict):
        try:
            allowed_fields = ["assessment", "diagnosis", "planning", 
                            "implementation", "rationale", "evaluation"]
            update_data = {}
            
            for field in allowed_fields:
                if field in payload:
                    update_data[field] = payload[field]
            
            if update_data:
                data = self.service.update_care_plan(uid, care_plan_id, update_data)
                if not data:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Care plan not found"
                    )
            
            return {
                "status": "success",
                "message": "Care plan saved successfully",
                "updated_at": update_data.get("updated_at")
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error auto-saving care plan: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to auto-save care plan: {str(e)}"
            )

    def rename_care_plan(self, uid: str, care_plan_id: str, patient_name: str):
        try:
            result = self.service.rename_care_plan(uid, care_plan_id, patient_name)
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Care plan not found"
                )
            
            return {
                "status": "success",
                "message": "Care plan renamed successfully",
                "patient_name": patient_name
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error renaming care plan: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to rename care plan: {str(e)}"
            )

    def duplicate_care_plan(self, uid: str, care_plan_id: str):
        try:
            result = self.service.duplicate_care_plan(uid, care_plan_id)
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Care plan not found"
                )
            
            new_id, new_data = result
            return {
                "status": "success",
                "message": "Care plan duplicated successfully",
                "id": new_id,
                "care_plan": self.service.format_care_plan(new_id, new_data)
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error duplicating care plan: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to duplicate care plan: {str(e)}"
            )

    def delete_care_plan(self, uid: str, care_plan_id: str):
        try:
            success = self.service.delete_care_plan(uid, care_plan_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Care plan not found"
                )
            
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
                detail=f"Failed to delete care plan: {str(e)}"
            )

    def toggle_favorite(self, uid: str, care_plan_id: str):
        try:
            favorite = self.service.toggle_favorite(uid, care_plan_id)
            if favorite is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Care plan not found"
                )
            
            return {
                "status": "success",
                "message": f"Favorite {'enabled' if favorite else 'disabled'}",
                "favorite": favorite
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error toggling favorite: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to toggle favorite: {str(e)}"
            )

    def get_recent_care_plans(self, uid: str, limit: int = 5):
        try:
            care_plans = self.service.get_recent_care_plans(uid, limit)
            return {
                "status": "success",
                "care_plans": care_plans
            }
        except Exception as e:
            logger.error(f"Error getting recent care plans: {str(e)}")
            return {
                "status": "success",
                "care_plans": []
            }