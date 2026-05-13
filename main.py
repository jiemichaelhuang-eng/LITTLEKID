"""
main.py — async glue that owns the event loop.

Tasks:
  vision_loop:    camera → MediaPipe → Mood + servo target
  servo_loop:     30Hz smoothing tick → PCA9685
  audio_loop:     mic → VAD → Whisper → chat.respond → TTS → speaker
  director_loop:  consumes mood + last chat reply → updates eye state
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import yaml

# Local imports
from brain.chat import ChatContext, respond
from brain.listen import SpeechSegmenter, transcribe
from brain.personality import Mood
from brain.vision import FaceTracker
from display.eyes import EyeRenderer
from hardware.audio_io import Microphone
from hardware.camera import Camera
from hardware.servos import HeadController, ServoConfig

log = logging.getLogger("main")


def load_config(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        log.warning("%s not found; using defaults", path)
        return {}
    return yaml.safe_load(p.read_text())


async def vision_loop(cam: Camera, tracker: FaceTracker, head: HeadController,
                      mood: Mood, eyes: EyeRenderer) -> None:
    loop = asyncio.get_running_loop()
    while True:
        frame = await loop.run_in_executor(None, cam.read)
        face = tracker.detect(frame)
        if face is None:
            eyes.update(look_x=0.0, look_y=0.0)
            await asyncio.sleep(1 / 30)
            continue
        mood.saw_face()
        # Map face position to servo angles. Negate so robot looks AT the face.
        head.set_head(pan_deg=-face.x * 60, tilt_deg=-face.y * 30)
        eyes.update(look_x=face.x * 0.6, look_y=face.y * 0.6)
        await asyncio.sleep(1 / 30)


async def servo_loop(head: HeadController) -> None:
    while True:
        head.tick()
        await asyncio.sleep(1 / 30)


async def audio_loop(eyes: EyeRenderer, mood: Mood) -> None:
    ctx = ChatContext()
    seg = SpeechSegmenter()
    loop = asyncio.get_running_loop()
    with Microphone() as mic:
        frames = mic.frames()
        # Run the blocking segmenter in an executor; bridge to async via a queue.
        q: asyncio.Queue[bytes] = asyncio.Queue()

        def producer():
            for utterance in seg.segments(frames):
                loop.call_soon_threadsafe(q.put_nowait, utterance)

        loop.run_in_executor(None, producer)

        while True:
            pcm = await q.get()
            mood.heard_speech()
            text = await transcribe(pcm)
            if not text:
                continue
            log.info("user: %s", text)
            reply, emotion, _action = await respond(text, ctx)
            mood.react_to_emotion(emotion)
            eyes.update(emotion=emotion)
            # TODO: pipe `reply` to a TTS provider and play through the speaker.
            log.info("robot: %s", reply)


async def director_loop(mood: Mood, eyes: EyeRenderer) -> None:
    """Slow tick — anything that doesn't belong in the hot paths."""
    while True:
        mood.tick()
        if mood.energy < 0.35:
            eyes.update(emotion="sleepy")
        await asyncio.sleep(1.0)


async def amain() -> None:
    cfg = load_config()

    head = HeadController(ServoConfig(**cfg.get("hardware", {}).get("servo", {})))
    cam = Camera(**cfg.get("hardware", {}).get("camera", {}))
    tracker = FaceTracker(**cfg.get("brain", {}).get("vision", {}))
    eyes = EyeRenderer(**cfg.get("display", {}))
    mood = Mood()

    eyes.start(fps=cfg.get("display", {}).get("fps", 30))

    try:
        await asyncio.gather(
            vision_loop(cam, tracker, head, mood, eyes),
            servo_loop(head),
            audio_loop(eyes, mood),
            director_loop(mood, eyes),
        )
    finally:
        eyes.stop()
        cam.close()
        head.relax()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        sys.exit(0)
