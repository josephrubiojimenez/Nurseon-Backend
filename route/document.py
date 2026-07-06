from fastapi import APIRouter, HTTPException, status
from database.firebase import db
import logging

logger = logging.getLogger("documents")
doc_router = APIRouter()

@doc_router.get("/", status_code=status.HTTP_200_OK)
async def get_all_documents():
    try:
        docs_ref = db.collection("nursing_documents")
        docs = docs_ref.stream()

        document_list = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data["id"] = doc.id
            document_list.append(doc_data)

        logger.info({len(document_list)})
        return document_list

    except Exception as e:
        logger.error(f"Document not Found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error"
        )