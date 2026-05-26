"""
Tool Classifier Inference Engine.

Loads trained ResNet50 classifier and provides inference interface.
Used for detecting HIGH threat tools in video frames and cropped regions.

Integration with existing inference pipeline:
  1. Detector finds potential threat regions (YOLO person detection + bounding box around)
  2. Classifier identifies specific tool in that region
  3. Returns: (tool_name, confidence, threat_level)
"""

import torch
import torch.nn as nn
import cv2
import numpy as np
from pathlib import Path
import json
from typing import Tuple, Dict, Optional


class ToolClassifierInference:
    """Tool classifier for real-time inference."""
    
    def __init__(self, model_path: str, device: str = 'cuda', confidence_threshold: float = 0.5):
        """
        Load trained classifier model.
        
        Args:
            model_path: Path to model weights (.pth file)
            device: 'cuda' or 'cpu'
            confidence_threshold: Minimum confidence to return a prediction
        """
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        self.confidence_threshold = confidence_threshold
        self.img_size = 224
        
        # Load checkpoint — supports both raw state_dict and full checkpoint formats
        checkpoint = torch.load(model_path, map_location=self.device)
        if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
            state_dict = checkpoint['model_state_dict']
            # class_mapping embedded in checkpoint takes priority
            if 'class_mapping' in checkpoint:
                self.class_mapping = {int(k): v for k, v in checkpoint['class_mapping'].items()}
        else:
            state_dict = checkpoint
            self.class_mapping = None  # resolved below

        # If class_mapping not in checkpoint, try metadata.json, then fall back to default
        if self.class_mapping is None:
            metadata_path = Path(model_path).parent / 'metadata.json'
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
                self.class_mapping = {int(k): v for k, v in self.metadata['class_mapping'].items()}
            else:
                self.class_mapping = {
                    0: 'crowbar',     1: 'hammer',       2: 'screwdriver',  3: 'drill',
                    4: 'drill_bit',   5: 'angle_grinder', 6: 'utility_knife', 7: 'hacksaw',
                    8: 'axe',         9: 'jack_hammer',  10: 'socket_wrench', 11: 'wrench',
                    12: 'pliers',    13: 'chisel',       14: 'file_tool',   15: 'caulking_gun',
                    16: 'torque_wrench', 17: 'hoe_tool',
                }

        self.num_classes = len(self.class_mapping)

        # Build model and load weights
        self.model = self._build_model()
        self.model.load_state_dict(state_dict)
        self.model = self.model.to(self.device)
        self.model.eval()
        
        print(f"✓ Loaded tool classifier: {model_path}")
        print(f"  Device: {self.device}")
        print(f"  Classes: {list(self.class_mapping.values())}")
        print(f"  Confidence threshold: {self.confidence_threshold}")
    
    def _build_model(self) -> nn.Module:
        """Build ResNet50 model architecture (matches training architecture)."""
        import torchvision.models as models
        
        class ToolClassifierModel(nn.Module):
            """Wrapper to match training model structure."""
            def __init__(self, num_classes):
                super().__init__()
                self.backbone = models.resnet50(pretrained=False)
                in_features = self.backbone.fc.in_features
                
                self.backbone.fc = nn.Sequential(
                    nn.Dropout(p=0.3),
                    nn.Linear(in_features, 512),
                    nn.BatchNorm1d(512),
                    nn.ReLU(inplace=True),
                    nn.Dropout(p=0.3),
                    nn.Linear(512, 256),
                    nn.BatchNorm1d(256),
                    nn.ReLU(inplace=True),
                    nn.Linear(256, num_classes)
                )
            
            def forward(self, x):
                return self.backbone(x)
        
        return ToolClassifierModel(self.num_classes)
    
    def preprocess(self, image: np.ndarray) -> torch.Tensor:
        """
        Preprocess image for model input.
        
        Args:
            image: BGR image from OpenCV (H, W, 3)
        
        Returns:
            Preprocessed tensor (1, 3, 224, 224) as float32
        """
        # Convert BGR to RGB
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Resize
        image = cv2.resize(image, (self.img_size, self.img_size), interpolation=cv2.INTER_LINEAR)
        
        # Normalize to [0, 1]
        image = image.astype(np.float32) / 255.0
        
        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        image = (image - mean) / std
        
        # Convert to tensor (ensure float32)
        image = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float()
        
        return image.to(self.device)
    
    def predict(self, image: np.ndarray, return_top_k: int = 1) -> Dict:
        """
        Predict tool class for image.
        
        Args:
            image: BGR image (H, W, 3) or (H, W, 4) with alpha
            return_top_k: Number of top predictions to return
        
        Returns:
            {
                'primary': {
                    'class_name': str,
                    'confidence': float,
                    'class_idx': int,
                    'threat_level': str
                },
                'top_k': [
                    {'class_name': str, 'confidence': float, 'class_idx': int},
                    ...
                ],
                'all_scores': [confidences for all classes]
            }
        """
        
        # Handle RGBA images
        if image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        
        # Preprocess
        tensor = self.preprocess(image)
        
        # Predict
        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1)
            conf, pred_idx = torch.max(probs, dim=1)
        
        conf = conf.item()
        pred_idx = pred_idx.item()
        
        # Get all probabilities
        all_probs = probs[0].cpu().numpy()
        
        # Sort by confidence
        sorted_indices = np.argsort(-all_probs)
        
        # Threat level mapping (all 18 HIGH threat tools)
        threat_map = {
            'crowbar': 'HIGH',
            'hammer': 'HIGH',
            'screwdriver': 'HIGH',
            'drill': 'HIGH',
            'drill_bit': 'HIGH',
            'angle_grinder': 'HIGH',
            'utility_knife': 'HIGH',
            'hacksaw': 'HIGH',
            'axe': 'HIGH',
            'jack_hammer': 'HIGH',
            'socket_wrench': 'HIGH',
            'wrench': 'HIGH',
            'pliers': 'HIGH',
            'chisel': 'HIGH',
            'file_tool': 'HIGH',
            'caulking_gun': 'HIGH',
            'torque_wrench': 'HIGH',
            'hoe_tool': 'HIGH',
        }
        
        result = {
            'primary': None,
            'top_k': [],
            'all_scores': all_probs.tolist(),
            'passed_threshold': conf >= self.confidence_threshold
        }
        
        # Primary prediction
        if conf >= self.confidence_threshold:
            class_name = self.class_mapping[pred_idx]
            threat_level = threat_map.get(class_name, 'UNKNOWN')
            
            result['primary'] = {
                'class_name': class_name,
                'confidence': float(conf),
                'class_idx': int(pred_idx),
                'threat_level': threat_level
            }
        
        # Top-k predictions
        for i, idx in enumerate(sorted_indices[:return_top_k]):
            class_name = self.class_mapping[int(idx)]
            conf_val = float(all_probs[int(idx)])
            threat_level = threat_map.get(class_name, 'UNKNOWN')
            
            result['top_k'].append({
                'class_name': class_name,
                'confidence': conf_val,
                'class_idx': int(idx),
                'threat_level': threat_level,
                'rank': i + 1
            })
        
        return result
    
    def predict_batch(self, images: list) -> list:
        """
        Predict on batch of images.
        
        Args:
            images: List of BGR images
        
        Returns:
            List of prediction results
        """
        results = []
        for image in images:
            result = self.predict(image)
            results.append(result)
        return results
    
    def predict_on_region(self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> Dict:
        """
        Predict tool on specific region of frame.
        
        Args:
            frame: BGR frame (H, W, 3)
            x1, y1, x2, y2: Bounding box coordinates
        
        Returns:
            Prediction result
        """
        # Extract region (with safety checks)
        h, w = frame.shape[:2]
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))
        
        region = frame[y1:y2, x1:x2]
        
        if region.size == 0:
            return {
                'primary': None,
                'top_k': [],
                'all_scores': [0.0] * self.num_classes,
                'passed_threshold': False,
                'error': 'Invalid region'
            }
        
        return self.predict(region)


