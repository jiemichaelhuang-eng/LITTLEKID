"""
Face tracking — MediaPipe Face Detection on a video stream.

Yields normalised face-centre coordinates (x, y) in [-1, +1] suitable for
driving the pan/tilt head. Negative x = left, positive x = right.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator, Optional

log = logging.getLogger(__name__)


@dataclass
class Face:
    x: float  # -1..+1, +1 = right edge of frame
    y: float  # -1..+1, +1 = bottom edge
    confidence: float


class FaceTracker:
    def __init__(self, detection_confidence: float = 0.6):
        import mediapipe as mp  # type: ignore
        self._mp = mp
        self._detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=detection_confidence
        )

    def detect(self, bgr_frame) -> Optional[Face]:
        # MediaPipe wants RGB.
        rgb = bgr_frame[..., ::-1]
        out = self._detector.process(rgb)
        if not out.detections:
            return None
        # Pick the largest detection.
        best = max(out.detections, key=lambda d: d.location_data.relative_bounding_box.width)
        b = best.location_data.relative_bounding_box
        cx = b.xmin + b.width / 2     # 0..1
        cy = b.ymin + b.height / 2
        return Face(
            x=(cx - 0.5) * 2.0,
            y=(cy - 0.5) * 2.0,
            confidence=best.score[0],
        )

    def stream(self, frames: Iterator) -> Iterator[Optional[Face]]:
        for f in frames:
            yield self.detect(f)
