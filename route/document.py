# routes/document.py
from fastapi import APIRouter, HTTPException, status
from controllers.documents_controller import DocumentsController
import logging

logger = logging.getLogger("documents")
doc_router = APIRouter()
controller = DocumentsController()

@doc_router.get("/", status_code=status.HTTP_200_OK)
async def get_all_documents():
    return controller.get_all_documents()