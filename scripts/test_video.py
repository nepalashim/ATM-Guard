#!/usr/bin/env python3
"""
Video Test Script - ResNet50 Tool Classifier
=============================================

Tests trained ResNet50 classifier on your ATM video file.
Detects HIGH threat tools and logs results.

Usage:
  python test_video.py "path/to/video.mp4"
  python test_video.py "path/to/video.mp4" --show          # Display window
  python test_video.py "path/to/video.mp4" --save-clips    # Save snapshots
"""

import argparse
import sys
import json
from pathlib import Path
from collections import defaultdict

import cv2
import torch
import numpy as np
from tqdm import tqdm
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from inference.classifier import ToolClassifierInference

# ──────────────────────────────────────────────────────────────────────────────

MODEL_PATH = Path(__file__).parent / "training" / "weights" / "tool_classifier" / "tool_classifier_final.pth"
LOGS_DIR = Path(__file__).parent / "logs"
STORAGE_DIR = Path(__file__).parent / "storage"

# ──────────────────────────────────────────────────────────────────────────────

def test_video(video_path: str, show: bool = False, save_clips: bool = False):
    """
    Process video file with trained classifier.
    
    Args:
        video_path: Path to video file
        show: Display frames with detections
        save_clips: Save snapshots to storage/
    """
    video_path = Path(video_path)
    if not video_path.exists():
        print(f"❌ Video not found: {video_path}")
        return
    
    LOGS_DIR.mkdir(exist_ok=True)
    STORAGE_DIR.mkdir(exist_ok=True)
    
    # Initialize classifier
    print(f"\n📦 Loading model from: {MODEL_PATH}")
    if not MODEL_PATH.exists():
        print(f"❌ Model file not found: {MODEL_PATH}")
        print(f"   Run training first: python training/11_classify_train.py")
        return
    
    try:
        classifier = ToolClassifierInference(
            str(MODEL_PATH),
            device='cuda' if torch.cuda.is_available() else 'cpu',
            confidence_threshold=0.5
        )
        device = "GPU 🚀" if torch.cuda.is_available() else "CPU 🐌"
        print(f"✅ Model loaded on {device}")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return
    
    # Open video
    print(f"\n🎬 Opening video: {video_path.name}")
    cap = cv2.VideoCapture(str(video_path))
    
    if not cap.isOpened():
        print(f"❌ Failed to open video")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = frame_count / fps if fps > 0 else 0
    
    print(f"  FPS: {fps:.1f}")
    print(f"  Frames: {frame_count}")
    print(f"  Duration: {duration_sec:.1f}s")
    
    # Results tracking
    detections = defaultdict(lambda: {"count": 0, "max_conf": 0.0, "frames": []})
    frame_num = 0
    start_time = datetime.now()
    
    # Process frames
    print(f"\n🔍 Processing frames...")
    pbar = tqdm(total=frame_count, desc="Progress")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_num += 1
        pbar.update(1)
        
        # Skip frames (e.g., process every 5th frame for speed)
        # Comment out to process all frames
        # if frame_num % 5 != 0:
        #     continue
        
        # Classify frame
        try:
            result = classifier.predict(frame)
            
            if result and result['primary'] is not None:
                primary = result['primary']
                class_name = primary['class_name']
                confidence = primary['confidence']
                threat_level = primary['threat_level']
                
                # Only track high confidence detections (>= 85%)
                if confidence >= 0.85:
                    # Track detection
                    detections[class_name]["count"] += 1
                    detections[class_name]["max_conf"] = max(
                        detections[class_name]["max_conf"], 
                        confidence
                    )
                    detections[class_name]["frames"].append({
                        "frame": frame_num,
                        "confidence": confidence,
                        "time": frame_num / fps if fps > 0 else 0
                    })
                    
                    # Log high confidence detections (>= 85%)
                    print(f"\n  [Frame {frame_num}] {class_name}: {confidence:.2%} ({threat_level})")
                
                # Display if requested
                if show:
                    h, w = frame.shape[:2]
                    label = f"{class_name} {confidence:.1%}"
                    color = (0, 0, 255) if threat_level == "HIGH" else (0, 255, 255)
                    cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                    cv2.imshow("Detection", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                # Save snapshot if requested
                if save_clips and confidence > 0.7:
                    snapshot_path = STORAGE_DIR / f"snapshot_{frame_num:06d}.jpg"
                    cv2.imwrite(str(snapshot_path), frame)
        
        except Exception as e:
            print(f"Error processing frame {frame_num}: {e}")
            continue
    
    pbar.close()
    cap.release()
    if show:
        cv2.destroyAllWindows()
    
    # Print summary
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f"\n" + "="*80)
    print(f"✅ PROCESSING COMPLETE")
    print(f"="*80)
    print(f"  Frames processed: {frame_num}")
    print(f"  Time elapsed: {elapsed:.1f}s")
    print(f"  Avg FPS: {frame_num/elapsed:.1f}")
    print(f"  Detections found: {sum(d['count'] for d in detections.values())}")
    
    if detections:
        print(f"\n📊 DETECTION SUMMARY")
        print(f"-"*80)
        for class_name in sorted(detections.keys()):
            d = detections[class_name]
            print(f"  {class_name:20s}: {d['count']:3d} times | Max conf: {d['max_conf']:.2%}")
        
        # Save detailed results
        results_file = LOGS_DIR / "test_results.json"
        results = {
            "video_file": str(video_path),
            "timestamp": datetime.now().isoformat(),
            "total_frames": frame_num,
            "duration_sec": duration_sec,
            "processing_time_sec": elapsed,
            "detections_by_class": {
                k: {
                    "count": v["count"],
                    "max_confidence": v["max_conf"],
                    "frame_list": v["frames"][:10]  # First 10 detections
                }
                for k, v in detections.items()
            }
        }
        
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📁 Results saved to: {results_file}")
    else:
        print(f"\n⚠️  No HIGH threat tools detected in video")
    
    print()


# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test ResNet50 tool classifier on video file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_video.py "path/to/video.mp4"
  python test_video.py "NIC/NIC videos/vlc-record-2024-05-15-16h12m19s...mp4" --show
  python test_video.py "video.mp4" --save-clips
        """
    )
    
    parser.add_argument(
        "video",
        help="Path to video file (MP4, MOV, AVI, etc.)"
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display frames with detections (slower)"
    )
    parser.add_argument(
        "--save-clips",
        action="store_true",
        help="Save snapshots to storage/"
    )
    
    args = parser.parse_args()
    
    test_video(
        args.video,
        show=args.show,
        save_clips=args.save_clips
    )
