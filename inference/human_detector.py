"""
Human Detection Module for Loitering Detection
Uses YOLOv11 to detect humans (person class) in frames
"""

import numpy as np
import torch
import cv2
from pathlib import Path
from typing import Optional, List, Tuple

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


class HumanDetector:
    """Detects humans in frames using YOLOv11"""
    
    def __init__(
        self, 
        model_path: str = "yolo11n.pt",
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        conf_threshold: float = 0.5
    ):
        """
        Initialize human detector
        
        Args:
            model_path: Path to YOLO model file (yolo11n.pt, yolo11s.pt, etc.)
            device: Device to run on ('cuda' or 'cpu')
            conf_threshold: Confidence threshold for detections (0.0-1.0)
        """
        if YOLO is None:
            raise ImportError("ultralytics not installed. Install with: pip install ultralytics")
        
        model_file = Path(model_path)
        if not model_file.exists():
            # Try relative to project root
            model_file = Path(__file__).resolve().parent.parent / model_path
        
        if not model_file.exists():
            raise FileNotFoundError(f"YOLO model not found: {model_path}")
        
        self.model = YOLO(str(model_file))
        self.model.to(device)
        self.device = device
        self.conf_threshold = conf_threshold
        self.person_class_id = 0  # COCO dataset: class 0 = person
        
    def detect_humans(self, frame: np.ndarray) -> Tuple[bool, List[dict]]:
        """
        Detect humans in frame
        
        Args:
            frame: Input frame (BGR, numpy array)
            
        Returns:
            Tuple of:
              - has_humans: Boolean indicating if humans detected
              - detections: List of human detections with bounding boxes
        """
        try:
            # Run inference
            results = self.model(frame, conf=self.conf_threshold, verbose=False)
            
            detections = []
            has_humans = False
            
            # Extract person detections
            for result in results:
                for detection in result.boxes:
                    # Check if detection is person class (id=0 in COCO)
                    if int(detection.cls[0]) == self.person_class_id:
                        has_humans = True
                        
                        # Extract bounding box and confidence
                        x1, y1, x2, y2 = detection.xyxy[0].cpu().numpy()
                        conf = float(detection.conf[0].cpu().numpy())
                        
                        detections.append({
                            'bbox': (int(x1), int(y1), int(x2), int(y2)),
                            'confidence': conf,
                            'center': (int((x1 + x2) / 2), int((y1 + y2) / 2))
                        })
            
            return has_humans, detections
        
        except Exception as e:
            print(f"[ERROR] Human detection failed: {e}")
            return False, []
    
    def detect_and_track(self, frame: np.ndarray) -> List[dict]:
        """
        Run YOLO with ByteTrack to detect and assign persistent track IDs to each person.
        Uses persist=True so the Kalman filter state is maintained across consecutive calls.

        Returns a list of detections, each containing:
          track_id  — stable integer ID assigned by ByteTrack
          bbox      — (x1, y1, x2, y2) ints
          confidence— float 0-1
          center    — (cx, cy) ints
        Returns [] when no persons are detected or tracking IDs not yet assigned.
        """
        try:
            results = self.model.track(
                frame,
                conf=self.conf_threshold,
                persist=True,          # ByteTrack: keep Kalman state between frames
                classes=[self.person_class_id],
                verbose=False,
            )
            detections = []
            for result in results:
                if result.boxes.id is None:
                    continue
                for box, track_id, conf in zip(
                    result.boxes.xyxy,
                    result.boxes.id,
                    result.boxes.conf,
                ):
                    x1, y1, x2, y2 = box.cpu().numpy().astype(int)
                    detections.append({
                        'track_id':   int(track_id),
                        'bbox':       (x1, y1, x2, y2),
                        'confidence': float(conf),
                        'center':     ((x1 + x2) // 2, (y1 + y2) // 2),
                    })
            return detections
        except Exception as e:
            print(f"[ERROR] ByteTrack tracking failed: {e}")
            return []

    def detect_humans_with_fallback(
        self, 
        frame: np.ndarray,
        fallback_motion_threshold: float = 500.0
    ) -> Tuple[bool, str]:
        """
        Detect humans with fallback to motion detection if YOLO fails
        
        Args:
            frame: Input frame
            fallback_motion_threshold: Laplacian variance threshold for motion detection
            
        Returns:
            Tuple of (has_humans, detection_method)
        """
        # Try YOLO first
        has_humans, detections = self.detect_humans(frame)
        if has_humans:
            return True, "YOLO"
        
        # Fallback to motion detection if no humans detected
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            variance = laplacian.var()
            
            if variance > fallback_motion_threshold:
                return True, "Motion_Fallback"
        except Exception as e:
            print(f"[WARNING] Motion fallback failed: {e}")
        
        return False, "None"


def get_human_detector(
    model_path: str = "yolo11n.pt",
    device: Optional[str] = None
) -> Optional[HumanDetector]:
    """
    Factory function to safely create human detector
    
    Args:
        model_path: Path to YOLO model
        device: Device to use ('cuda' or 'cpu')
        
    Returns:
        HumanDetector instance or None if YOLO not available
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    try:
        return HumanDetector(model_path, device)
    except (ImportError, FileNotFoundError) as e:
        print(f"[WARNING] Could not initialize HumanDetector: {e}")
        print("[WARNING] Loitering detection will use motion-based fallback")
        return None


# Test the human detector
if __name__ == "__main__":
    import cv2
    
    print("[+] Testing HumanDetector...")
    
    # Try to create detector
    detector = get_human_detector()
    if detector is None:
        print("[-] HumanDetector not available, exiting test")
        exit(1)
    
    print(f"[+] HumanDetector loaded on device: {detector.device}")
    print(f"[+] Person class ID: {detector.person_class_id}")
    print(f"[+] Confidence threshold: {detector.conf_threshold}")
    
    # Test on a sample frame if available
    test_image_path = Path(__file__).parent.parent / "data" / "images" / "camA"
    if test_image_path.exists():
        test_images = list(test_image_path.glob("*.jpg"))[:1]
        
        if test_images:
            frame = cv2.imread(str(test_images[0]))
            if frame is not None:
                print(f"[+] Testing on: {test_images[0].name}")
                
                has_humans, detections = detector.detect_humans(frame)
                print(f"[+] Humans detected: {has_humans}")
                print(f"[+] Number of detections: {len(detections)}")
                
                for i, det in enumerate(detections):
                    print(f"    [{i}] Confidence: {det['confidence']:.2%}, BBox: {det['bbox']}")
