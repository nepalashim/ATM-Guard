"""
ATM Sentinel — Inference Configuration
All runtime settings in one place. Edit this file to change camera URLs,
model paths, alert thresholds, or API endpoints.
"""

from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent

# ── Camera RTSP streams ───────────────────────────────────────────────────────
CAMERAS = {
    "camA": {
        "url":  "rtsp://admin:123456@192.168.1.149:554/stream2",
        "fps":  5,
        "name": "ATM Front Camera",
    },
}

# ── Model weights ─────────────────────────────────────────────────────────────
WEIGHTS_DIR        = ROOT / "training" / "weights"

# Finetuned YOLO11n for Tool Detection (5 tools: crowbar, hammer, screwdriver, drill, angle_grinder)
TOOL_YOLO_WEIGHTS  = ROOT / "best-tools.pt"

# NEW: YOLO Human Detector for Loitering (yolo11n recommended for speed)
# Options: yolo11n.pt (nano, 2.6M params), yolo11s.pt (small, 9.6M params)
# Located in project root: {ROOT}/yolo11n.pt or {ROOT}/yolo11s.pt
YOLO_HUMAN_DETECTOR_MODEL = ROOT / "yolo11n.pt"
YOLO_CONF_THRESHOLD = 0.85  # Confidence threshold for YOLO person detections

# Legacy/Optional (kept for reference)
YOLO_WEIGHTS       = WEIGHTS_DIR / "yolo_atm_yolo11s_atm.pt"
AUTOENCODER_WEIGHTS= WEIGHTS_DIR / "conv_autoencoder.pth"
POSE_ENCODER_WEIGHTS= WEIGHTS_DIR / "pose_encoder.pth"

# ── Data files ────────────────────────────────────────────────────────────────
THRESHOLDS_PATH    = ROOT / "data" / "thresholds.json"
KMEANS_CENTERS     = ROOT / "data" / "behaviour" / "kmeans_centers.npy"

# ── Inference settings ────────────────────────────────────────────────────────
IMGSZ              = 640    # YOLO inference image size
AE_IMGSZ           = 128    # autoencoder image size (legacy)
POSE_WINDOW        = 30     # LSTM sequence length (legacy)
POSE_DIM           = 34     # 17 keypoints × 2 (legacy)
BOTTLENECK         = 32     # LSTM encoder output dim (legacy)
YOLO_CONF          = 0.70  # minimum YOLO confidence (legacy)

# NEW: Finetuned Tool YOLO Settings
TOOL_YOLO_CONF     = 0.75   # minimum confidence for tool detections
TOOL_YOLO_BBOX_PADDING = 0.20  # 20% padding around person bbox when cropping for tool detection
DEVICE             = "cuda" # "cuda" or "cpu"

# NEW: Loitering Detection Settings
LOITERING_TIME_THRESHOLD = 100.0  # seconds - person must be present for >100s to trigger LOW threat alert
LOITERING_GRACE_PERIOD   = 10.0   # seconds - grace window before a vanished track's timer is cleared (handles brief occlusions)
PERSON_PRESENCE_DETECTION = True  # Enable/disable loitering detection

# ── Alert settings ────────────────────────────────────────────────────────────
LOITER_SECONDS     = 60     # seconds before loitering LOW alert
ALERT_COOLDOWN     = 10     # seconds between repeated same-level alerts per camera
MIN_ALERT_LEVEL    = "LOW"  # suppress NONE alerts from being logged

# ── Output ────────────────────────────────────────────────────────────────────
LOG_DIR            = ROOT / "logs"
ALERT_LOG          = LOG_DIR / "alerts.jsonl"   # one JSON per line

# ── FastAPI backend ───────────────────────────────────────────────────────────
API_BASE_URL       = "http://127.0.0.1:8000"
API_ALERT_ENDPOINT = f"{API_BASE_URL}/api/alerts"
API_ENABLED        = True    # set True when backend is running
API_TIMEOUT        = 2.0     # seconds
