from pydantic import BaseModel
from typing import Optional

class UploadResponse(BaseModel):
    status: str
    doc_id: str
    length: int
    message: Optional[str] = None

class DocItem(BaseModel):
    id: str
    name: str
    upload_time: str
    status: str
    size: Optional[int] = None

class DocListResponse(BaseModel):
    total: int
    items: list[DocItem]
    page: int
    size: int
