from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime

class ConversationContext(BaseModel):
    user_preferences: Optional[Dict[str, Any]] = None
    current_products: Optional[List[int]] = None
    session_data: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    context: Optional[ConversationContext] = None

class ToolCall(BaseModel):
    function: str
    arguments: Dict[str, Any]
    result: Any

class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    tool_calls: Optional[List[ToolCall]] = []
    timestamp: datetime