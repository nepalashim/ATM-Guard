"""
ATM Sentinel — Supervised Inference Pipeline v2
================================================
YOLO-only pipeline using YOLO11 for human loitering detection and
best-tools.pt for high-risk tool detection.

Two alert types:
  1. TOOL_DETECTED (HIGH): Tool detected with confidence >= 85%
  2. LOITERING (LOW): Person present for >100 seconds

Usage:
  python inference/main_supervised.py                   # live RTSP (camA)
  python inference/main_supervised.py --video path/to/video  # offline test
  python inference/main_supervised.py --video path/to/video --show  # with display
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch
import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inference.config import (
    TOOL_YOLO_WEIGHTS, TOOL_YOLO_CONF, DEVICE, IMGSZ,
    YOLO_HUMAN_DETECTOR_MODEL, YOLO_CONF_THRESHOLD,
    LOITERING_TIME_THRESHOLD, LOITERING_GRACE_PERIOD, PERSON_PRESENCE_DETECTION,
    LOG_DIR, API_ALERT_ENDPOINT, API_ENABLED, API_TIMEOUT, CAMERAS, ROOT,
)
from inference.human_detector import HumanDetector

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


# ── Tool to threat mapping ────────────────────────────────────────────────────

TOOL_THREAT_MAP = {
    # All 18 trained tools — HIGH threat
    "crowbar":       "HIGH",
    "hammer":        "HIGH",
    "screwdriver":   "HIGH",
    "drill":         "HIGH",
    "drill_bit":     "HIGH",
    "angle_grinder": "HIGH",
    "utility_knife": "HIGH",
    "hacksaw":       "HIGH",
    "axe":           "HIGH",
    "jack_hammer":   "HIGH",
    "socket_wrench": "HIGH",
    "wrench":        "HIGH",
    "pliers":        "HIGH",
    "chisel":        "HIGH",
    "file_tool":     "HIGH",
    "caulking_gun":  "HIGH",
    "torque_wrench": "HIGH",
    "hoe_tool":      "HIGH",
}


def _runtime_device() -> str:
    """Return a device string that is valid for the installed torch build."""
    if DEVICE == "cuda" and torch.cuda.is_available():
        return "cuda"
    return "cpu"


class ToolYoloDetector:
    """Fine-tuned YOLO detector for HIGH-risk tool detection."""

    def __init__(self, model_path: Path, device: str, conf_threshold: float):
        if YOLO is None:
            raise ImportError("ultralytics not installed. Install with: pip install ultralytics")
        if not model_path.exists():
            raise FileNotFoundError(f"Tool YOLO model not found: {model_path}")

        self.model = YOLO(str(model_path))
        self.device = device
        self.conf_threshold = conf_threshold
        self.names = self.model.names or {}

    def detect(self, frame_bgr: np.ndarray) -> list[dict]:
        results = self.model(
            frame_bgr,
            imgsz=IMGSZ,
            conf=self.conf_threshold,
            device=self.device,
            verbose=False,
        )[0]

        detections: list[dict] = []
        if results.boxes is None:
            return detections

        for box in results.boxes:
            class_idx = int(box.cls.item())
            class_name = str(self.names.get(class_idx, f"class_{class_idx}")).replace(" ", "_")
            conf = float(box.conf.item())
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            detections.append({
                "class_idx": class_idx,
                "class_name": class_name,
                "confidence": conf,
                "bbox": (x1, y1, x2, y2),
            })

        return detections


# ── Alert logger ──────────────────────────────────────────────────────────────

class AlertLogger:
    """Logs and transmits alerts to backend."""
    
    def __init__(self):
        LOG_DIR.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._cooldown: dict[str, float] = {}
        self._alert_log = LOG_DIR / "alerts.jsonl"
    
    def emit(self, alert: dict):
        """Log and POST alert to backend."""
        cam_id = alert["cam_id"]
        level = alert["level"]
        alert_type = alert.get("alert_type", "TOOL_DETECTED")
        
        # Cooldown key: per-track for LOITERING (each person fires once), per-type for tools
        track_id = alert.get("track_id", "")
        key = f"{cam_id}_LOITERING_{track_id}" if alert_type == "LOITERING" else f"{cam_id}_{alert_type}"
        now = time.time()
        last = self._cooldown.get(key, 0)
        if now - last < 30:
            return
        self._cooldown[key] = now
        
        # Print to console
        ts = alert.get("timestamp", datetime.now().isoformat())[:19]
        obj = alert.get("object_detected", "unknown")
        conf = alert.get("confidence", 0)
        
        colour_map = {"HIGH": "\033[91m", "MEDIUM": "\033[93m", "LOW": "\033[94m", "NONE": ""}
        reset = "\033[0m"
        c = colour_map.get(level, "")
        
        if alert_type == "TOOL_DETECTED":
            print(f"{c}[{ts}] [{cam_id}] {alert_type}={level:6s} tool={obj:20s} conf={conf:.2%}{reset}")
        else:  # LOITERING
            duration = alert.get("loiter_sec", 0)
            print(f"{c}[{ts}] [{cam_id}] {alert_type}={level:6s} duration={duration:.0f}s{reset}")
        
        # Write to JSONL
        with self._lock:
            with open(self._alert_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert) + "\n")
        
        # POST to backend — store returned DB id on the alert dict for clip patching
        if API_ENABLED:
            db_id = self._post_to_api(alert)
            if db_id:
                alert["_db_id"] = db_id
    
    def _post_to_api(self, alert: dict) -> int | None:
        """Send alert to FastAPI backend. Returns the created alert's DB id."""
        try:
            payload = {
                "cam_id": alert["cam_id"],
                "level": alert["level"],
                "alert_type": alert.get("alert_type", "TOOL_DETECTED"),
                "object_detected": alert.get("object_detected"),
                "confidence": alert.get("confidence"),
                "detection_source": alert.get("detection_source", "YOLO"),
                "track_id": alert.get("track_id"),
                "loiter_sec": alert.get("loiter_sec", 0.0),
                "timestamp": alert.get("timestamp"),
                "ae_level": "NONE",
                "yolo_level": "NONE",
                "beh_level": "NONE",
                "ae_error": 0.0,
                "top_detection": None,
                "cluster_id": 0,
                "n_detections": 0,
                "frame_path": alert.get("frame_path"),
                "video_path": alert.get("video_path"),
            }
            resp = httpx.post(API_ALERT_ENDPOINT, json=payload, timeout=API_TIMEOUT)
            if resp.status_code == 201:
                return resp.json().get("id")
        except Exception as e:
            print(f"  [API Error] {e}")
        return None


