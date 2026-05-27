# importing libraries
from pydantic import BaseModel, Field
from typing import Optional

# class for upload request
class UploadRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None


# class for upload response
class UploadResponse(BaseModel):
    bot_id: str
    chunks_created: int
    source: str
    message: str


# class for chat message
class ChatMessage(BaseModel):
    role: str 
    content: str


# class for chat request
class ChatRequest(BaseModel):
    bot_id: str
    user_message: str
    conversation_history: list[ChatMessage] = Field(default_factory=list)


# class for stats response
class StatsResponse(BaseModel):
    bot_id: str
    total_messages: int
    avg_latency_ms: float
    estimated_cost_usd: float
    unanswered_questions: int
