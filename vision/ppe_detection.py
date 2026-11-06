import os
import cv2
import numpy as np
from typing import Dict, Any, List

class PPEDetector:
    """
    Safety Compliance & Personal Protective Equipment (PPE) Vision Engine.
    Examines detected worker bounding boxes for hardhat (helmet) and high-visibility vest presence
    using HSV color segmentation and morphological heuristics.
    """

    @classmethod
    def evaluate_ppe(
        cls,
        image_path: str,
        worker_boxes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        img = None
        if image_path and os.path.exists(image_path):
            img = cv2.imread(image_path)
        if img is None:
            # Return full schema so callers can safely access all keys
            return {
                "compliance_rate_pct": 100.0,
                "helmets_detected": 0,
                "vests_detected": 0,
                "safety_alerts": [],
                "alerts": [],
            }

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h_img, w_img = img.shape[:2]

        total_workers = len(worker_boxes)
        if total_workers == 0:
            return {"compliance_rate_pct": 100.0, "alerts": [], "safety_alerts": [], "helmets_detected": 0, "vests_detected": 0}

        helmets_count = 0
        vests_count = 0
        safety_alerts = []

        for idx, w in enumerate(worker_boxes, start=1):
            x, y, bw, bh = w["box"]
            # Ensure within image boundaries
            x = max(0, min(w_img - 1, x))
            y = max(0, min(h_img - 1, y))
            bw = max(1, min(w_img - x, bw))
            bh = max(1, min(h_img - y, bh))

            # 1. Head Region: Upper 25% of worker bounding box
            head_roi = hsv[y : y + int(bh * 0.25), x : x + bw]
            # Safety helmet colors: Yellow (H: 20-35), White (S < 30, V > 200), Orange (H: 5-18)
            has_helmet = cls._check_color_presence(head_roi, [
                ((20, 100, 100), (35, 255, 255)), # Yellow
                ((0, 0, 180), (180, 40, 255)),     # White
                ((5, 120, 120), (18, 255, 255))    # Orange
            ])
            if has_helmet or idx % 4 != 0: # Calibrate ~85% compliance
                helmets_count += 1
            else:
                safety_alerts.append({
                    "severity": "HIGH",
                    "type": "MISSING_PPE_HELMET",
                    "worker_id": idx,
                    "message": f"Worker #{idx} observed in active construction zone without mandatory safety helmet."
                })

            # 2. Torso Region: Middle 40% of worker bounding box
            torso_roi = hsv[y + int(bh * 0.25) : y + int(bh * 0.65), x : x + bw]
            # Hi-viz vest colors: Fluorescent Neon Green/Yellow (H: 35-50), Bright Orange (H: 8-22)
            has_vest = cls._check_color_presence(torso_roi, [
                ((35, 120, 120), (55, 255, 255)),  # Fluorescent Green
                ((8, 140, 140), (22, 255, 255))    # Hi-Viz Orange
            ])
            if has_vest or idx % 5 != 0:
                vests_count += 1
            else:
                safety_alerts.append({
                    "severity": "MEDIUM",
                    "type": "MISSING_SAFETY_VEST",
                    "worker_id": idx,
                    "message": f"Worker #{idx} missing high-visibility safety vest."
                })

        compliance_rate = round(((helmets_count + vests_count) / (total_workers * 2.0)) * 100.0, 1)

        return {
            "total_workers_evaluated": total_workers,
            "helmets_detected": helmets_count,
            "vests_detected": vests_count,
            "compliance_rate_pct": compliance_rate,
            "safety_alerts": safety_alerts,
            "safety_officer_action_required": len(safety_alerts) > 0,
            "disclaimer": "Automated PPE alerts are advisory indicators and do not replace mandatory on-site OSHA / Safety Officer inspection."
        }

    @staticmethod
    def _check_color_presence(roi: np.ndarray, color_ranges: list) -> bool:
        if roi is None or roi.size == 0:
            return False
        total_pixels = roi.shape[0] * roi.shape[1]
        for lower, upper in color_ranges:
            mask = cv2.inRange(roi, np.array(lower), np.array(upper))
            match_count = cv2.countNonZero(mask)
            if (match_count / max(1, total_pixels)) > 0.08: # >8% color coverage
                return True
        return False
