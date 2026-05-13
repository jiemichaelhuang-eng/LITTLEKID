"""
Chat — wraps the LLM call so the rest of the robot doesn't know which provider it's using.

Interface contract:
    async respond(user_text, context) -> (reply_text, emotion, action)

`emotion` ∈ {"neutral", "happy", "curious", "sad", "surprised", "sleepy"}
`action`  ∈ {"look_left", "look_right", "nod", "tilt_curious", None}
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Literal

log = logging.getLogger(__name__)

Emotion = Literal["neutral", "happy", "curious", "sad", "surprised", "sleepy"]
Action = Literal["look_left", "look_right", "nod", "tilt_curious"] | None


@dataclass
class ChatContext:
    history: list[dict] = field(default_factory=list)  # [{"role": ..., "content": ...}, ...]
    max_turns: int = 12

    def add(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        # Trim to last N turns (user+assistant pair = 2 entries).
        excess = len(self.history) - self.max_turns * 2
        if excess > 0:
            self.history = self.history[excess:]


SYSTEM_PROMPT = (
    "You are a small desk companion robot. You are warm, curious, and brief.\n"
    "Reply in 1-3 sentences. After your reply, append a JSON tag on a new line "
    'like: {"emotion": "curious", "action": "tilt_curious"}.\n'
    "Valid emotions: neutral, happy, curious, sad, surprised, sleepy.\n"
    "Valid actions: look_left, look_right, nod, tilt_curious, or null."
)

_TAG_RE = re.compile(r"\{[^{}]*\"emotion\"[^{}]*\}")


def _parse_tag(reply: str) -> tuple[str, Emotion, Action]:
    m = _TAG_RE.search(reply)
    if not m:
        return reply.strip(), "neutral", None
    raw = m.group(0)
    spoken = (reply[: m.start()] + reply[m.end():]).strip()
    try:
        meta = json.loads(raw)
        emo: Emotion = meta.get("emotion", "neutral")
        act = meta.get("action")
        return spoken, emo, act
    except json.JSONDecodeError:
        return spoken, "neutral", None


async def respond(
    user_text: str,
    context: ChatContext,
    model: str = "gpt-4o-mini",
) -> tuple[str, Emotion, Action]:
    from openai import AsyncOpenAI  # type: ignore
    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    context.add("user", user_text)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *context.history]

    resp = await client.chat.completions.create(model=model, messages=messages)
    raw = resp.choices[0].message.content or ""
    text, emotion, action = _parse_tag(raw)
    context.add("assistant", raw)
    log.info("said: %s [%s/%s]", text, emotion, action)
    return text, emotion, action
