"""
Audio I/O — microphone capture and speaker playback.

Capture is a generator of 30ms int16 PCM frames at 16kHz — the format webrtcvad expects.
Playback accepts a WAV file path or raw bytes.
"""
from __future__ import annotations

import logging
import queue
import wave
from typing import Iterator

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 480


class Microphone:
    """Streaming mic capture suitable for webrtcvad."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, device: int | None = None):
        import sounddevice as sd  # type: ignore
        self._sd = sd
        self.sample_rate = sample_rate
        self.device = device
        self._q: queue.Queue[bytes] = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=FRAME_SAMPLES,
            device=device,
            callback=self._on_audio,
        )

    def _on_audio(self, indata, frames, time_info, status):  # noqa: D401
        if status:
            log.debug("mic status: %s", status)
        self._q.put(bytes(indata))

    def __enter__(self):
        self._stream.start()
        return self

    def __exit__(self, *_):
        self._stream.stop()
        self._stream.close()

    def frames(self) -> Iterator[bytes]:
        while True:
            yield self._q.get()


def play_wav(path: str) -> None:
    """Blocking WAV playback."""
    import simpleaudio as sa  # type: ignore
    wave_obj = sa.WaveObject.from_wave_file(path)
    play = wave_obj.play()
    play.wait_done()


def save_wav(path: str, pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(sample_rate)
        w.writeframes(pcm_bytes)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import time
    with Microphone() as mic:
        print("recording 2s…")
        chunks = []
        t0 = time.time()
        for frame in mic.frames():
            chunks.append(frame)
            if time.time() - t0 > 2:
                break
        save_wav("/tmp/test.wav", b"".join(chunks))
        print("saved /tmp/test.wav")
