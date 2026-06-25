from fastapi import APIRouter
from database.firebase import db

doc_router = APIRouter()

@doc_router.get("/")
async def get_all_documents():
    docs_ref = db.collection("nursing_documents")
    docs = docs_ref.stream()
    return [doc.to_dict() for doc in docs]