# ATM Sentinel — System Documentation

**Seethos.ai | Computer Vision | ATM Monitoring**
Real-time ATM threat detection using finetuned YOLOv11n tool detection and loitering tracking.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [File Structure](#3-file-structure)
4. [AI Pipeline](#4-ai-pipeline)
5. [Alert System](#5-alert-system)
6. [Database Schema](#6-database-schema)
7. [API Reference](#7-api-reference)
8. [User Roles & Auth](#8-user-roles--auth)
9. [Running the System](#9-running-the-system)
10. [Configuration Reference](#10-configuration-reference)
11. [Retraining the Model](#11-retraining-the-model)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. System Overview

ATM Sentinel monitors ATM cameras in real time and fires alerts when:

| Alert Level | Trigger | Detection Method |
|-------------|---------|-----------------|
| **HIGH** | One of 5 threat tools detected at ≥ 75% confidence | Finetuned YOLOv11n on YOLO person-crop |
| **LOW** | A person remains in frame for > 60 seconds | Frame-level loitering timer |

**Technology stack:**

| Layer | Technology |
|-------|-----------|
| Inference | PyTorch 2.6, YOLOv11n (base + finetuned), OpenCV |
| Backend | FastAPI, PostgreSQL, SQLAlchemy, JWT |
| Frontend | React 18, TypeScript, Vite |
| GPU | NVIDIA CUDA 12.4 (RTX 4070 tested) |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     RTSP Camera (camA)                      │
│           rtsp://admin:123456@192.168.1.149:554/stream1     │
└───────────────────────┬─────────────────────────────────────┘
                        │ frames @ 5 FPS
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Inference Engine  (daemon thread)              │
│                                                             │
│  Frame pre-resize → 1280×720                                │
│       │                                                     │
│       ├── YOLOv11n (person detection, conf ≥ 0.85)         │
│       │      └── crop each person bbox + 20% padding        │
│       │             └── Finetuned YOLOv11n (5 tools)        │
│       │                    └── conf ≥ 75% → HIGH alert      │
│       │                                                     │
│       └── Loitering tracker (frame-level timer)            │
│              └── loiter timer increments per frame         │
│                     └── loiter ≥ 60s → LOW alert           │
│                                                             │
│  On alert:  save JPEG snapshot → storage/snapshots/         │
│             record 5s MP4 clip → storage/clips/  (thread)   │
│             POST /api/alerts   → backend                    │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP POST
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (:8000)                   │
│                                                             │
│  POST /api/alerts  → store in PostgreSQL                    │
│  WebSocket /ws     → broadcast to connected frontends       │
│  PATCH /api/alerts/{id} → update video_path after clip done │
│  GET  /api/alerts  → serve alert history with filters       │
│  /storage/*        → serve static snapshots & clips         │
└───────────────────────┬─────────────────────────────────────┘
                        │ REST + WebSocket
                        ▼
┌─────────────────────────────────────────────────────────────┐
│               React Frontend (:5173)                        │
│                                                             │
│  Dashboard      → live camera feed + real-time alerts       │
│  Alert History  → table with snapshot/video modal           │
│  Cameras        → RTSP camera management (manager only)     │
│  Reports        → statistics dashboard (manager only)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. File Structure

```
Atm-monitoring/
│
├── backend/                        # FastAPI REST API + WebSocket
│   ├── main.py                     # App entry: CORS, routers, inference thread, DB migration
│   ├── database.py                 # SQLAlchemy engine, SessionLocal, Base
│   ├── .env                        # DB credentials (not committed)
│   ├── .env.example                # Template for .env
│   ├── models/
│   │   └── db.py                   # ORM: Alert, Camera, User tables
│   ├── routers/
│   │   ├── alerts.py               # CRUD + acknowledge/escalate/sos/patch
│   │   ├── auth.py                 # Login, signup, JWT issue
│   │   ├── cameras.py              # Camera management + RTSP stream proxy
│   │   ├── users.py                # User CRUD (manager only)
│   │   ├── reports.py              # Stats + PDF report generation
│   │   └── ws.py                   # WebSocket manager (broadcast alerts)
│   ├── schemas/
│   │   ├── alerts.py               # AlertCreate, AlertOut, AlertStats
│   │   ├── cameras.py              # CameraCreate, CameraOut
│   │   └── users.py                # UserCreate, UserOut, Token
│   └── utils/
│       └── auth.py                 # JWT encode/decode, password hashing
│
├── inference/                      # Real-time detection pipeline
│   ├── main.py                     # Main loop: FrameProcessor, AlertLogger (ACTIVE)
│   ├── main_supervised.py          # Legacy supervised pipeline (deprecated)
│   ├── config.py                   # All runtime settings (single source of truth)
│   ├── models.py                   # Model loaders: YOLODetector, ToolDetector, AnomalyDetector, BehaviourClassifier
│   ├── classifier.py               # Legacy ResNet50 tool classifier (DEPRECATED)
│   ├── score_fusion.py             # Alert fusion: ae_error + tool_dets + behaviour → alert_level
│   └── __init__.py
│
├── frontend/                       # React + TypeScript dashboard
│   ├── package.json                # npm deps + scripts (dev, build, preview)
│   ├── vite.config.ts              # Vite: proxy /api → :8000, /storage → :8000
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx                # React 18 root render
│       ├── App.tsx                 # React Router: routes + auth guard
│       ├── api.ts                  # Axios client + TypeScript Alert/Camera/User interfaces
│       ├── App.css / index.css
│       ├── components/
│       │   └── Layout.tsx          # Sidebar nav + role-aware menu items
│       └── pages/
│           ├── Login.tsx           # JWT login form
│           ├── Signup.tsx          # Role selection + registration
│           ├── Dashboard.tsx       # Live feed + real-time alert banner (WebSocket)
│           ├── AlertHistory.tsx    # Alert table + snapshot/video modal
│           ├── CameraManager.tsx   # Add/edit/delete cameras (manager only)
│           └── ManagerDashboard.tsx # Stats charts + PDF export (manager only)
│
├── training/                       # Model training pipeline
│   ├── 11_classify_train.py        # ResNet50 training (DEPRECATED - not used)
│   ├── 11_classify_train_all_18_tools.py  # Full 18-class training (DEPRECATED)
│   ├── 12_classify_eval.py         # Evaluation (DEPRECATED)
│   ├── training_10_classify_dataset_loader.py  # Dataset loader (DEPRECATED)
│   ├── test_dataset_all_tools.py   # Dataset integrity check (DEPRECATED)
│   ├── train_supervised.bat        # Windows batch runner (DEPRECATED)
│   ├── weights/
│   │   └── tool_classifier/
│   │       ├── best_model.pth      # DEPRECATED: ResNet50, 18 classes (not used)
│   │       ├── tool_classifier_final.pth  # DEPRECATED: Backup checkpoint
│   │       └── metadata.json       # DEPRECATED: class_mapping
│   └── legacy/                     # Archived unsupervised pipeline scripts (01–09)
│
│   NOTE: Tool detection now uses finetuned YOLOv11n model (5 classes):
│   📍 C:\Seethos.ai\ComputerVision\ToolsFinetuning-Yolo\runs\yolov11n_tool_detection\weights\best.pt
│
├── storage/                        # Served as /storage/* by FastAPI
│   ├── snapshots/                  # Alert frame JPEGs → camA_{tool}_{timestamp}.jpg
│   └── clips/                      # 5-second MP4 clips → camA_{tool}_{timestamp}.mp4
│
├── data/                           # Dataset configs and ROI masks
│   └── atm.yaml                    # 14-class YOLO dataset config (legacy)
│
├── logs/
│   └── alerts.jsonl                # Append-only JSONL alert log (all fired alerts)
│
├── scripts/
│   ├── seed_admin.py               # Create first admin/manager account
│   └── show_results.py             # Visualize training results
│
├── yolo11n.pt                      # YOLOv11 nano — person detection (COCO, class 0)
├── yolo11s.pt                      # YOLOv11 small — alternative detector
├── requirements.txt                # Python dependencies
├── setup_postgres.bat              # Windows: create DB + user
├── setup_postgres.sh               # Linux/macOS: create DB + user
└── documentation.md                # This file
```

---

## 4. AI Pipeline

### 4.1 Tool Detection — HIGH Alert

**Flow per frame:**

```
1. Pre-resize frame to 1280×720 (handles 4K cameras)
2. Base YOLOv11n detects persons (conf ≥ 0.85)
   ├── For each person: crop bbox + 20% padding
   └── If no persons: skip tool detection
3. Finetuned YOLOv11n (5 tools) runs on each crop
   ├── Input: cropped person region
   ├── Output: confidence per class (5 tools: crowbar, hammer, screwdriver, drill, angle_grinder)
   └── Best confidence across all crops = candidate
4. If best_conf ≥ TOOL_YOLO_CONF (0.75):
   ├── Save JPEG snapshot → storage/snapshots/
   ├── POST HIGH alert to backend
   └── Start background thread → record 5s MP4 clip
```

**Why person-crop:** Camera is 4K wide-angle. Full-frame detection shrinks a held tool to ~12px. Cropping the person's body gives the tool 40–70% of the input.

**5 Finetuned Tool Classes (all HIGH threat):**

| Class | Tool | Model Path |
|-------|------|------------|
| 0 | crowbar | Finetuned YOLOv11n |
| 1 | hammer | (5 classes) |
| 2 | screwdriver | C:\Seethos.ai\ComputerVision\ToolsFinetuning-Yolo\runs\yolov11n_tool_detection\weights\best.pt |
| 3 | drill | |
| 4 | angle_grinder | |

**Model architecture:** YOLOv11n backbone with custom head for 5-class tool detection. Trained on tool-specific dataset with person context.

---

### 4.2 Loitering Detection — LOW Alert

**Flow per frame:**

```
1. Base YOLOv11n detects persons (conf ≥ 0.85) 
2. Track loitering time:
   ├── _first_seen timestamp: set on first person detection
   ├── loiter_sec = now - _first_seen
   └── If loiter_sec ≥ LOITER_SECONDS (60s):
       ├── Flag loiter_bump = True
       └── Score fusion marks as LOW alert
3. On alert:
   ├── Save JPEG snapshot
   ├── POST LOW alert with loiter_sec duration
   └── Start background thread → record 5s MP4 clip
4. Reset on frame clear:
   └── If no persons detected for > 3 frames:
       └── Reset _first_seen = None (loiter timer resets)
```

**Design:** Frame-level loitering timer (not per-person tracking). Simpler than ByteTrack—doesn't require tracking stability, just accumulates time while any person is in frame.

---

### 4.3 Snapshot & Video Clip

| | Snapshot | Video Clip |
|--|---------|-----------|
| Format | JPEG (quality 85) | MP4 (mp4v codec) |
| When | Immediately at alert | 5 seconds recorded after alert |
| Path | `storage/snapshots/camA_{tool}_{ts}.jpg` | `storage/clips/camA_{tool}_{ts}.mp4` |
| Served | `GET /storage/snapshots/…` | `GET /storage/clips/…` |
| Thread | Inline (fast) | Background thread (non-blocking) |

Clip path is patched back via `PATCH /api/alerts/{id}` once recording completes.

---

## 5. Alert System

### Alert Types

| Field | TOOL_DETECTED | LOITERING |
|-------|--------------|-----------|
| `level` | HIGH | LOW |
| `alert_type` | TOOL_DETECTED | LOITERING |
| `object_detected` | tool class name | human |
| `track_id` | null | ByteTrack integer ID |
| `loiter_sec` | 0.0 | dwell duration |
| `confidence` | classifier confidence | YOLO person confidence |
| `detection_source` | ResNet50+YOLO_crop | ByteTrack+YOLO |
| `frame_path` | storage/snapshots/… | storage/snapshots/… |
| `video_path` | storage/clips/… (async) | null |

### Alert Lifecycle

```
Inference fires alert
    → POST /api/alerts (201 Created)
    → WebSocket broadcast to all connected frontends
    → Supervisor sees alert banner on Dashboard

Supervisor reviews alert
    → GET /api/alerts/{id}  (view snapshot + video)
    → POST /api/alerts/{id}/acknowledge
    → POST /api/alerts/{id}/comment  (investigation notes)
    → POST /api/alerts/{id}/mark-true | mark-false
    → POST /api/alerts/{id}/escalate  (email to manager)
    → POST /api/alerts/{id}/sos       (HIGH only — emergency email)
```

### Alert Cooldown

- Tool detection: 30s cooldown per camera (key: `camA_TOOL_DETECTED`)
- Loitering: one alert per track_id lifetime (key: `camA_LOITERING_{track_id}`)
- Snapshot only saved if not in cooldown window

---

## 6. Database Schema

**PostgreSQL** on `localhost:5432`, database: `atmdb`

Auto-migrated at startup via `Base.metadata.create_all()` + safe `ALTER TABLE ADD COLUMN IF NOT EXISTS` for new columns.

```sql
-- users
id, email, full_name, password_hash, role (supervisor|manager), is_active, created_at

-- cameras
id, cam_id, name, url, location, latitude, longitude, is_active, created_at

-- alerts
id, camera_id (FK), cam_id, level (HIGH|MEDIUM|LOW|NONE)
alert_type, object_detected, confidence, detection_source, track_id
ae_level, yolo_level, beh_level, ae_error,         ← legacy fields
top_detection, cluster_id, n_detections, loiter_sec
frame_path, video_path, thumbnail, timestamp
acknowledged, acknowledged_by_id (FK), acknowledged_at
comment, is_false_alert
escalated, escalated_at, escalated_by_id (FK)
```

---

## 7. API Reference

**Base URL:** `http://localhost:8000`  
**Auth:** Bearer JWT in `Authorization` header (all endpoints except POST /api/auth/login and POST /api/auth/register)

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account (email, password, role) |
| POST | `/api/auth/login` | Returns JWT token |
| GET | `/api/auth/me` | Current user profile |

### Alerts
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/alerts` | Create alert (inference pipeline only) |
| GET | `/api/alerts` | List alerts (filters: cam_id, level, from_date, to_date, limit) |
| GET | `/api/alerts/{id}` | Single alert detail |
| PATCH | `/api/alerts/{id}` | Update video_path after clip recorded |
| GET | `/api/alerts/stats` | Counts by level, camera, today |
| POST | `/api/alerts/{id}/acknowledge` | Mark reviewed |
| POST | `/api/alerts/{id}/comment` | Save investigation notes |
| POST | `/api/alerts/{id}/mark-true` | Mark as true threat |
| POST | `/api/alerts/{id}/mark-false` | Mark as false positive |
| POST | `/api/alerts/{id}/escalate` | Email manager |
| POST | `/api/alerts/{id}/sos` | Emergency broadcast (HIGH only) |

### Cameras
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cameras` | List cameras |
| POST | `/api/cameras` | Add camera (manager only) |
| PUT | `/api/cameras/{id}` | Update camera |
| DELETE | `/api/cameras/{id}` | Remove camera |
| GET | `/api/cameras/{cam_id}/stream` | MJPEG stream proxy |

### WebSocket
| Path | Description |
|------|-------------|
| `ws://localhost:8000/ws` | Real-time alert broadcast (JWT in query param) |

### Static Files
| Path | Description |
|------|-------------|
| `/storage/snapshots/{filename}` | Alert JPEG snapshots |
| `/storage/clips/{filename}` | Alert MP4 video clips |

---

## 8. User Roles & Auth

| Feature | Supervisor | Manager |
|---------|-----------|---------|
| View Dashboard | ✅ | ✅ |
| View Alert History | ✅ | ✅ |
| Acknowledge / Comment | ✅ | ✅ |
| Escalate alerts | ✅ | ✅ |
| SOS trigger | ✅ | ✅ |
| Manage Cameras | ❌ | ✅ |
| View Reports | ❌ | ✅ |
| Manage Users | ❌ | ✅ |

**Token storage:** JWT stored in `localStorage` as `token`. Role stored as `role`. Cleared on 401 response — redirects to `/login`.

**First user setup:**
```bash
cd c:\Seethos.ai\ComputerVision\Atm-monitoring
.venv\Scripts\python.exe scripts/seed_admin.py
```

---

## 9. Running the System

### Prerequisites

- Python 3.11+ with virtual environment at `.venv/`
- Node.js 18+
- PostgreSQL 14+ running on port 5432
- NVIDIA GPU with CUDA 12.4+ drivers (optional, falls back to CPU)

### Step 1 — Database Setup (first time only)

```bat
# Windows
setup_postgres.bat

# or manually in psql:
CREATE USER postgres WITH PASSWORD 'postgres';
CREATE DATABASE atmdb OWNER postgres;
```

Configure `backend/.env`:
```env
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=atmdb
```

### Step 2 — Backend (includes inference pipeline)

```bat
cd c:\Seethos.ai\ComputerVision\Atm-monitoring
.venv\Scripts\activate

# Development
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Production (no reload, multiple workers)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

On startup the backend automatically:
- Runs `CREATE TABLE IF NOT EXISTS` for all tables
- Runs `ALTER TABLE ADD COLUMN IF NOT EXISTS` for new columns
- Starts the inference daemon thread (connects to RTSP, loads models)

**Expected startup output:**
```
[inference] Pipeline started in background thread.
[camA] Starting inference...
✓ Loaded tool classifier: training/weights/tool_classifier/best_model.pth
  Device: cuda
  Classes: ['crowbar', 'hammer', ...]
  Confidence threshold: 0.75
  [+] Tool classifier loaded
  [+] YOLO human detector loaded (yolo11n.pt)
INFO: Uvicorn running on http://0.0.0.0:8000
```

### Step 3 — Frontend

```bat
cd c:\Seethos.ai\ComputerVision\Atm-monitoring\frontend
npm install       # first time only
npm run dev
```

Open **http://localhost:5173**

### Step 4 — Create First Account

Navigate to `http://localhost:5173/signup`, create a Manager account, then create Supervisor accounts as needed.

### Running Inference Standalone (offline video test)

```bat
cd c:\Seethos.ai\ComputerVision\Atm-monitoring
.venv\Scripts\activate
python inference/main_supervised.py --video path/to/video.mp4
python inference/main_supervised.py --video path/to/video.mp4 --show
python inference/main_supervised.py --cam camA   # live RTSP
```

---

## 10. Configuration Reference

**File:** `inference/config.py` — single source of truth for all runtime settings.

```python
# Camera
CAMERAS = {
    "camA": {
        "url": "rtsp://admin:123456@192.168.1.149:554/stream1",
        "fps": 5,
        "name": "ATM Front Camera",
    }
}

# Model paths
TOOL_CLASSIFIER_WEIGHTS = ROOT / "training/weights/tool_classifier/best_model.pth"
YOLO_HUMAN_DETECTOR_MODEL = ROOT / "yolo11n.pt"

# Detection thresholds
CLASSIFIER_CONF_THRESHOLD = 0.75   # Minimum confidence for HIGH tool alert
                                    # Note: 0.75 is interim — retrain on camera-specific
                                    # data for original 0.85 target
YOLO_CONF_THRESHOLD = 0.85         # YOLO person detection confidence
LOITERING_TIME_THRESHOLD = 100.0   # seconds before LOW loitering alert fires
LOITERING_GRACE_PERIOD = 10.0      # seconds before a lost track's timer clears
PERSON_PRESENCE_DETECTION = True   # enable/disable loitering detection

# Hardware
DEVICE = "cuda"                    # "cuda" or "cpu"

# Backend
API_ALERT_ENDPOINT = "http://127.0.0.1:8000/api/alerts"
API_ENABLED = True
API_TIMEOUT = 2.0                  # seconds
```

**Alert cooldown** (in `main_supervised.py` `AlertLogger`):
- Tool alerts: 30s cooldown per camera
- Loitering alerts: one alert per ByteTrack track_id (no repeat for same person)

---

## 11. Retraining the Model

The ResNet50 classifier was trained on isolated tool images. For higher accuracy on the production camera (wide-angle, person-held tools), retrain with camera-specific images.

### Collect Training Data

Stand in front of the ATM camera holding each tool in various positions. Save frames:

```python
# Quick data collection from RTSP
import cv2
cap = cv2.VideoCapture("rtsp://admin:123456@192.168.1.149:554/stream1")
# save every 10th frame with label
```

Aim for **100–200 images per tool** from the actual camera angle.

### Train

```bat
cd c:\Seethos.ai\ComputerVision\Atm-monitoring
.venv\Scripts\activate
python training/11_classify_train_all_18_tools.py
```

Training config is in `training_10_classify_dataset_loader.py`. The best checkpoint is automatically saved to `training/weights/tool_classifier/best_model.pth`.

After retraining, raise `CLASSIFIER_CONF_THRESHOLD` back toward `0.85` in `inference/config.py`.

### Evaluate

```bat
python training/12_classify_eval.py
```

---

## 12. Troubleshooting

### Backend won't start
- Check PostgreSQL is running: `pg_isready -U postgres`
- Check `backend/.env` credentials match the database
- Check port 8000 is free: `netstat -an | findstr 8000`

### Inference pipeline not firing alerts
- Check RTSP URL is reachable: `ffprobe rtsp://admin:123456@192.168.1.149:554/stream1`
- Check GPU is available: `.venv\Scripts\python -c "import torch; print(torch.cuda.is_available())"`
- Lower `CLASSIFIER_CONF_THRESHOLD` in `inference/config.py` temporarily for testing
- Check `logs/alerts.jsonl` — if empty, inference is not running; look for errors in the uvicorn console

### RTSP stream issues
- Camera must output **H.264** codec — OpenCV does not support H.265/HEVC
- Change codec in camera web UI: Video → Encoding → H.264
- Test stream: `ffplay rtsp://admin:123456@192.168.1.149:554/stream1`

### Low tool detection confidence
- Root cause: model trained on isolated tool images, not wide-angle camera scenes
- Interim fix: `CLASSIFIER_CONF_THRESHOLD = 0.75` (current setting)
- Long-term fix: retrain with ~100 images per tool from this camera (see §11)
- The person-crop strategy (crop YOLO person bbox before classifying) is already applied

### PyTorch CPU-only (no CUDA)
```bat
.venv\Scripts\pip install "torch==2.6.0+cu124" "torchvision==0.21.0+cu124" --index-url https://download.pytorch.org/whl/cu124
```

### Snapshot not appearing in alert modal
- Verify FastAPI static mount: `storage/` is served at `/storage`
- Check file was written: look in `storage/snapshots/`
- Frontend path: `src={`/${selected.frame_path}`}` — frame_path must start with `storage/`

### Too many snapshots being saved
- Snapshots are gated by the 30s alert cooldown — only one per cooldown window
- If accumulating rapidly, increase `CLASSIFIER_CONF_THRESHOLD`

---

*Seethos.ai — ATM Sentinel v2.0 | Supervised Pipeline*
