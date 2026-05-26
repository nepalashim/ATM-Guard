"""
ATM Sentinel — Inference Pipeline
==================================
Reads RTSP streams (or a local video for testing), runs all four models
on each frame, fuses signals, and outputs alerts.

Each camera runs in its own thread. Alerts are logged to logs/alerts.jsonl
and optionally POSTed to the FastAPI backend.

Usage:
  python inference/main.py                        # live RTSP (both cameras)
  python inference/main.py --cam camA             # single camera
  python inference/main.py --video path/to/video  # offline test on video file
  python inference/main.py --video path/to/video --show  # display window
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# Add project root to path so inference/ imports work from any cwd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inference.config import (
    CAMERAS, ALERT_LOG, LOG_DIR, API_ALERT_ENDPOINT,
    API_ENABLED, API_TIMEOUT, ALERT_COOLDOWN, MIN_ALERT_LEVEL,
    TOOL_YOLO_BBOX_PADDING,
)
from inference.models import ModelRegistry
from inference.score_fusion import fuse, _load_thresholds

# ── Alert level ordering ──────────────────────────────────────────────────────
LEVEL_INT = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


# ── Alert logger ──────────────────────────────────────────────────────────────

class AlertLogger:
    def __init__(self):
        LOG_DIR.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._cooldown: dict[str, float] = {}   # cam_id -> last alert time

    def emit(self, alert: dict):
        cam_id = alert["cam_id"]
        level  = alert["alert"]

        # Suppress below min level
        if LEVEL_INT.get(level, 0) < LEVEL_INT.get(MIN_ALERT_LEVEL, 1):
            return

        # Cooldown per camera
        now = time.time()
        last = self._cooldown.get(cam_id, 0)
        if now - last < ALERT_COOLDOWN:
            return
        self._cooldown[cam_id] = now

        ts = alert.get("timestamp", datetime.now().isoformat())
        colour = {"HIGH": "\033[91m", "MEDIUM": "\033[93m",
                  "LOW": "\033[94m",  "NONE": ""}
        reset  = "\033[0m"
        c = colour.get(level, "")
        print(f"{c}[{ts[:19]}] [{cam_id}] ALERT={level:6s} "
              f"ae={alert.get('ae_level')} yolo={alert.get('yolo_level')} "
              f"beh={alert.get('beh_level')}  "
              f"err={alert.get('ae_error', 0):.5f}{reset}")
        if alert.get("top_det"):
            d = alert["top_det"]
            print(f"             Detected: {d['class_name']} (conf={d['conf']}, risk={d['risk']})")

        # Write to JSONL log
        with self._lock:
            with open(ALERT_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert) + "\n")

        # POST to API
        if API_ENABLED:
            self._post_to_api(alert)

    def _post_to_api(self, alert: dict):
        try:
            import httpx
            payload = {
                "cam_id":       alert["cam_id"],
                "level":        alert["alert"],
                "ae_level":     alert.get("ae_level", "NONE"),
                "yolo_level":   alert.get("yolo_level", "NONE"),
                "beh_level":    alert.get("beh_level", "NONE"),
                "ae_error":     alert.get("ae_error", 0.0),
                "top_detection": alert.get("top_det"),
                "cluster_id":   alert.get("cluster_id", 0),
                "n_detections": alert.get("n_detections", 0),
                "loiter_sec":   alert.get("loiter_sec", 0.0),
                "frame_path":   alert.get("frame_path"),
                "video_path":   alert.get("video_path"),
                "timestamp":    alert.get("timestamp"),
            }
            httpx.post(API_ALERT_ENDPOINT, json=payload, timeout=API_TIMEOUT)
        except Exception:
            pass   # don't crash inference if backend is down


# ── Frame processor ───────────────────────────────────────────────────────────

class FrameProcessor:
    def __init__(self, cam_id: str, registry: ModelRegistry, logger: AlertLogger):
        self.cam_id       = cam_id
        self.registry     = registry
        self.logger       = logger
        self.thresholds   = _load_thresholds()
        self._first_seen: float | None = None
        self._frame_buffer: deque = deque(maxlen=75)  # ~5s at 15 fps

    def _crop_bbox_with_padding(self, frame_bgr: np.ndarray, bbox: list, padding: float = 0.2) -> np.ndarray | None:
        """
        Crop bounding box from frame with padding.
        
        Args:
            frame_bgr: Full frame
            bbox: [x1, y1, x2, y2] in image coordinates
            padding: Fraction of bbox size to add as padding (0.2 = 20%)
        
        Returns:
            Cropped region or None if crop is invalid
        """
        h, w = frame_bgr.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        
        # Calculate padding
        box_w = x2 - x1
        box_h = y2 - y1
        pad_x = int(box_w * padding)
        pad_y = int(box_h * padding)
        
        # Apply padding with bounds checking
        x1_crop = max(0, x1 - pad_x)
        y1_crop = max(0, y1 - pad_y)
        x2_crop = min(w, x2 + pad_x)
        y2_crop = min(h, y2 + pad_y)
        
        # Validate crop
        if x2_crop <= x1_crop or y2_crop <= y1_crop:
            return None
        
        return frame_bgr[y1_crop:y2_crop, x1_crop:x2_crop].copy()

    def process(self, frame_bgr: np.ndarray) -> dict:
        ts = datetime.now().isoformat()
        self._frame_buffer.append(frame_bgr.copy())

        # Track loitering
        if self._first_seen is None:
            self._first_seen = time.time()
        loiter_sec = time.time() - self._first_seen

        # Run all models
        ae_error    = self.registry.anomaly.run(frame_bgr)
        yolo_person_dets = self.registry.yolo.run(frame_bgr)
        cluster_id  = self.registry.behaviour.run(frame_bgr)

        if cluster_id == -1:
            cluster_id = 0   # default until buffer is full

        # Tool detection: for each person, detect tools in cropped region
        tool_dets = []
        for person_det in yolo_person_dets:
            # Only process person detections (class_idx 0)
            if person_det.get("class_idx") != 0:
                continue
            
            person_crop = self._crop_bbox_with_padding(frame_bgr, person_det["box"], TOOL_YOLO_BBOX_PADDING)
            if person_crop is None or person_crop.size == 0:
                continue
            
            # Run tool detector on cropped region
            tools_in_crop = self.registry.tool_detector.run(person_crop)
            tool_dets.extend(tools_in_crop)

        # Fuse signals (use tool detections instead of generic YOLO detections)
        result = fuse(
            ae_error   = ae_error,
            yolo_dets  = tool_dets,  # now contains tool detections
            cluster_id = cluster_id,
            loiter_sec = loiter_sec,
            thresholds = self.thresholds,
        )

        frame_path, video_path = None, None
        if LEVEL_INT.get(result.get("alert", "NONE"), 0) >= LEVEL_INT.get(MIN_ALERT_LEVEL, 1):
            frame_path, video_path = self._save_media(frame_bgr, ts)

        alert = {
            "timestamp":    ts,
            "cam_id":       self.cam_id,
            "loiter_sec":   round(loiter_sec, 1),
            "n_detections": len(tool_dets),  # count tool detections
            "cluster_id":   cluster_id,
            "frame_path":   frame_path,
            "video_path":   video_path,
            **result,
        }

        self.logger.emit(alert)
        return alert

    def reset_loiter(self):
        self._first_seen = None

    def _save_media(self, frame_bgr: np.ndarray, ts: str) -> tuple:
        safe_ts = ts.replace(':', '-').replace('.', '-')[:19]
        storage   = Path(__file__).resolve().parent.parent / "storage"
        snap_dir  = storage / "snapshots"
        video_dir = storage / "videos"
        snap_dir.mkdir(parents=True, exist_ok=True)
        video_dir.mkdir(parents=True, exist_ok=True)

        snap_name = f"{self.cam_id}_{safe_ts}.jpg"
        cv2.imwrite(str(snap_dir / snap_name), frame_bgr)
        frame_path = f"storage/snapshots/{snap_name}"

        frames = list(self._frame_buffer)
        video_path = None
        if frames:
            h, w = frames[0].shape[:2]
            vid_name = f"{self.cam_id}_{safe_ts}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(video_dir / vid_name), fourcc, 15.0, (w, h))
            for f in frames:
                out.write(f)
            out.release()
            video_path = f"storage/videos/{vid_name}"

        return frame_path, video_path


# ── Camera reader thread ──────────────────────────────────────────────────────

class CameraThread(threading.Thread):
    def __init__(
        self,
        cam_id:    str,
        source:    str,
        target_fps: int,
        processor: FrameProcessor,
        show:      bool = False,
    ):
        super().__init__(name=f"cam-{cam_id}", daemon=True)
        self.cam_id     = cam_id
        self.source     = source
        self.target_fps = target_fps
        self.processor  = processor
        self.show       = show
        self._stop_evt  = threading.Event()
        self.frame_count = 0
        self.alert_counts: dict[str, int] = {"NONE": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0}

    def stop(self):
        self._stop_evt.set()

    def run(self):
        interval = 1.0 / self.target_fps
        print(f"[{self.cam_id}] Opening: {self.source}")

        while not self._stop_evt.is_set():
            cap = cv2.VideoCapture(self.source)
            if not cap.isOpened():
                print(f"[{self.cam_id}] Cannot open source, retrying in 5s...")
                time.sleep(5)
                continue

            print(f"[{self.cam_id}] Stream opened. Processing at {self.target_fps} fps.")
            last_proc = 0.0

            while not self._stop_evt.is_set():
                ret, frame = cap.read()
                if not ret:
                    print(f"[{self.cam_id}] Stream ended or lost. Reconnecting...")
                    break

                now = time.time()
                if now - last_proc < interval:
                    continue
                last_proc = now

                try:
                    result = self.processor.process(frame)
                    self.frame_count += 1
                    self.alert_counts[result["alert"]] += 1

                    if self.show:
                        self._draw(frame, result)
                        cv2.imshow(f"ATM Sentinel - {self.cam_id}", frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            self._stop_evt.set()
                            break

                except Exception as e:
                    print(f"[{self.cam_id}] Processing error: {e}")

            cap.release()
            if not self._stop_evt.is_set():
                time.sleep(2)   # brief pause before reconnect

        if self.show:
            cv2.destroyAllWindows()

    def _draw(self, frame: np.ndarray, result: dict):
        colour = {"HIGH": (0, 0, 255), "MEDIUM": (0, 140, 255),
                  "LOW": (255, 200, 0), "NONE": (0, 200, 0)}
        level  = result["alert"]
        c      = colour.get(level, (255, 255, 255))
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), c, -1)
        txt = (f"{self.cam_id}  ALERT={level}  "
               f"ae={result['ae_level']}  yolo={result['yolo_level']}  "
               f"beh={result['beh_level']}")
        if result.get("top_det"):
            txt += f"  [{result['top_det']['class_name']}]"
        cv2.putText(frame, txt, (8, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


# ── Core runner (no argparse — safe to call from backend) ─────────────────────

def run(cam_id: str | None = None, video: str | None = None, show: bool = False):
    print("=" * 60)
    print("ATM Sentinel — Inference Pipeline")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Alert log: {ALERT_LOG}")
    print()

    registry = ModelRegistry()
    logger   = AlertLogger()

    if video:
        sources = {"test": {"url": video, "fps": 5, "name": "Test Video"}}
    else:
        sources = CAMERAS
        if cam_id:
            if cam_id not in sources:
                print(f"ERROR: camera '{cam_id}' not in config. Choose: {list(sources)}")
                return
            sources = {cam_id: sources[cam_id]}

    threads: list[CameraThread] = []
    for cid, cfg in sources.items():
        proc   = FrameProcessor(cid, registry, logger)
        thread = CameraThread(
            cam_id    = cid,
            source    = cfg["url"],
            target_fps= cfg["fps"],
            processor = proc,
            show      = show,
        )
        threads.append(thread)
        thread.start()
        print(f"Started thread for {cid}: {cfg['name']}")

    print()
    print("Press Ctrl+C to stop.\n")

    def _shutdown(_sig, _frame):
        print("\nShutting down...")
        for t in threads:
            t.stop()

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        for t in threads:
            t.stop()

    print("\n" + "=" * 60)
    print("Session summary:")
    for t in threads:
        print(f"  [{t.cam_id}] frames={t.frame_count}  alerts={t.alert_counts}")
    print("=" * 60)


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ATM Sentinel inference")
    parser.add_argument("--cam",   default=None)
    parser.add_argument("--video", default=None)
    parser.add_argument("--show",  action="store_true")
    args = parser.parse_args()
    run(cam_id=args.cam, video=args.video, show=args.show)


if __name__ == "__main__":
    main()
