import logging
from services.documents_service import DocumentsService

logger = logging.getLogger("documents_controller")

class DocumentsController:
    def __init__(self):
        self.service = DocumentsService()

    def get_all_documents(self):
        logger.info("Controller passing request to get all documents.")
        return self.service.get_all_documents()

    def get_document(self, doc_id: str):
        logger.info(f"Controller passing request to get document: {doc_id}")
        return self.service.get_document_by_id(doc_id)

    def get_documents_by_category(self, category: str):
        logger.info(f"Controller passing request to filter by category: {category}")
        return self.service.get_documents_by_category(category)

    def search_documents(self, query: str):
        logger.info(f"Controller passing search request with query: {query}")
        return self.service.search_documents(query)