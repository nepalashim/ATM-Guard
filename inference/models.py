"""
ATM Sentinel — Model Loading & Inference Wrappers
Loads all four trained models once at startup and exposes simple run() methods.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from inference.config import (
    YOLO_HUMAN_DETECTOR_MODEL, AUTOENCODER_WEIGHTS, POSE_ENCODER_WEIGHTS,
    KMEANS_CENTERS, IMGSZ, AE_IMGSZ, POSE_DIM, BOTTLENECK,
    POSE_WINDOW, YOLO_CONF, DEVICE, YOLO_CONF_THRESHOLD,
)


# ── Device ────────────────────────────────────────────────────────────────────

def get_device() -> torch.device:
    if DEVICE == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


# ── 1. YOLO Human Detector ───────────────────────────────────────────────────

class YOLODetector:
    """Base YOLO model for human/person detection (handles loitering tracking)."""
    def __init__(self, device: torch.device):
        from ultralytics import YOLO
        print(f"  Loading human detector: {YOLO_HUMAN_DETECTOR_MODEL.name}")
        self.model  = YOLO(str(YOLO_HUMAN_DETECTOR_MODEL))
        self.device = device
        self.conf_threshold = YOLO_CONF_THRESHOLD

    def run(self, frame_bgr: np.ndarray) -> list[dict]:
        """
        Detect persons in frame.
        Returns list of {class_idx, conf, box:[x1,y1,x2,y2]} for person detections (class_idx=0).
        """
        results = self.model(
            frame_bgr,
            imgsz=IMGSZ,
            conf=self.conf_threshold,
            device=self.device,
            verbose=False,
            classes=[0],  # person class only
        )[0]

        dets = []
        if results.boxes is not None:
            for box in results.boxes:
                dets.append({
                    "class_idx": int(box.cls.item()),
                    "conf":      round(float(box.conf.item()), 3),
                    "box":       [round(float(v), 1) for v in box.xyxy[0].tolist()],
                })
        return dets


# ── 2. ConvAutoencoder ────────────────────────────────────────────────────────

def _conv_block(in_ch, out_ch):
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, 4, stride=2, padding=1, bias=False),
        nn.BatchNorm2d(out_ch),
        nn.LeakyReLU(0.2, inplace=True),
    )

def _deconv_block(in_ch, out_ch, activation="relu"):
    layers = [
        nn.ConvTranspose2d(in_ch, out_ch, 4, stride=2, padding=1, bias=False),
        nn.BatchNorm2d(out_ch),
    ]
    layers.append(nn.ReLU(inplace=True) if activation == "relu" else nn.Tanh())
    return nn.Sequential(*layers)

class _ConvAE(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(
            _conv_block(3, 32), _conv_block(32, 64),
            _conv_block(64, 128), _conv_block(128, 256),
        )
        self.decoder = nn.Sequential(
            _deconv_block(256, 128), _deconv_block(128, 64),
            _deconv_block(64, 32),  _deconv_block(32, 3, "tanh"),
        )
    def forward(self, x):
        return self.decoder(self.encoder(x))


class AnomalyDetector:
    def __init__(self, device: torch.device):
        print(f"  Loading autoencoder: {AUTOENCODER_WEIGHTS.name}")
        self.device = device
        self.model  = _ConvAE().to(device)
        self.model.load_state_dict(
            torch.load(str(AUTOENCODER_WEIGHTS), map_location=device)
        )
        self.model.eval()

    @torch.no_grad()
    def run(self, frame_bgr: np.ndarray) -> float:
        """Return MSE reconstruction error (anomaly score)."""
        img = cv2.resize(frame_bgr, (AE_IMGSZ, AE_IMGSZ))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        t   = torch.from_numpy(img).permute(2, 0, 1).float() / 127.5 - 1.0
        t   = t.unsqueeze(0).to(self.device)
        recon = self.model(t)
        return float(F.mse_loss(recon, t).item())


# ── 3. Pose Encoder + K-Means Behaviour Classifier ───────────────────────────

class _PoseEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(POSE_DIM, 128, 2, batch_first=True, dropout=0.2)
        self.fc   = nn.Linear(128, BOTTLENECK)
    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.fc(h[-1])


class BehaviourClassifier:
    def __init__(self, device: torch.device):
        print(f"  Loading pose encoder: {POSE_ENCODER_WEIGHTS.name}")
        self.device  = device
        self.encoder = _PoseEncoder().to(device)
        self.encoder.load_state_dict(
            torch.load(str(POSE_ENCODER_WEIGHTS), map_location=device)
        )
        self.encoder.eval()

        print(f"  Loading k-means centers: {KMEANS_CENTERS.name}")
        self.centers = np.load(str(KMEANS_CENTERS))   # (6, BOTTLENECK)

        # Sliding window buffer for pose sequence
        self._buffer: deque[np.ndarray] = deque(maxlen=POSE_WINDOW)

        # Load YOLO pose model for keypoint extraction
        from ultralytics import YOLO
        self._pose_model = YOLO("yolo11n-pose.pt")

    def _extract_keypoints(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Run YOLO pose on frame, return 34-dim normalised keypoint vector."""
        results = self._pose_model(frame_bgr, verbose=False)
        kpts    = results[0].keypoints
        if kpts is not None and len(kpts) > 0 and kpts.xy is not None:
            xy  = kpts.xy[0].cpu().numpy()
            h, w = results[0].orig_shape
            xy[:, 0] /= max(w, 1)
            xy[:, 1] /= max(h, 1)
            return xy.flatten().astype(np.float32)
        return np.zeros(POSE_DIM, dtype=np.float32)

    @torch.no_grad()
    def run(self, frame_bgr: np.ndarray) -> int:
        """
        Add frame to pose buffer. Returns cluster_id (-1 if buffer not full yet).
        """
        kp = self._extract_keypoints(frame_bgr)
        self._buffer.append(kp)

        if len(self._buffer) < POSE_WINDOW:
            return -1   # not enough frames yet

        seq = np.stack(list(self._buffer), axis=0)              # (30, 34)
        t   = torch.from_numpy(seq).unsqueeze(0).to(self.device) # (1, 30, 34)
        emb = self.encoder(t).cpu().numpy()                      # (1, 32)

        # Nearest k-means centre
        dists = np.linalg.norm(self.centers - emb, axis=1)
        return int(np.argmin(dists))


