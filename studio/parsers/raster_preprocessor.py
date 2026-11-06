"""
studio.parsers.raster_preprocessor
==================================
Computer Vision Preprocessor for Architectural Floor Plans.
Performs OpenCV-based deskewing, noise filtering, adaptive thresholding,
and morphological wall-line candidate extraction.
"""

import math
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
import cv2
import numpy as np

from utils.logging_config import logger


class RasterPreprocessor:
    """
    Preprocesses 2D architectural raster images (floor plans, blueprints, sketches).
    Prepares clean binary line-work for wall and room recognition algorithms.
    """

    def __init__(self, image_path: str | Path):
        self.image_path = Path(image_path)
        if not self.image_path.exists():
            raise FileNotFoundError(f"Image not found: {self.image_path}")

        # Read image using OpenCV
        self.original_bgr = cv2.imread(str(self.image_path))
        if self.original_bgr is None:
            raise ValueError(f"OpenCV could not decode image at {self.image_path}")

        self.height, self.width = self.original_bgr.shape[:2]

    def grayscale(self) -> np.ndarray:
        """Convert BGR to single-channel 8-bit grayscale."""
        return cv2.cvtColor(self.original_bgr, cv2.COLOR_BGR2GRAY)

    def denoise_and_filter(self, gray: Optional[np.ndarray] = None) -> np.ndarray:
        """Apply edge-preserving bilateral filtering to eliminate paper grain/scratches."""
        img_gray = gray if gray is not None else self.grayscale()
        return cv2.bilateralFilter(img_gray, d=9, sigmaColor=75, sigmaSpace=75)

    def binarize(self, gray: Optional[np.ndarray] = None, invert: bool = True) -> np.ndarray:
        """
        Produce high-contrast binary drawing image using Otsu thresholding.
        invert=True outputs white walls (255) on black background (0), standard for morphological ops.
        """
        img_gray = gray if gray is not None else self.denoise_and_filter()
        thresh_flag = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
        _, binary = cv2.threshold(img_gray, 0, 255, thresh_flag + cv2.THRESH_OTSU)
        return binary

    def detect_skew_angle(self, binary: Optional[np.ndarray] = None) -> float:
        """
        Detect plan tilt/skew angle in degrees using Probabilistic Hough Line Transform.
        Returns angle in degrees to rotate image back to level.
        """
        bin_img = binary if binary is not None else self.binarize()
        lines = cv2.HoughLinesP(
            bin_img,
            rho=1,
            theta=np.pi / 180,
            threshold=120,
            minLineLength=int(min(self.width, self.height) * 0.15),
            maxLineGap=10
        )

        if lines is None or len(lines) == 0:
            return 0.0

        angles: List[float] = []
        for line in lines:
            coords = np.array(line).flatten()
            if len(coords) < 4:
                continue
            x1, y1, x2, y2 = int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])
            dx = x2 - x1
            dy = y2 - y1
            angle = math.degrees(math.atan2(dy, dx))
            # Normalize angle to range [-45, 45]
            if angle < -45:
                angle += 90
            elif angle > 45:
                angle -= 90
            angles.append(angle)

        if not angles:
            return 0.0

        median_angle = float(np.median(angles))
        # Ignore negligible tilt (< 0.2 degrees)
        if abs(median_angle) < 0.2:
            return 0.0

        logger.info(f"Detected drawing skew angle: {median_angle:.2f}°")
        return round(median_angle, 2)

    def deskew(self, image: Optional[np.ndarray] = None, angle: Optional[float] = None) -> Tuple[np.ndarray, float]:
        """Rotate drawing to align walls squarely with horizontal and vertical axes."""
        target_img = image if image is not None else self.original_bgr
        skew_angle = angle if angle is not None else self.detect_skew_angle()

        if abs(skew_angle) < 0.2:
            return target_img, 0.0

        center = (self.width // 2, self.height // 2)
        rot_mat = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
        deskewed = cv2.warpAffine(
            target_img,
            rot_mat,
            (self.width, self.height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        return deskewed, skew_angle

    def extract_wall_lines(
        self,
        binary: Optional[np.ndarray] = None,
        min_wall_length_px: int = 40
    ) -> Dict[str, np.ndarray]:
        """
        Morphological kernel filtering to isolate horizontal and vertical wall candidates.
        Removes thin text and dimension tick marks while preserving thick wall strokes.
        """
        bin_img = binary if binary is not None else self.binarize()

        # Horizontal structuring element
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_wall_length_px, 1))
        h_walls = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, h_kernel)

        # Vertical structuring element
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_wall_length_px))
        v_walls = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, v_kernel)

        # Combined wall mask
        combined_walls = cv2.bitwise_or(h_walls, v_walls)

        return {
            "horizontal": h_walls,
            "vertical": v_walls,
            "combined": combined_walls,
        }

    def save_debug_image(self, img: np.ndarray, name_suffix: str) -> Path:
        """Save an intermediate stage image to disk for inspection / review."""
        out_dir = self.image_path.parent / "studio_processed"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{self.image_path.stem}_{name_suffix}.png"
        cv2.imwrite(str(out_file), img)
        return out_file
