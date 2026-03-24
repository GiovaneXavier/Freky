from datetime import datetime
from pydantic import BaseModel

from core.rules import Decision


class DetectionSchema(BaseModel):
    class_name: str
    confidence: float
    bbox: list[float]


class ScanResult(BaseModel):
    id: str
    created_at: datetime
    filename: str
    decision: Decision
    detections: list[DetectionSchema]
    processing_time_ms: float | None

    class Config:
        from_attributes = True


class FeedbackRequest(BaseModel):
    operator_id: str
    feedback: str  # "confirmed" | "false_positive" | "false_negative"


class ScanListItem(BaseModel):
    id: str
    created_at: datetime
    filename: str
    decision: Decision
    operator_feedback: str | None

    class Config:
        from_attributes = True
