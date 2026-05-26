import time
import cv2
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.database import get_db
from backend.models.db import Camera
from backend.schemas.cameras import CameraOut, CameraCreate, CameraUpdate
from backend.utils.auth import get_current_user, require_role

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.execute(select(Camera)).scalars().all()


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    return cam


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(body: CameraCreate, db: Session = Depends(get_db),
                  _=Depends(require_role("admin", "manager"))):
    existing = db.execute(select(Camera).where(Camera.cam_id == body.cam_id)).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"Camera '{body.cam_id}' already exists")
    cam = Camera(**body.model_dump())
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


@router.put("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: int, body: CameraUpdate,
                  db: Session = Depends(get_db),
                  _=Depends(require_role("admin", "manager"))):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(cam, field, val)
    db.commit()
    db.refresh(cam)
    return cam


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: int, db: Session = Depends(get_db),
                  _=Depends(require_role("admin"))):
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    db.delete(cam)
    db.commit()


@router.get("/{cam_id}/stream")
def stream_camera(cam_id: str, db: Session = Depends(get_db)):
    cam = db.execute(select(Camera).where(Camera.cam_id == cam_id)).scalar_one_or_none()
    if not cam:
        raise HTTPException(404, "Camera not found")

    def generate(url: str):
        # FFmpeg properties to handle HEVC and improve RTSP reliability
        cap = cv2.VideoCapture(url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # Set timeout properties
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)      # 10s timeout
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)      # 10s read timeout
        
        reconnect_count = 0
        max_reconnect = 3
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    reconnect_count += 1
                    if reconnect_count > max_reconnect:
                        print(f"[stream] {cam_id}: Failed to reconnect after {max_reconnect} attempts")
                        break
                    time.sleep(0.5)
                    cap.release()
                    cap = cv2.VideoCapture(url)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)
                    continue
                
                reconnect_count = 0  # reset on successful read
                h, w = frame.shape[:2]
                new_w = 960
                new_h = int(h * new_w / w)
                frame = cv2.resize(frame, (new_w, new_h))
                _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                       + buf.tobytes() + b'\r\n')
                time.sleep(1 / 15)  # ~15 FPS
        except Exception as e:
            print(f"[stream] {cam_id}: Stream error - {e}")
        finally:
            cap.release()

    return StreamingResponse(
        generate(cam.url),
        media_type='multipart/x-mixed-replace; boundary=frame',
    )
