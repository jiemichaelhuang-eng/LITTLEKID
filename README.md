# Companion Robot

A desk-companion robot built by **Michael** (hardware/product) and **Andy** (software/ML). Target: working MVP on a Raspberry Pi 5 in 2–4 weeks. See [`docs/project_plan.md`](docs/project_plan.md) for the full plan.

## Quick start (on the Pi)

```bash
git clone <this-repo> companion-robot
cd companion-robot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # then edit API keys
python main.py
```

## Repo layout

```
companion-robot/
├── hardware/        # Michael owns these — knows the wiring
│   ├── servos.py    # PCA9685 + pan/tilt limits
│   ├── camera.py    # CSI camera capture
│   └── audio_io.py  # mic capture + speaker playback
├── brain/           # Andy owns these — pure software
│   ├── vision.py    # MediaPipe face tracking
│   ├── listen.py    # VAD + Whisper
│   ├── chat.py      # LLM loop
│   └── personality.py
├── display/
│   └── eyes.py      # Pygame eye renderer
├── docs/
│   └── project_plan.md
├── main.py          # Async glue
├── config.example.yaml
└── requirements.txt
```

## Interface contract (the API between the two halves)

These signatures don't change without a discussion — that's the whole point.

| Module | Function | Notes |
|---|---|---|
| `hardware.servos` | `set_head(pan_deg: float, tilt_deg: float)` | Pan ±75°, tilt -30° to +45°. Module enforces limits. |
| `display.eyes` | `render(state: dict)` | `state = {"look_x": float, "look_y": float, "blink": bool, "emotion": str}` |
| `brain.chat` | `async respond(user_text, context) -> (reply_text, emotion, action)` | `action` ∈ `look_left`, `nod`, `tilt_curious`, `None` |

## Branches

- `main` — known-good, demo-able
- `michael/hardware` — Michael's working branch (hardware/, display/)
- `andy/brain` — Andy's working branch (brain/)

Open a PR into `main` once a feature is integration-tested.