# ── 4. Tool Detector (Finetuned YOLOv11n) ────────────────────────────────────

class ToolDetector:
    """
    Finetuned YOLOv11n for tool detection in cropped person regions.
    Detects: crowbar, hammer, screwdriver, drill, angle_grinder
    """
    def __init__(self, device: torch.device):
        from ultralytics import YOLO
        from inference.config import TOOL_YOLO_WEIGHTS, TOOL_YOLO_CONF
        
        print(f"  Loading tool detector: {TOOL_YOLO_WEIGHTS.name}")
        self.model  = YOLO(str(TOOL_YOLO_WEIGHTS))
        self.device = device
        self.conf_threshold = TOOL_YOLO_CONF
        
        # Tool class mapping from finetuned model
        self.class_names = {
            0: "crowbar",
            1: "hammer", 
            2: "screwdriver",
            3: "drill",
            4: "angle_grinder"
        }

    def run(self, crop_bgr: np.ndarray) -> list[dict]:
        """
        Run tool detector on a cropped person region.
        
        Returns list of {class_idx, class_name, conf, box:[x1,y1,x2,y2]} 
        for all detections above confidence threshold.
        """
        results = self.model(
            crop_bgr,
            conf=self.conf_threshold,
            device=self.device,
            verbose=False,
        )[0]

        dets = []
        if results.boxes is not None:
            for box in results.boxes:
                class_idx = int(box.cls.item())
                dets.append({
                    "class_idx": class_idx,
                    "class_name": self.class_names.get(class_idx, f"class_{class_idx}"),
                    "conf":      round(float(box.conf.item()), 3),
                    "box":       [round(float(v), 1) for v in box.xyxy[0].tolist()],
                })
        return dets


# ── Model registry ────────────────────────────────────────────────────────────

class ModelRegistry:
    """Load all models once. Pass this object around instead of reloading."""

    def __init__(self):
        device = get_device()
        print(f"Loading models on {device}...")
        self.device    = device
        self.yolo      = YOLODetector(device)
        self.anomaly   = AnomalyDetector(device)
        self.behaviour = BehaviourClassifier(device)
        self.tool_detector = ToolDetector(device)
        print("All models loaded.\n")
