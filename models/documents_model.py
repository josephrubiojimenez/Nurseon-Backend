# models/documents_models.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DocumentContent(BaseModel):
    type: str  # 'paragraph' or 'heading'
    text: str

class DocumentSource(BaseModel):
    id: str
    text: str

class DocumentData(BaseModel):
    id: str
    title: str
    category: str
    readTime: str
    description: str
    publishDate: str
    content: List[DocumentContent]
    sources: List[DocumentSource]

class DocumentResponse(BaseModel):
    id: str
    title: str
    category: str
    readTime: str
    description: str
    publishDate: str
    content: List[DocumentContent]
    sources: List[DocumentSource]