class RegionBasedToolDetector:
    """
    Combines object detection with tool classification.
    
    Strategy:
      1. Use YOLO to detect people/objects
      2. Classify regions containing tools
      3. Return detection + classification results
    """
    
    def __init__(self, classifier_path: str, device: str = 'cuda'):
        """
        Initialize region-based detector.
        
        Args:
            classifier_path: Path to trained classifier model
            device: 'cuda' or 'cpu'
        """
        self.classifier = ToolClassifierInference(classifier_path, device=device)
    
    def detect_tools_in_frame(
        self,
        frame: np.ndarray,
        detected_regions: list,
        confidence_threshold: float = 0.7
    ) -> list:
        """
        Classify tools in detected regions.
        
        Args:
            frame: BGR frame (H, W, 3)
            detected_regions: List of (x1, y1, x2, y2, class_name, conf) from YOLO
            confidence_threshold: Minimum confidence for tool detection
        
        Returns:
            List of {
                'bbox': (x1, y1, x2, y2),
                'yolo_class': str,
                'tool_detected': bool,
                'tool_name': str or None,
                'tool_confidence': float,
                'threat_level': str,
                'original_confidence': float
            }
        """
        results = []
        
        for region_info in detected_regions:
            x1, y1, x2, y2, yolo_class, yolo_conf = region_info
            
            # Classify region
            pred = self.classifier.predict_on_region(frame, x1, y1, x2, y2)
            
            result = {
                'bbox': (int(x1), int(y1), int(x2), int(y2)),
                'yolo_class': yolo_class,
                'original_confidence': float(yolo_conf),
                'tool_detected': False,
                'tool_name': None,
                'tool_confidence': 0.0,
                'threat_level': 'NONE'
            }
            
            if pred['primary'] is not None:
                tool_conf = pred['primary']['confidence']
                
                if tool_conf >= confidence_threshold:
                    result['tool_detected'] = True
                    result['tool_name'] = pred['primary']['class_name']
                    result['tool_confidence'] = tool_conf
                    result['threat_level'] = pred['primary']['threat_level']
            
            results.append(result)
        
        return results


if __name__ == '__main__':
    # Test the classifier
    import cv2
    
    # Try to find a test image
    test_image_path = r'C:\Seethos.ai\ComputerVision\Atm-monitoring\Training-on-Tools\Data-set-tools\Crowbar Dataset Collection\2025-04-16T21-22-59.781Z\0007b9b2-1698-4ffd-aa0b-ccbec43cf76d.jpg'
    
    if Path(test_image_path).exists():
        print("Testing Tool Classifier...")
        print("=" * 60)
        
        # Create dummy model path (will need to train first)
        model_path = r'C:\Seethos.ai\ComputerVision\Atm-monitoring\training\weights\tool_classifier\tool_classifier_final.pth'
        
        if Path(model_path).exists():
            classifier = ToolClassifierInference(model_path)
            
            # Load test image
            image = cv2.imread(test_image_path)
            print(f"Image shape: {image.shape}")
            
            # Predict
            result = classifier.predict(image, return_top_k=3)
            print(f"\nPrediction result:")
            print(json.dumps(result, indent=2))
        else:
            print(f"Model not found at {model_path}")
            print("Please train the model first using: python 11_classify_train.py")
    else:
        print(f"Test image not found at {test_image_path}")
