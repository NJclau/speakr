from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

class JobCreateRequest(BaseModel):
    language: str = "auto"
    target_language: Optional[str] = None
    enable_diarization: bool = True
    model_size: str = "medium"
    priority: int = 2 # JobPriority.NORMAL
    processing_options: Dict[str, Any] = {}
    custom_vocabulary: Optional[List[str]] = None

class JobResponse(BaseModel):
    id: uuid.UUID
    status: str
    queue_position: Optional[int]
    estimated_wait_time: Optional[str]
    created_at: datetime
    progress: Optional[int]
    error_message: Optional[str]

class TranscriptSegmentOut(BaseModel):
    start: float
    end: float
    text: str
    confidence: float
    speaker: Optional[str]
    language: Optional[str]

class TranscriptResponse(BaseModel):
    id: uuid.UUID
    segments: List[TranscriptSegmentOut]
    metadata: Dict[str, Any]
    summary: Optional[str]
    export_formats: List[str] = ["txt", "srt", "vtt", "json", "docx"]

class Job(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    status: str
    original_filename: Optional[str] = None
    file_size: Optional[int] = None
    duration_seconds: Optional[int] = None
    language: str
    processing_options: Dict[str, Any]
    transcript_data: Optional[Dict[str, Any]] = None
    confidence_scores: Optional[Dict[str, Any]] = None
    speaker_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    queue_position: Optional[int] = None
    priority: int

    class Config:
        orm_mode = True
