# services/documents_service.py
import logging
from typing import List, Dict, Any
from fastapi import HTTPException, status

from database.firebase import db

logger = logging.getLogger("documents_service")

class DocumentsService:
    def __init__(self):
        self.collection_name = "nursing_documents"

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all nursing documents from Firestore"""
        try:
            docs_ref = db.collection(self.collection_name)
            docs = docs_ref.stream()

            document_list = []
            for doc in docs:
                doc_data = doc.to_dict()
                doc_data["id"] = doc.id
                document_list.append(doc_data)

            logger.info(f"Retrieved {len(document_list)} documents")
            return document_list

        except Exception as e:
            logger.error(f"Document not Found: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving documents"
            )

    def get_document_by_id(self, doc_id: str) -> Dict[str, Any]:
        """Get a specific document by ID"""
        try:
            doc_ref = db.collection(self.collection_name).document(doc_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found"
                )
            
            doc_data = doc.to_dict()
            doc_data["id"] = doc.id
            return doc_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving document {doc_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving document"
            )

    def get_documents_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get documents by category"""
        try:
            docs_ref = db.collection(self.collection_name).where("category", "==", category)
            docs = docs_ref.stream()

            document_list = []
            for doc in docs:
                doc_data = doc.to_dict()
                doc_data["id"] = doc.id
                document_list.append(doc_data)

            logger.info(f"Retrieved {len(document_list)} documents in category: {category}")
            return document_list

        except Exception as e:
            logger.error(f"Error retrieving documents by category: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving documents by category"
            )

    def search_documents(self, query: str) -> List[Dict[str, Any]]:
        """Search documents by title or description"""
        try:
            # Get all documents and filter
            all_docs = self.get_all_documents()
            query_lower = query.lower()
            
            filtered_docs = [
                doc for doc in all_docs
                if query_lower in doc.get("title", "").lower() 
                or query_lower in doc.get("description", "").lower()
                or query_lower in doc.get("category", "").lower()
            ]
            
            logger.info(f"Found {len(filtered_docs)} documents matching search: {query}")
            return filtered_docs

        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error searching documents"
            )