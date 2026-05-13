"""
Personality / mood state machine.

A small internal state — energy, mood, attention — that the director task
reads when picking eye/head animations. Not strictly ML, but it's what makes
the robot feel alive instead of like a chatbot.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class Mood:
    energy: float = 0.6      # 0..1; decays slowly, rises with interaction
    valence: float = 0.5     # 0..1; 0=sad, 1=happy
    attention: float = 0.0   # 0..1; rises when a face is present
    _last_tick: float = 0.0

    def tick(self) -> None:
        now = time.monotonic()
        dt = max(0.0, now - self._last_tick) if self._last_tick else 0.0
        self._last_tick = now
        # Energy decays toward 0.3 over ~5 minutes when idle.
        self.energy += (0.3 - self.energy) * (dt / 300.0)

    def saw_face(self) -> None:
        self.attention = min(1.0, self.attention + 0.2)
        self.energy = min(1.0, self.energy + 0.05)

    def heard_speech(self) -> None:
        self.energy = min(1.0, self.energy + 0.1)

    def react_to_emotion(self, emotion: str) -> None:
        mapping = {"happy": 0.1, "sad": -0.1, "surprised": 0.05, "curious": 0.02}
        self.valence = max(0.0, min(1.0, self.valence + mapping.get(emotion, 0.0)))
