import json
import os
import smtplib
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from backend.database import get_db
from backend.models.db import Alert, Camera, User
from backend.schemas.alerts import AlertOut, AlertCreate, AlertStats, CommentRequest
from backend.utils.auth import get_current_user
from backend.routers.ws import manager as ws_manager

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# ── List / Stats ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[AlertOut])
def list_alerts(
    cam_id:       Optional[str]  = None,
    level:        Optional[str]  = None,
    acknowledged: Optional[bool] = None,
    escalated:    Optional[bool] = None,
    from_date:    Optional[date] = None,
    to_date:      Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Alert).order_by(desc(Alert.timestamp))
    if cam_id:       q = q.where(Alert.cam_id == cam_id)
    if level:        q = q.where(Alert.level == level)
    if acknowledged is not None:
        q = q.where(Alert.acknowledged == acknowledged)
    if escalated is not None:
        q = q.where(Alert.escalated == escalated)
    if from_date:
        q = q.where(Alert.timestamp >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        q = q.where(Alert.timestamp <= datetime.combine(to_date, datetime.max.time()))
    return db.execute(q.offset(skip).limit(limit)).scalars().all()


@router.get("/stats", response_model=AlertStats)
def alert_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    total  = db.execute(select(func.count(Alert.id))).scalar()
    high   = db.execute(select(func.count(Alert.id)).where(Alert.level == "HIGH")).scalar()
    medium = db.execute(select(func.count(Alert.id)).where(Alert.level == "MEDIUM")).scalar()
    low    = db.execute(select(func.count(Alert.id)).where(Alert.level == "LOW")).scalar()
    unack  = db.execute(select(func.count(Alert.id)).where(Alert.acknowledged == False)).scalar()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today  = db.execute(select(func.count(Alert.id)).where(Alert.timestamp >= today_start)).scalar()
    rows   = db.execute(select(Alert.cam_id, func.count(Alert.id)).group_by(Alert.cam_id)).all()
    return AlertStats(total=total, high=high, medium=medium, low=low,
                      unacknowledged=unack, today=today, by_camera={r[0]: r[1] for r in rows})


# ── Single alert ───────────────────────────────────────────────────────────────

@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    return alert


# ── Patch video_path (called by inference after clip is recorded) ─────────────

@router.patch("/{alert_id}", response_model=AlertOut)
def patch_alert(alert_id: int, body: dict, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    if "video_path" in body:
        alert.video_path = body["video_path"]
    db.commit()
    db.refresh(alert)
    return alert


# ── Create (called by inference pipeline) ─────────────────────────────────────

@router.post("", response_model=AlertOut, status_code=201)
async def create_alert(body: AlertCreate, db: Session = Depends(get_db)):
    cam = db.execute(select(Camera).where(Camera.cam_id == body.cam_id)).scalar_one_or_none()
    if not cam:
        cam = Camera(cam_id=body.cam_id, name=body.cam_id, url="")
        db.add(cam)
        db.flush()

    top_det_str = json.dumps(body.top_detection) if body.top_detection else None
    alert = Alert(
        camera_id=cam.id,
        cam_id=body.cam_id,
        level=body.level,
        # NEW fields
        alert_type=body.alert_type,
        object_detected=body.object_detected,
        confidence=body.confidence,
        detection_source=body.detection_source,
        track_id=body.track_id,
        # Legacy fields
        ae_level=body.ae_level,
        yolo_level=body.yolo_level,
        beh_level=body.beh_level,
        ae_error=body.ae_error,
        top_detection=top_det_str,
        cluster_id=body.cluster_id,
        n_detections=body.n_detections,
        loiter_sec=body.loiter_sec,
        frame_path=body.frame_path,
        video_path=body.video_path,
        timestamp=body.timestamp or datetime.utcnow(),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    await ws_manager.broadcast(json.dumps({
        "id":               alert.id,
        "cam_id":           alert.cam_id,
        "level":            alert.level,
        "alert_type":       alert.alert_type,
        "object_detected":  alert.object_detected,
        "confidence":       alert.confidence,
        "detection_source": alert.detection_source,
        "ae_level":         alert.ae_level,
        "yolo_level":       alert.yolo_level,
        "beh_level":        alert.beh_level,
        "ae_error":         alert.ae_error,
        "top_detection":    top_det_str,
        "n_detections":     alert.n_detections,
        "loiter_sec":       alert.loiter_sec,
        "frame_path":       alert.frame_path,
        "video_path":       alert.video_path,
        "timestamp":        alert.timestamp.isoformat(),
        "acknowledged":     False,
        "acknowledged_at":  None,
        "comment":          None,
        "is_false_alert":   False,
        "escalated":     False,
        "escalated_at":  None,
    }))
    return alert


# ── Acknowledge ────────────────────────────────────────────────────────────────

@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(alert_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.acknowledged      = True
    alert.acknowledged_by_id = current_user.id
    alert.acknowledged_at   = datetime.utcnow()
    db.commit()
    db.refresh(alert)
    return alert


# ── Comment ────────────────────────────────────────────────────────────────────

@router.post("/{alert_id}/comment", response_model=AlertOut)
def add_comment(alert_id: int, body: CommentRequest,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.comment = body.text
    db.commit()
    db.refresh(alert)
    return alert


# ── Manager comment ────────────────────────────────────────────────────────────

@router.post("/{alert_id}/manager-comment", response_model=AlertOut)
def add_manager_comment(alert_id: int, body: CommentRequest,
                        db: Session = Depends(get_db),
                        _: User = Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.manager_comment = body.text
    db.commit()
    db.refresh(alert)
    return alert


# ── Mark true / false ──────────────────────────────────────────────────────────

@router.post("/{alert_id}/mark-false", response_model=AlertOut)
def mark_false(alert_id: int, db: Session = Depends(get_db),
               _: User = Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.is_false_alert = True
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/mark-true", response_model=AlertOut)
def mark_true(alert_id: int, db: Session = Depends(get_db),
              _: User = Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.is_false_alert = False
    db.commit()
    db.refresh(alert)
    return alert


# ── Escalate to manager ────────────────────────────────────────────────────────

@router.post("/{alert_id}/escalate", response_model=AlertOut)
def escalate(alert_id: int, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.escalated        = True
    alert.escalated_at     = datetime.utcnow()
    alert.escalated_by_id  = current_user.id
    db.commit()
    db.refresh(alert)
    _send_escalation_email(alert, current_user)
    return alert


# ── SOS ───────────────────────────────────────────────────────────────────────

@router.post("/{alert_id}/sos")
async def sos(alert_id: int, db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):  # noqa: used for email + ws
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    print(f"\n🚨 SOS TRIGGERED — Alert #{alert_id} | Camera: {alert.cam_id} | By: {current_user.email}\n")
    await ws_manager.broadcast(json.dumps({
        "type": "sos",
        "alert_id": alert_id,
        "cam_id": alert.cam_id,
        "triggered_by": current_user.full_name,
    }))
    _send_sos_email(alert, current_user)
    return {"ok": True, "message": f"SOS triggered for alert #{alert_id}"}


# ── Email helpers ──────────────────────────────────────────────────────────────

def _send_escalation_email(alert: Alert, by_user: User):
    smtp_host     = os.getenv("SMTP_HOST", "")
    smtp_port     = int(os.getenv("SMTP_PORT", "587"))
    smtp_user     = os.getenv("SMTP_USER", "")
    smtp_pass     = os.getenv("SMTP_PASS", "")
    manager_email = os.getenv("MANAGER_EMAIL", "")
    if not all([smtp_host, smtp_user, smtp_pass, manager_email]):
        return
    try:
        msg = MIMEMultipart()
        msg["From"]    = smtp_user
        msg["To"]      = manager_email
        msg["Subject"] = f"[ATM Sentinel] {alert.level} Alert Escalated — {alert.cam_id}"
        body = (
            f"Alert ID   : {alert.id}\n"
            f"Camera     : {alert.cam_id}\n"
            f"Level      : {alert.level}\n"
            f"Time       : {alert.timestamp}\n"
            f"Comment    : {alert.comment or 'No comment provided'}\n"
            f"Escalated by: {by_user.full_name} ({by_user.email})\n"
        )
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, manager_email, msg.as_string())
    except Exception as e:
        print(f"[email] Escalation email failed: {e}")


def _send_sos_email(alert: Alert, by_user: User):
    smtp_host     = os.getenv("SMTP_HOST", "")
    smtp_port     = int(os.getenv("SMTP_PORT", "587"))
    smtp_user     = os.getenv("SMTP_USER", "")
    smtp_pass     = os.getenv("SMTP_PASS", "")
    manager_email = os.getenv("MANAGER_EMAIL", "")
    if not all([smtp_host, smtp_user, smtp_pass, manager_email]):
        return
    try:
        msg = MIMEMultipart()
        msg["From"]    = smtp_user
        msg["To"]      = manager_email
        msg["Subject"] = f"🚨 SOS — ATM Sentinel HIGH Alert at {alert.cam_id}"
        body = (
            f"URGENT: SOS triggered\n\n"
            f"Alert ID   : {alert.id}\n"
            f"Camera     : {alert.cam_id}\n"
            f"Level      : {alert.level}\n"
            f"Time       : {alert.timestamp}\n"
            f"Triggered by: {by_user.full_name} ({by_user.email})\n"
        )
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, manager_email, msg.as_string())
    except Exception as e:
        print(f"[email] SOS email failed: {e}")
