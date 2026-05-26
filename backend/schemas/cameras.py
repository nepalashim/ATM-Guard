from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CameraCreate(BaseModel):
    cam_id: str
    name: str
    url: str
    location: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool = True


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = None


class CameraOut(BaseModel):
    id: int
    cam_id: str
    name: str
    url: str
    location: str
    latitude: Optional[float]
    longitude: Optional[float]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
