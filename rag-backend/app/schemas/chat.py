from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    question: str
    top_k: Optional[int] = 3
    
class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
