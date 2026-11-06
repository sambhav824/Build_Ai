import os
from typing import Tuple, Any
from utils.logging_config import logger

class VisionModelLoader:
    """
    Manages loading of Computer Vision models for Site Intelligence.
    Supports Ultralytics YOLO when weights are present locally,
    with an offline visual pipeline fallback for air-gapped / sandbox environments.
    """
    _yolo_model = None

    @classmethod
    def get_detector(cls) -> Tuple[str, Any]:
        """
        Returns ('yolo', model) if YOLO model weight exists locally,
        otherwise ('cv_contour', None) for offline deterministic detection.
        """
        if cls._yolo_model is not None:
            return "yolo", cls._yolo_model

        local_weights = ["yolov8n.pt", "models/yolov8n.pt"]
        for weight in local_weights:
            if os.path.exists(weight):
                try:
                    from ultralytics import YOLO
                    cls._yolo_model = YOLO(weight)
                    logger.info(f"Loaded local YOLO model: {weight}")
                    return "yolo", cls._yolo_model
                except Exception as e:
                    logger.warning(f"Could not initialize YOLO from {weight}: {e}")

        logger.info("Operating in offline Computer Vision mode (local contour & color analysis).")
        return "cv_contour", None
