from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class AlertCreate(BaseModel):
    cam_id: str
    level: str
    
    # NEW: Supervised approach
    alert_type: str = "TOOL_DETECTED"  # "TOOL_DETECTED" or "LOITERING"
    object_detected: Optional[str] = None  # "crowbar", "drill", "human", etc.
    confidence: Optional[float] = None  # 0-1
    detection_source: str = "YOLO"  # "YOLO11_tool_detector" or "ByteTrack+YOLO"
    track_id: Optional[int] = None  # ByteTrack person track ID (LOITERING only)
    
    # Legacy fields (for backward compatibility)
    ae_level: str = "NONE"
    yolo_level: str = "NONE"
    beh_level: str = "NONE"
    ae_error: float = 0.0
    top_detection: Optional[Any] = None
    cluster_id: int = 0
    n_detections: int = 0
    loiter_sec: float = 0.0
    frame_path: Optional[str] = None
    video_path: Optional[str] = None
    timestamp: Optional[datetime] = None


class AlertOut(BaseModel):
    id: int
    cam_id: str
    level: str
    
    # NEW fields
    alert_type: str
    object_detected: Optional[str]
    confidence: Optional[float]
    detection_source: str
    track_id: Optional[int] = None
    
    # Legacy fields
    ae_level: str
    yolo_level: str
    beh_level: str
    ae_error: float
    top_detection: Optional[str]
    n_detections: int
    loiter_sec: float
    frame_path: Optional[str]
    video_path: Optional[str]
    timestamp: datetime
    acknowledged: bool
    acknowledged_at: Optional[datetime]
    comment: Optional[str]
    manager_comment: Optional[str] = None
    is_false_alert: bool
    escalated: bool
    escalated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AlertStats(BaseModel):
    total: int
    high: int
    medium: int
    low: int
    unacknowledged: int
    today: int
    by_camera: dict


class CommentRequest(BaseModel):
    text: str
