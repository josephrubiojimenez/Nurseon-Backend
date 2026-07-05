# routes/document.py
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional

from controllers.documents_controller import DocumentsController

logger = logging.getLogger("documents")
doc_router = APIRouter()
controller = DocumentsController()

@doc_router.get("/", status_code=status.HTTP_200_OK)
async def get_all_documents():
    return controller.get_all_documents()

@doc_router.get("/{doc_id}", status_code=status.HTTP_200_OK)
async def get_document(doc_id: str):
    return controller.get_document(doc_id)

@doc_router.get("/category/{category}", status_code=status.HTTP_200_OK)
async def get_documents_by_category(category: str):
    return controller.get_documents_by_category(category)

@doc_router.get("/search/", status_code=status.HTTP_200_OK)
async def search_documents(query: str = Query(..., min_length=1)):
    return controller.search_documents(query)