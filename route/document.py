from fastapi import APIRouter, HTTPException, status
from database.firebase import db
import logging

# Setup logging for tracking document fetches on Render
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
            # Inject the actual Firestore document ID into the dictionary
            doc_data["id"] = doc.id
            document_list.append(doc_data)

        logger.info(f"Successfully retrieved {len(document_list)} nursing documents from Firestore.")
        return document_list

    except Exception as e:
        logger.error(f"Failed to fetch nursing documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database communication sequence failed. Unable to fetch documents."
        )