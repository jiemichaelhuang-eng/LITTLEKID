"""
Camera capture — wraps picamera2 on the Pi, falls back to OpenCV on dev laptops.

Yields BGR numpy frames so MediaPipe / OpenCV can consume them directly.
"""
from __future__ import annotations

import logging
from typing import Iterator

import numpy as np

log = logging.getLogger(__name__)


class Camera:
    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self._impl = self._open()

    def _open(self):
        # Prefer the Pi CSI camera.
        try:
            from picamera2 import Picamera2  # type: ignore
            cam = Picamera2()
            cfg = cam.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"}
            )
            cam.configure(cfg)
            cam.start()
            log.info("picamera2 started (%dx%d @ %dfps)", self.width, self.height, self.fps)
            return ("picamera2", cam)
        except Exception as e:  # noqa: BLE001
            log.info("picamera2 unavailable (%s) — falling back to OpenCV", e)

        import cv2  # type: ignore
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        if not cap.isOpened():
            raise RuntimeError("No camera available")
        return ("cv2", cap)

    def read(self) -> np.ndarray:
        kind, dev = self._impl
        if kind == "picamera2":
            frame = dev.capture_array()
            # picamera2 hands back RGB; convert to BGR for OpenCV/MediaPipe.
            return frame[..., ::-1].copy()
        ok, frame = dev.read()
        if not ok:
            raise RuntimeError("camera read failed")
        return frame

    def frames(self) -> Iterator[np.ndarray]:
        while True:
            yield self.read()

    def close(self) -> None:
        kind, dev = self._impl
        if kind == "picamera2":
            dev.stop()
        else:
            dev.release()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cam = Camera()
    f = cam.read()
    print("frame shape:", f.shape)
    cam.close()
