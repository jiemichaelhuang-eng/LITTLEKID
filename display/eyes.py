"""
Eye renderer — Pygame, fullscreen, on the framebuffer.

Interface contract:
    render(state: dict) where state =
        {"look_x": -1..+1, "look_y": -1..+1, "blink": bool, "emotion": str}

Render in its own thread at 30fps; the brain just mutates state.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

import pygame  # type: ignore


@dataclass
class EyeState:
    look_x: float = 0.0
    look_y: float = 0.0
    blink: bool = False
    emotion: str = "neutral"


EMOTION_COLOURS = {
    "neutral":   (120, 200, 255),
    "happy":     (255, 220, 120),
    "curious":   (180, 255, 200),
    "sad":       (100, 130, 200),
    "surprised": (255, 180, 220),
    "sleepy":    (180, 180, 180),
}


class EyeRenderer:
    def __init__(self, width: int = 1024, height: int = 600, fullscreen: bool = True):
        pygame.init()
        flags = pygame.FULLSCREEN if fullscreen else 0
        self.screen = pygame.display.set_mode((width, height), flags)
        self.width, self.height = width, height
        self.state = EyeState()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self.state, k, v)

    def render(self, state: dict) -> None:
        """Convenience wrapper matching the section-3 interface contract."""
        self.update(**state)

    def _draw(self) -> None:
        with self._lock:
            s = EyeState(**self.state.__dict__)

        self.screen.fill((10, 10, 14))
        cx_l = self.width * 0.33
        cx_r = self.width * 0.67
        cy = self.height * 0.5
        eye_w = self.width * 0.18
        eye_h = self.height * 0.45 * (0.1 if s.blink else 1.0)
        colour = EMOTION_COLOURS.get(s.emotion, EMOTION_COLOURS["neutral"])

        # Tilt cue: "curious" raises the right eye slightly.
        tilt = 8 if s.emotion == "curious" else 0

        for (cx, dy) in ((cx_l, 0), (cx_r, -tilt)):
            rect = pygame.Rect(0, 0, eye_w, eye_h)
            rect.center = (cx + s.look_x * 20, cy + s.look_y * 15 + dy)
            pygame.draw.rect(self.screen, colour, rect, border_radius=int(eye_w * 0.4))
        pygame.display.flip()

    def _loop(self, fps: int) -> None:
        clock = pygame.time.Clock()
        while not self._stop.is_set():
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self._stop.set()
            self._draw()
            clock.tick(fps)

    def start(self, fps: int = 30) -> None:
        self._thread = threading.Thread(target=self._loop, args=(fps,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        pygame.quit()


if __name__ == "__main__":
    # Demo: eyes looking around, blinking occasionally.
    eyes = EyeRenderer(fullscreen=False)
    eyes.start()
    t0 = time.time()
    try:
        while True:
            t = time.time() - t0
            eyes.update(
                look_x=math.sin(t * 0.8),
                look_y=math.sin(t * 0.5) * 0.4,
                blink=int(t) % 4 == 0 and (t - int(t)) < 0.15,
                emotion="curious" if int(t) % 10 < 5 else "happy",
            )
            time.sleep(1 / 30)
    except KeyboardInterrupt:
        eyes.stop()
