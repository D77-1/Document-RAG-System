from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    question: str
    doc_id: Optional[str] = None
    top_k: Optional[int] = 3
    threshold: Optional[float] = 0.5
    
class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
