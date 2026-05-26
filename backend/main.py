from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import threading
import sys

from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.database import engine, Base
from backend.routers import auth, alerts, cameras, users, reports, ws
from backend.models.db import Camera

# Create all tables
Base.metadata.create_all(bind=engine)

# Add new columns if they don't exist (safe PostgreSQL migration)
_NEW_COLS = {
    "video_path": "VARCHAR(512)",
    "comment": "TEXT",
    "is_false_alert": "BOOLEAN DEFAULT FALSE",
    "escalated": "BOOLEAN DEFAULT FALSE",
    "escalated_at": "TIMESTAMP",
    "escalated_by_id": "INTEGER",
    "alert_type": "VARCHAR(50)",
    "object_detected": "VARCHAR(80)",
    "confidence": "REAL",
    "detection_source": "VARCHAR(50)",
    "track_id": "INTEGER",
    "manager_comment": "TEXT",
}
with engine.begin() as _conn:
    for _col, _dtype in _NEW_COLS.items():
        try:
            _conn.execute(text(f"ALTER TABLE alerts ADD COLUMN IF NOT EXISTS {_col} {_dtype}"))
        except Exception:
            pass


def _sync_configured_cameras():
    """Ensure cameras from inference/config.py exist in the dashboard database."""
    try:
        from inference.config import CAMERAS
    except Exception as e:
        print(f"[cameras] Could not load configured cameras: {e}")
        return

    with Session(engine) as db:
        changed = False
        for cam_id, cfg in CAMERAS.items():
            cam = db.query(Camera).filter(Camera.cam_id == cam_id).one_or_none()
            if cam is None:
                db.add(Camera(
                    cam_id=cam_id,
                    name=cfg.get("name") or cam_id,
                    url=cfg.get("url") or "",
                    location=cfg.get("location", ""),
                    is_active=True,
                ))
                changed = True
                continue

            if not cam.url and cfg.get("url"):
                cam.url = cfg["url"]
                changed = True
            if (not cam.name or cam.name == cam.cam_id) and cfg.get("name"):
                cam.name = cfg["name"]
                changed = True

        if changed:
            db.commit()


_sync_configured_cameras()

# ── Inference thread ──────────────────────────────────────────────────────────
_inference_threads: list = []

def _start_inference():
    """Start inference thread with auto-restart on crash."""
    import time
    retry_count = 0
    max_retries = 10
    
    while retry_count < max_retries:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            sys.argv = [sys.argv[0]]  # strip uvicorn args so inference argparse doesn't choke
            from inference.main_supervised import run
            run()
        except KeyboardInterrupt:
            print("[inference] Interrupted")
            break
        except Exception as e:
            retry_count += 1
            print(f"[inference] Crashed (attempt {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                wait_time = min(2 ** retry_count, 60)  # exponential backoff, max 60s
                print(f"[inference] Restarting in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"[inference] Max retries exceeded. Giving up.")
                break
    
    print("[inference] Thread exited.")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    t = threading.Thread(target=_start_inference, name="inference", daemon=True)
    t.start()
    _inference_threads.append(t)
    print("[inference] Pipeline started in background thread.")
    yield
    print("[inference] Shutting down...")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ATM Sentinel API",
    version="1.0.0",
    description="Real-time ATM threat detection backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static alert frames if storage dir exists
storage = Path(__file__).parent.parent / "storage"
storage.mkdir(exist_ok=True)
app.mount("/storage", StaticFiles(directory=str(storage)), name="storage")

# Routers
app.include_router(auth.router)
app.include_router(alerts.router)
app.include_router(cameras.router)
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(ws.router)


@app.get("/")
def root():
    return {"service": "ATM Sentinel API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
