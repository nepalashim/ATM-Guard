from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(120), unique=True, nullable=False, index=True)
    full_name     = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role          = Column(Enum("admin", "manager", "supervisor", name="user_role"), default="supervisor")
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    acknowledged_alerts = relationship("Alert", foreign_keys="Alert.acknowledged_by_id", back_populates="acknowledged_by_user")


class Camera(Base):
    __tablename__ = "cameras"

    id         = Column(Integer, primary_key=True, index=True)
    cam_id     = Column(String(20), unique=True, nullable=False)
    name       = Column(String(120), nullable=False)
    url        = Column(String(255), nullable=False)
    location   = Column(String(255), default="")
    latitude   = Column(Float, nullable=True)
    longitude  = Column(Float, nullable=True)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    alerts = relationship("Alert", back_populates="camera")


class Alert(Base):
    __tablename__ = "alerts"

    id               = Column(Integer, primary_key=True, index=True)
    camera_id        = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    cam_id           = Column(String(20), nullable=False)
    level            = Column(Enum("HIGH", "MEDIUM", "LOW", "NONE", name="alert_level"), nullable=False)
    
    # NEW: Alert classification
    alert_type       = Column(String(50), default="TOOL_DETECTED")  # "TOOL_DETECTED" or "LOITERING"
    object_detected  = Column(String(80), nullable=True)  # "crowbar", "drill", "human", etc.
    confidence       = Column(Float, nullable=True)  # 0-1, confidence of detection
    detection_source = Column(String(50), default="YOLO")  # "YOLO11_tool_detector", "ByteTrack+YOLO"
    track_id         = Column(Integer, nullable=True)  # ByteTrack person track ID (LOITERING only)
    
    # OLD: Legacy fields (kept for backward compatibility)
    ae_level         = Column(String(10), default="NONE")
    yolo_level       = Column(String(10), default="NONE")
    beh_level        = Column(String(10), default="NONE")
    ae_error         = Column(Float, default=0.0)
    top_detection    = Column(Text, nullable=True)
    cluster_id       = Column(Integer, default=0)
    n_detections     = Column(Integer, default=0)
    loiter_sec       = Column(Float, default=0.0)  # Duration of loitering in seconds
    
    # Media & paths
    frame_path       = Column(String(512), nullable=True)
    video_path       = Column(String(512), nullable=True)
    thumbnail        = Column(String(512), nullable=True)
    timestamp        = Column(DateTime, default=datetime.utcnow, index=True)

    # Review fields
    acknowledged       = Column(Boolean, default=False)
    acknowledged_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at    = Column(DateTime, nullable=True)
    comment            = Column(Text, nullable=True)   # supervisor notes
    manager_comment    = Column(Text, nullable=True)   # manager notes (after escalation)
    is_false_alert     = Column(Boolean, default=False)
    escalated          = Column(Boolean, default=False)
    escalated_at       = Column(DateTime, nullable=True)
    escalated_by_id    = Column(Integer, ForeignKey("users.id"), nullable=True)

    camera               = relationship("Camera", back_populates="alerts")
    acknowledged_by_user = relationship("User", foreign_keys=[acknowledged_by_id], back_populates="acknowledged_alerts")
    escalated_by_user    = relationship("User", foreign_keys=[escalated_by_id])
