"""
Servo control — owns the pan/tilt head.

Interface contract (do not change without discussion):
    set_head(pan_deg: float, tilt_deg: float) -> None

The Brain sends angles, never raw PWM. This module enforces limits so a
software bug can't strip a gear, and applies exponential smoothing so the
head doesn't jerk on sudden target jumps.

Hardware: Adafruit PCA9685 over I2C, 2x MG90S micro servos.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class ServoConfig:
    i2c_address: int = 0x40
    pan_channel: int = 0
    tilt_channel: int = 1
    pan_min_deg: float = -75.0
    pan_max_deg: float = 75.0
    tilt_min_deg: float = -30.0
    tilt_max_deg: float = 45.0
    smoothing: float = 0.25  # 0 = instant, 1 = never move


class HeadController:
    """Single-instance servo driver. Thread-safe."""

    def __init__(self, cfg: ServoConfig | None = None):
        self.cfg = cfg or ServoConfig()
        self._lock = threading.Lock()
        self._current_pan = 0.0
        self._current_tilt = 0.0
        self._target_pan = 0.0
        self._target_tilt = 0.0
        self._kit = self._init_kit()

    def _init_kit(self):
        try:
            from adafruit_servokit import ServoKit  # type: ignore
            kit = ServoKit(channels=16, address=self.cfg.i2c_address)
            log.info("PCA9685 initialised at 0x%02x", self.cfg.i2c_address)
            return kit
        except Exception as e:  # noqa: BLE001
            log.warning("ServoKit unavailable (%s) — running in mock mode", e)
            return None

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    def set_head(self, pan_deg: float, tilt_deg: float) -> None:
        """Set the desired head position in degrees. Smoothed; safe to call at 30Hz."""
        with self._lock:
            self._target_pan = self._clamp(pan_deg, self.cfg.pan_min_deg, self.cfg.pan_max_deg)
            self._target_tilt = self._clamp(tilt_deg, self.cfg.tilt_min_deg, self.cfg.tilt_max_deg)

    def tick(self) -> None:
        """Advance the smoother one step and write to the servos. Call from a 30Hz loop."""
        with self._lock:
            a = 1.0 - self.cfg.smoothing
            self._current_pan += (self._target_pan - self._current_pan) * a
            self._current_tilt += (self._target_tilt - self._current_tilt) * a
            pan = self._current_pan
            tilt = self._current_tilt
        self._write(pan, tilt)

    def _write(self, pan_deg: float, tilt_deg: float) -> None:
        if self._kit is None:
            return
        # ServoKit angle is 0..180; map our centred range to that.
        self._kit.servo[self.cfg.pan_channel].angle = 90.0 + pan_deg
        self._kit.servo[self.cfg.tilt_channel].angle = 90.0 + tilt_deg

    def relax(self) -> None:
        """Disable PWM to stop idle jitter. Call when the head reaches its target."""
        if self._kit is None:
            return
        self._kit.servo[self.cfg.pan_channel].angle = None
        self._kit.servo[self.cfg.tilt_channel].angle = None


# Module-level convenience for the simplest possible API.
_default: HeadController | None = None


def set_head(pan_deg: float, tilt_deg: float) -> None:
    global _default
    if _default is None:
        _default = HeadController()
    _default.set_head(pan_deg, tilt_deg)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    h = HeadController()
    print("Sweep test: 5 seconds of pan motion")
    t0 = time.time()
    import math
    while time.time() - t0 < 5:
        h.set_head(60 * math.sin(time.time() * 2), 0)
        h.tick()
        time.sleep(1 / 30)
    h.relax()