# ── Frame processor ───────────────────────────────────────────────────────────

class FrameProcessor:
    """Processes frames and detects HIGH tool alerts plus LOW loitering alerts."""
    
    def __init__(self, cam_id: str, tool_detector: ToolYoloDetector, logger: AlertLogger, human_detector=None, rtsp_url: str = ""):
        self.cam_id = cam_id
        self.tool_detector = tool_detector
        self.logger = logger
        self.human_detector = human_detector
        self.rtsp_url = rtsp_url
        self.frame_count = 0
        
        # Per-track loitering state (keyed by ByteTrack track_id)
        self._track_first_seen: dict[int, float] = {}
        self._track_last_seen:  dict[int, float] = {}
        self._alerted_tracks:   set[int]         = set()

        # Snapshot storage dir
        self._snap_dir = ROOT / "storage" / "snapshots"
        self._snap_dir.mkdir(parents=True, exist_ok=True)

    def _save_snapshot(self, frame: np.ndarray, cam_id: str, label: str) -> str | None:
        """Save frame as JPEG and return relative path for serving via /storage/."""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{cam_id}_{label}_{ts}.jpg"
            path = self._snap_dir / filename
            cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return f"storage/snapshots/{filename}"
        except Exception as e:
            print(f"  [Snapshot Error] {e}")
            return None

    def _record_clip(self, rtsp_url: str, cam_id: str, label: str, duration: int = 5) -> str | None:
        """Record a short video clip from the RTSP stream in a background thread."""
        try:
            clips_dir = ROOT / "storage" / "clips"
            clips_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{cam_id}_{label}_{ts}.mp4"
            path = clips_dir / filename

            cap = cv2.VideoCapture(rtsp_url)
            fps = min(cap.get(cv2.CAP_PROP_FPS) or 20, 30)
            # Cap at 1280x720 for browser-friendly file size
            w   = min(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)  or 1280), 1280)
            h   = min(int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720),  720)
            # avc1 = H.264 — universally supported by browsers
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            out = cv2.VideoWriter(str(path), fourcc, fps, (w, h))

            end = time.time() + duration
            while time.time() < end:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame.shape[1] != w or frame.shape[0] != h:
                    frame = cv2.resize(frame, (w, h))
                out.write(frame)

            cap.release()
            out.release()
            return f"storage/clips/{filename}" if path.exists() and path.stat().st_size > 0 else None
        except Exception as e:
            print(f"  [Clip Error] {e}")
            return None
    
    def process(self, frame_bgr: np.ndarray) -> dict:
        """
        Process single frame:
        1. Run fine-tuned YOLO tool detector
        2. Track loitering with YOLO11 human detections
        
        Returns alert dict if threshold met, else None.
        """
        self.frame_count += 1
        ts = datetime.now().isoformat()
        alerts = []

        # Pre-resize to 1280×720 — improves both YOLO person detection and
        fh, fw = frame_bgr.shape[:2]
        if fw > 1280:
            frame_bgr = cv2.resize(frame_bgr, (1280, 720), interpolation=cv2.INTER_LINEAR)

        # DETECTION 1: HIGH alerts from best-tools.pt.
        # YOLO detects each person → we crop their body region (+ 20% padding)
        try:
            tool_dets = self.tool_detector.detect(frame_bgr)
            high_tool_dets = [
                det for det in tool_dets
                if TOOL_THREAT_MAP.get(det["class_name"], "HIGH") == "HIGH"
            ]

            if high_tool_dets:
                best = max(high_tool_dets, key=lambda det: det["confidence"])
                best_conf = best["confidence"]
                best_class = best["class_name"]
                cooldown_key = f"{self.cam_id}_TOOL_DETECTED"
                in_cooldown = time.time() - self.logger._cooldown.get(cooldown_key, 0) < 30
                snap = None if in_cooldown else self._save_snapshot(frame_bgr, self.cam_id, best_class)
                alert = {
                    "cam_id": self.cam_id,
                    "level": "HIGH",
                    "alert_type": "TOOL_DETECTED",
                    "object_detected": best_class,
                    "confidence": best_conf,
                    "detection_source": "YOLO11_tool_detector",
                    "timestamp": ts,
                    "loiter_sec": 0.0,
                    "frame_path": snap,
                    "video_path": None,
                    # Legacy fields
                    "ae_level": "NONE",
                    "yolo_level": "HIGH",
                    "beh_level": "NONE",
                    "ae_error": 0.0,
                    "top_detection": {"class_name": best_class, "confidence": best_conf, "bbox": best["bbox"]},
                    "cluster_id": 0,
                    "n_detections": len(high_tool_dets),
                }
                alerts.append(alert)

                # Record 5s clip in background — update alert video_path via API when done
                if snap and self.rtsp_url:
                    rtsp      = self.rtsp_url
                    cam       = self.cam_id
                    lbl       = best_class
                    alert_ref = alert  # mutable dict — _db_id is set by emit() before clip finishes
                    def _clip_and_patch(rtsp=rtsp, cam=cam, lbl=lbl, alert_ref=alert_ref):
                        clip_path = self._record_clip(rtsp, cam, lbl, duration=5)
                        # emit() runs synchronously and sets _db_id well before 5s clip finishes
                        db_id = alert_ref.get("_db_id")
                        if clip_path and db_id and API_ENABLED:
                            try:
                                httpx.patch(f"{API_ALERT_ENDPOINT}/{db_id}",
                                            json={"video_path": clip_path},
                                            timeout=API_TIMEOUT)
                            except Exception:
                                pass
                    threading.Thread(target=_clip_and_patch, daemon=True).start()

        except Exception as e:
            print(f"  [Tool YOLO Error] {e}")
        
        # ── DETECTION 2: Loitering (ByteTrack per-person tracking) ────────────
        if PERSON_PRESENCE_DETECTION and self.human_detector is not None:
            now = time.time()
            tracked = self.human_detector.detect_and_track(frame_bgr)
            active_ids = {d['track_id'] for d in tracked}

            for det in tracked:
                tid = det['track_id']

                # Register new track
                if tid not in self._track_first_seen:
                    self._track_first_seen[tid] = now
                self._track_last_seen[tid] = now

                # Fire LOW alert once per track when dwell time exceeds threshold
                dwell = now - self._track_first_seen[tid]
                if dwell >= LOITERING_TIME_THRESHOLD and tid not in self._alerted_tracks:
                    self._alerted_tracks.add(tid)
                    snap = self._save_snapshot(frame_bgr, self.cam_id, f"loiter_track{tid}")
                    alert = {
                        "cam_id": self.cam_id,
                        "level": "LOW",
                        "alert_type": "LOITERING",
                        "object_detected": "human",
                        "track_id": tid,
                        "confidence": det['confidence'],
                        "detection_source": "ByteTrack+YOLO",
                        "timestamp": ts,
                        "loiter_sec": round(dwell, 1),
                        "frame_path": snap,
                        "video_path": None,
                        # Legacy fields
                        "ae_level": "NONE",
                        "yolo_level": "NONE",
                        "beh_level": "LOW",
                        "ae_error": 0.0,
                        "top_detection": {"class_name": "human", "confidence": det['confidence']},
                        "cluster_id": 0,
                        "n_detections": len(tracked),
                    }
                    alerts.append(alert)

            # Grace-period cleanup: purge tracks not seen for > LOITERING_GRACE_PERIOD seconds
            for tid in list(self._track_last_seen):
                if tid not in active_ids:
                    if now - self._track_last_seen[tid] > LOITERING_GRACE_PERIOD:
                        self._track_first_seen.pop(tid, None)
                        self._track_last_seen.pop(tid, None)
                        self._alerted_tracks.discard(tid)
        
        # Emit all alerts
        for alert in alerts:
            self.logger.emit(alert)
        
        return {"alerts": alerts, "frame_count": self.frame_count}
    
    def _detect_motion(self, frame_bgr: np.ndarray) -> bool:
        """
        Fallback motion/presence detection using Laplacian variance.
        Used when YOLO human detector is not available.
        
        Returns True if significant motion detected in frame.
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            
            # Apply GaussianBlur to reduce noise
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            # Compute Laplacian variance (edge detection)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            variance = laplacian.var()
            
            # Threshold: if variance > threshold, consider it motion/presence
            return variance > 500.0
        except Exception as e:
            print(f"    [Motion detection error] {e}")
            return False


# ── Main inference loop ───────────────────────────────────────────────────────

def run_camera(cam_id: str, camera_config: dict, logger: AlertLogger):
    """Run inference loop for a single camera with automatic reconnection."""
    
    print(f"\n[{cam_id}] Starting inference...")
    
    device = _runtime_device()
    if DEVICE == "cuda" and device == "cpu":
        print("  [!] CUDA requested but unavailable; using CPU")

    # Load fine-tuned YOLO tool detector
    tool_detector = ToolYoloDetector(
        model_path=TOOL_YOLO_WEIGHTS,
        device=device,
        conf_threshold=TOOL_YOLO_CONF,
    )
    print(f"  [+] Tool YOLO loaded ({TOOL_YOLO_WEIGHTS.name})")
    
    # Load YOLO11 human detector for LOW loitering alerts
    human_detector = HumanDetector(
        model_path=str(YOLO_HUMAN_DETECTOR_MODEL),
        device=device,
        conf_threshold=YOLO_CONF_THRESHOLD,
    )
    print(f"  [+] YOLO human detector loaded ({YOLO_HUMAN_DETECTOR_MODEL.name})")
    
    # Open video source with reconnection logic
    source = camera_config.get("url", "rtsp://...")
    processor = FrameProcessor(cam_id, tool_detector, logger, human_detector, rtsp_url=source)
    
    reconnect_attempts = 0
    max_reconnect = 5
    
    while reconnect_attempts < max_reconnect:
        try:
            print(f"  Connecting to {source}...")
            cap = cv2.VideoCapture(source)
            
            # Set RTSP timeout and read timeout
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)

            if not cap.isOpened():
                print(f"  [RTSP] Could not open stream, retrying...")
                reconnect_attempts += 1
                time.sleep(min(2 ** reconnect_attempts, 30))
                continue
            
            print(f"  [RTSP] Connected ✓")
            reconnect_attempts = 0  # Reset counter on successful connection

            fps = camera_config.get("fps", 5)
            frame_interval = 1.0 / fps
            last_frame_time = 0
            frame_fail_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    frame_fail_count += 1
                    if frame_fail_count > 10:  # Allow some transient failures
                        print(f"  [RTSP] Stream failed (10 consecutive read failures)")
                        break
                    time.sleep(0.1)
                    continue
                
                frame_fail_count = 0  # Reset on successful read
                
                # Skip frames to maintain target FPS
                now = time.time()
                if now - last_frame_time < frame_interval:
                    continue
                last_frame_time = now
                
                # Process frame
                result = processor.process(frame)
        
        except KeyboardInterrupt:
            print(f"  [Interrupted]")
            break
        except Exception as e:
            print(f"  [Error] {e}")
        finally:
            cap.release()
            cv2.destroyAllWindows()
        
        # Reconnect attempt
        reconnect_attempts += 1
        if reconnect_attempts < max_reconnect:
            wait = min(2 ** reconnect_attempts, 30)
            print(f"  [RTSP] Reconnecting in {wait}s (attempt {reconnect_attempts}/{max_reconnect})...")
            time.sleep(wait)
    
    if reconnect_attempts >= max_reconnect:
        print(f"  [{cam_id}] Failed to maintain connection after {max_reconnect} attempts.")
    else:
        print(f"  [{cam_id}] Stopped.")


def run():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(
        description="ATM Sentinel Supervised Inference Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cam", type=str, default="camA", help="Camera ID (default: camA)")
    parser.add_argument("--video", type=str, help="Test on offline video file")
    parser.add_argument("--show", action="store_true", help="Display video window")
    args = parser.parse_args()
    
    LOG_DIR.mkdir(exist_ok=True)
    logger = AlertLogger()
    
    # Load camera config
    if args.video:
        # Offline video test
        camera_config = {"url": args.video, "fps": 5, "name": "Test Video"}
    else:
        # Live RTSP camera
        camera_config = CAMERAS.get(args.cam, CAMERAS.get("camA"))
    
    # Run inference
    run_camera(args.cam, camera_config, logger)


if __name__ == "__main__":
    run()
