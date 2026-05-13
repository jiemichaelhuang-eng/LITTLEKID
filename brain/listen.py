"""
Listen — VAD-gated speech capture, transcribed with Whisper.

Strategy:
1. Read 30ms int16 frames from hardware.audio_io.Microphone.
2. Feed each frame to webrtcvad. Buffer voiced frames.
3. After `silence_ms` of silence following speech, emit the buffered utterance.
4. Hand the utterance to Whisper (OpenAI API for v1; faster-whisper for v2).
"""
from __future__ import annotations

import io
import logging
import wave
from collections import deque
from dataclasses import dataclass
from typing import AsyncIterator, Iterator

from hardware.audio_io import FRAME_MS, FRAME_SAMPLES, SAMPLE_RATE

log = logging.getLogger(__name__)


@dataclass
class ListenConfig:
    vad_aggressiveness: int = 2   # 0..3
    silence_ms: int = 600
    preroll_ms: int = 300         # keep a bit of context before speech starts


class SpeechSegmenter:
    """Stateful: yields utterance bytes (int16 PCM) once VAD says we're done speaking."""

    def __init__(self, cfg: ListenConfig | None = None):
        import webrtcvad  # type: ignore
        self.cfg = cfg or ListenConfig()
        self._vad = webrtcvad.Vad(self.cfg.vad_aggressiveness)
        preroll_frames = self.cfg.preroll_ms // FRAME_MS
        self._preroll: deque[bytes] = deque(maxlen=preroll_frames)
        self._silence_frames_needed = self.cfg.silence_ms // FRAME_MS

    def segments(self, frames: Iterator[bytes]) -> Iterator[bytes]:
        in_speech = False
        buf: list[bytes] = []
        silence_count = 0
        for frame in frames:
            is_speech = self._vad.is_speech(frame, SAMPLE_RATE)
            if not in_speech:
                self._preroll.append(frame)
                if is_speech:
                    in_speech = True
                    buf = list(self._preroll)
                    buf.append(frame)
                    silence_count = 0
            else:
                buf.append(frame)
                if is_speech:
                    silence_count = 0
                else:
                    silence_count += 1
                    if silence_count >= self._silence_frames_needed:
                        yield b"".join(buf)
                        in_speech = False
                        buf = []
                        self._preroll.clear()


def pcm_to_wav_bytes(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return bio.getvalue()


async def transcribe(pcm: bytes, model: str = "whisper-1") -> str:
    """Send to OpenAI Whisper. Replace with faster-whisper for offline v2."""
    from openai import AsyncOpenAI  # type: ignore
    client = AsyncOpenAI()
    wav = pcm_to_wav_bytes(pcm)
    result = await client.audio.transcriptions.create(
        model=model,
        file=("speech.wav", wav, "audio/wav"),
    )
    return result.text.strip()


async def utterances(frames: Iterator[bytes]) -> AsyncIterator[str]:
    seg = SpeechSegmenter()
    for pcm in seg.segments(frames):
        text = await transcribe(pcm)
        if text:
            log.info("heard: %s", text)
            yield text
