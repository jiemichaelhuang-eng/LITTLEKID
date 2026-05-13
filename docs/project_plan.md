# Desk Companion Robot — Project Plan

A two-person build: Michael (hardware/product) + Andy (software/ML). Target: working desk MVP in 2–4 weeks, with a clear path to a wearable shoulder version later.

---

## 1. System Architecture

Think of the robot as three layers that you can build and test independently before merging them. This separation is the single most important design decision — it lets each of you make progress without blocking the other.

**Layer 1 — Body (your domain).** Mechanical chassis, head pan/tilt mechanism, screen mount, camera mount, speaker, mic, battery, power distribution, wiring harness.

**Layer 2 — Brain (your friend's domain, runs on the Raspberry Pi).** Vision pipeline, audio pipeline, conversation engine, "personality" state machine, output renderer (eyes + speech + motion commands).

**Layer 3 — Nerves (shared).** The protocols that let the Brain talk to the Body — servo commands, screen frames, audio in/out. This is the interface contract you both agree on at the start.

The data flow each second of the robot's life looks like this: the camera and microphone feed the Brain; the Brain decides what to look at, what to say, and how to feel; the Brain then renders eyes to the screen, sends servo angles to the motor driver, and pipes synthesized speech to the speaker. Everything runs on one Pi in the MVP — no networked services, no second microcontroller. Keep it simple.

### Recommended topology for MVP

```
 ┌────────────────────────────────────────────┐
 │              Raspberry Pi 5                │
 │                                            │
 │  ┌──────────┐   ┌────────────┐   ┌──────┐  │
 │  │  Vision  │──▶│            │──▶│ Eyes │──┼──▶ HDMI/DSI screen
 │  │ (camera) │   │            │   └──────┘  │
 │  └──────────┘   │   Brain    │             │
 │  ┌──────────┐   │  (Python)  │   ┌──────┐  │
 │  │  Audio   │──▶│            │──▶│ TTS  │──┼──▶ Speaker
 │  │  (mic)   │   │            │   └──────┘  │
 │  └──────────┘   └─────┬──────┘             │
 │                       │                    │
 │                       ▼ I²C                │
 │                 ┌──────────┐               │
 │                 │ PCA9685  │──── PWM ──────┼──▶ 2× servos (pan/tilt)
 │                 └──────────┘               │
 └────────────────────────────────────────────┘
```

**Skip the ESP32 for the MVP.** With a 2–4 week timeline and "some experience," adding a second microcontroller and a serial protocol doubles the integration work for zero gain. The Pi can drive servos directly through a PCA9685 over I²C. Add the ESP32 in v2 when you want the head to be wireless or untethered from the brain.

---

## 2. Hardware Bill of Materials (MVP)

Prices in USD, sourced from Amazon/Adafruit/Pimoroni in mid-2026. Substitutions are fine — these are the proven-easy versions.

| Category | Part | ~Price | Why this one |
|---|---|---|---|
| **Brain** | Raspberry Pi 5, 8GB | $80 | Plenty for MediaPipe + Whisper-small + a chat loop. Skip Jetson — overkill, harder OS, worse ecosystem for your stack. |
| **Storage** | SanDisk 64GB A2 microSD | $10 | A2 rating matters for Pi 5 boot speed |
| **Power (desk)** | Official Pi 5 27W USB-C PSU | $12 | Pi 5 is power-hungry; cheaper bricks brown-out under camera + servo load |
| **Servo driver** | Adafruit PCA9685 16-channel | $15 | I²C, separate servo power rail, room to grow to 16 motors |
| **Servos** | 2× MG90S metal-gear micro servos | $12 | For head pan/tilt. Skip SG90 plastic gears — they strip after a week of face tracking |
| **Servo power** | 5V 3A buck converter or separate 5V 2A USB plug | $8 | Servos must NOT share the Pi's 5V rail — they cause brownouts |
| **Camera** | Raspberry Pi Camera Module 3 (wide) | $35 | Native CSI, autofocus, 12MP, MediaPipe-friendly. Much better than USB webcams on Pi. |
| **Screen** | 7.9" or 5" HDMI IPS LCD (1024×600 ish) | $45 | Big enough for two animated eyes side-by-side. Use HDMI not SPI — SPI screens are too slow for smooth eye animation. |
| **Microphone** | ReSpeaker 2-Mic HAT (or USB lavalier) | $25 | The HAT has hardware beamforming; the cheap lav works fine for MVP |
| **Speaker** | Adafruit Mini External USB speaker or 3W I²S amp + cone | $15 | USB is plug-and-play; I²S is cleaner audio |
| **Wiring** | Dupont jumper kit, JST connectors, heat-shrink | $15 | Don't skip — quality wiring saves hours of debugging |
| **Prototyping** | Half-size breadboard, 5V/GND distribution rail | $8 | For the screen-eye-mockup stage before printing the case |
| **Chassis** | PLA filament (1kg, dark gray) | $25 | Already have a printer? Skip this; if you need prints, JLCPCB/PCBWay/local makerspace |
| **Misc** | M2/M2.5/M3 screw assortment, threaded inserts, brass standoffs | $20 | Heat-set inserts make plastic cases feel premium and let you re-open them |
| | | **~$325** | Comfortable middle of the "Flexible" budget |

**Things to skip in v1 (add later):**
- Battery + charging circuit → desk robot runs on wall power; batteries add a week of work
- IMU/accelerometer → no use until you want gesture response or balance
- Touch sensor → cute but unnecessary
- LIDAR / ToF → for navigation; this robot doesn't move
- ESP32 → covered above

---

## 3. Hardware ↔ Software Interface (the contract)

This is the document you and your friend write together on day 1 and don't change. It's the API between your two halves.

**Servo commands.** The Brain sends desired angles, not raw PWM. Wrap the PCA9685 in a small Python module (`hardware/servos.py`) with one function: `set_head(pan_deg, tilt_deg)`. Pan range: -75 to +75. Tilt range: -30 to +45. Your friend writes high-level logic; your module does the angle-to-pulse-width math and enforces limits so a software bug can't strip a gear.

**Eye rendering.** The Brain owns a `display/eyes.py` module that exposes one call: `render(state)`, where `state` is a small dict — `{ "look_x": 0.3, "look_y": -0.1, "blink": False, "emotion": "curious" }`. Implement with Pygame in fullscreen mode on the framebuffer. Your friend just updates the state; the renderer redraws at 30fps in its own thread.

**Audio.** Use `sounddevice` for capture and `simpleaudio` or `pygame.mixer` for playback. Voice activity detection with `webrtcvad` so you only send speech segments to Whisper.

**Conversation.** Wrap GPT calls behind `brain/chat.py` with one async function `respond(user_text, context) -> (reply_text, emotion, action)`. The action can be `"look_left" | "nod" | "tilt_curious" | None`. This keeps the conversation logic decoupled from the rest.

**The folder layout you start with on the Pi:**

```
companion-robot/
├── hardware/        # Michael owns these — knows the wiring
│   ├── servos.py
│   ├── camera.py
│   └── audio_io.py
├── brain/           # Friend owns these — pure software
│   ├── vision.py    # MediaPipe face tracking
│   ├── listen.py    # VAD + Whisper
│   ├── chat.py      # GPT loop
│   └── personality.py
├── display/
│   └── eyes.py      # Pygame renderer
├── main.py          # Glues everything together
└── config.yaml      # Tunables: servo limits, model names, API keys
```

Use git from day 1. One repo. Your friend works on `brain/` branches; you work on `hardware/` and `display/` branches.

---

## 4. The 2–4 Week MVP

**Definition of done for the MVP:** the robot sits on your desk, displays animated eyes, follows your face with its head, and when you speak to it, it transcribes what you said, sends it to GPT, speaks the reply back, and shows an emotion-tinted eye expression. Wall-powered, single Pi, plastic case.

That's it. Resist scope creep. Battery, wake-word, wearable form, persistent memory, custom personality — all v2.

### Week-by-week roadmap

**Week 1 — Bring-up and "hello world" in parallel.**

You (hardware):
- Order parts day 1 (shipping is your critical path)
- While waiting: design the head mechanism in Blender — a pan servo at the base, a tilt servo on top, the screen mounted on the tilt bracket. Look up "two-servo pan-tilt bracket" for reference geometry; don't reinvent it.
- When parts arrive: assemble Pi, flash Raspberry Pi OS Bookworm 64-bit, get the camera and screen working, wire the PCA9685, write `servos.py`, prove you can sweep both servos through their ranges from a Python REPL.

Your friend (software):
- Spin up the repo, set up Python 3.11 venv on their own laptop with `mediapipe`, `openai-whisper`, `openai`, `pygame`
- Build `eyes.py` standalone — animated blinking eyes that take a "look_x/look_y" input. Test on their laptop first; deploy to Pi later.
- Build `vision.py` standalone using their laptop's webcam — MediaPipe Face Detection returning normalized face center coordinates at 30fps.

**Week 2 — First integration: the head looks at you.**

Together, on the Pi: feed `vision.py` output into `servos.py` through a simple proportional controller (smooth out the motion — naive control will be jittery; use exponential smoothing on the target angle). When this works the robot can sit on your desk and just look at faces. This alone is uncanny and impressive — show it to people.

Meanwhile, your friend builds `listen.py`: webrtcvad detects when you start and stop speaking, captures the WAV segment, runs Whisper-small (or the OpenAI hosted Whisper API for speed), prints the transcription. Test as a standalone script.

**Week 3 — Voice loop.**

Your friend wires `listen.py` → `chat.py` (OpenAI Chat Completions) → TTS (OpenAI TTS is fastest to integrate, or `piper` for fully-local) → speaker. Now you can have a conversation with no body movement.

You: design and print the case. Make it open-back / serviceable. Use heat-set inserts. Plan a cable routing path. Three iterations is normal — don't expect first-print success.

**Week 4 — Glue and polish.**

`main.py` runs everything in async tasks: vision loop, audio loop, eye render loop, plus a "director" task that consumes vision + chat events and updates eye state and head motion. Add the action vocabulary — when GPT replies with a "curious" emotion, eyes squint and head tilts 10°. Bug-bash, demo, record video.

**If you slip the timeline,** drop these features first: emotion-driven head motions, autofocus tuning, fancy eye animations. Keep: face tracking, voice loop, basic eyes.

---

## 5. Frameworks & Tools Recommendations

**Vision — use MediaPipe, not YOLO.** YOLO is heavy and overkill for face tracking. MediaPipe Face Detection and Face Mesh run at 30fps on a Pi 5 CPU, give you eye/nose landmarks for free, and have zero setup pain. Keep YOLO in mind only if you later want to recognize objects ("what am I holding up?").

**Speech in — start with the OpenAI Whisper API.** It's fast and free-ish. Move to local `whisper.cpp` or `faster-whisper` only if you want offline operation; the small model runs at near-realtime on a Pi 5.

**Speech out — OpenAI TTS for v1, Piper for v2.** OpenAI gets you a good voice in 5 minutes. Piper is fully local, free forever, and has cute character voices.

**LLM — OpenAI Chat Completions (gpt-4o-mini is the right tier for cost/quality), or Anthropic's Claude Haiku.** Both are cheap and fast. For under $5/month of usage you'll be fine.

**ROS2 — skip for now.** ROS2 is overkill for a single-Pi single-process robot and will eat a week of your timeline. Adopt it only when you have multiple compute nodes or sensors and need their pub/sub system. A python asyncio main loop is plenty.

**Eyes — Pygame.** Don't use a web tech (React/Electron) for eyes; the latency and resource cost is significant. Pygame on the Pi's framebuffer is 20 lines of code and butter-smooth.

**Servo control — adafruit-circuitpython-servokit.** Wraps PCA9685 nicely. Three lines to drive a servo.

**Development workflow — VSCode Remote-SSH into the Pi.** Edit files on your laptop, they save and run on the Pi. Don't develop in nano over SSH unless you enjoy pain.

---

## 6. Designing a Manufacturable Casing

A few principles that will save you a lot of pain:

**Design around the screen first.** The screen drives the front face geometry. Everything else fits around it. Mount the camera directly above the screen — eye contact feels natural that way. The mic goes in front (not buried) so it picks up speech clearly.

**Two-shell construction.** Front shell and back shell, joined by 4 M3 screws through heat-set inserts. The back is removable for service. Internal mounting features (boss posts, snap clips) hold the Pi, screen, and servo bracket without extra brackets.

**Print orientation matters.** Orient parts so screw bosses and hinge points print along the layer lines, not perpendicular — perpendicular print directions make these features weak. PrusaSlicer's "Paint-on Supports" is your friend.

**Wall thickness:** 2.4mm for body shells (= 6 perimeters at 0.4mm nozzle), 3mm where threads or screws bite in. Less than 2mm and the case feels cheap and flexes.

**Tolerances:** for a screw hole, model the shaft diameter +0.2mm. For a press-fit, -0.1mm. Print one tolerance test print before committing to the full case.

**Cable management:** plan the cable runs in Blender before you print. Reserve a 5mm channel along one inside wall for the camera ribbon and another for power. Otherwise you'll print a beautiful case that won't close.

**Make it look like a product, not a prototype.** Curves and chamfers cost nothing and read as "designed" rather than "engineered". Look at Vector / Cozmo / Loona / Misa for proportions. The screen should feel like a face, not a panel — slight curvature, framed by the body, with the camera tucked in like a forehead dot.

**Tools:**
- Blender for modeling (you already plan to use it — totally viable for this scale of part). Add the "Bool Tool" and "LoopTools" addons.
- PrusaSlicer or OrcaSlicer for slicing.
- For when you eventually want to manufacture: JLC3DP / PCBWay 3D Printing / Hubs do MJF nylon prints that look injection-molded for ~$30 per part. SLA at JLC for screen bezels is very nice.

---

## 7. Cool, Realistic ML Features for the v2 Backlog

Once the MVP is alive, these are the high-impact-per-week-of-work additions, roughly in order:

**Wake word ("Hey Cozmo" / whatever you name it).** Use openWakeWord — Python, runs on the Pi, you can train a custom wake word in an afternoon. Eliminates push-to-talk and makes it feel alive.

**Persistent memory.** Append every conversation to a SQLite database; on each new exchange, retrieve relevant past chunks via embeddings and inject into the GPT system prompt. "I remember you told me about your sister Anna" is the single most magical moment in this kind of robot.

**Emotion-aware face tracking.** MediaPipe Face Mesh gives you blendshapes — including smile, eyebrow raise, eye openness. The robot can mirror your mood, or respond to it. Cheap to implement, huge impact.

**Object curiosity.** Hold something up; it looks at it; it asks about it (multimodal GPT call with the camera frame). Implementable in a day once the voice loop works.

**Wake-on-presence.** Idle screen with closed eyes; opens when a face appears. Tiny code change, big "alive" effect.

**Personality / mood state machine.** A simple internal state — energy, mood, attention — that influences GPT's system prompt and eye animations. Not ML really, but it's what makes Cozmo feel like Cozmo.

**Speaker recognition (who is this?).** SpeechBrain has prebuilt models. Lets the robot greet you by name without you logging in.

**Skip these (sound cool, painful to ship):**
- SLAM / autonomous navigation — wrong robot for this
- On-device LLM fine-tuning — buy more Pi RAM and don't bother
- Custom YOLO training — MediaPipe + multimodal GPT covers it
- Gesture recognition — possible but rarely worth the effort vs. just talking to it

---

## 8. Risks & How to Dodge Them

A few things that bite every first-time builder:

**Power instability.** Servos on the Pi 5V rail will reset the Pi the moment two servos move at once. **Always** give servos a separate 5V supply with a common ground to the Pi. Brown-out symptoms look like "everything is broken" but are almost always power.

**SD card death.** Pi SD cards die from too many writes. Move logs and any frequent writes to RAM (`tmpfs`) or use a USB SSD for the brain after a few weeks of dev.

**Camera ribbon orientation.** The Pi 5 uses the smaller CSI connector and the cable can be installed reversed — no damage but it'll just not detect. If `libcamera-hello` shows nothing, try flipping the ribbon.

**WiFi cuts out during demo.** Whisper-API and GPT calls need internet. Always pre-download a local fallback (Piper TTS + faster-whisper-small) before showing the robot to anyone you want to impress.

**Servo jitter when idle.** Either disable PWM when the head reaches the target, or accept a small dead-zone. Constant minor twitching looks bad on video.

**Friend's laptop ≠ Pi.** Code that runs in your friend's macOS Python venv may not run on Pi's ARM64. Set up the Pi as the actual dev target from week 1, even if your friend writes the code on their laptop.

---

## 9. What to do this week

In priority order:

1. Both: agree on the folder layout above and create the GitHub repo today.
2. You: order the parts from the BOM (it's the long-lead item).
3. You: while waiting, start the Blender model of the head/pan-tilt bracket. Don't model the outer case yet — wait until you have the screen in hand to measure.
4. Friend: stand up the Python environment, get `eyes.py` and `vision.py` working on their laptop with the webcam.
5. Both: write the one-page interface contract (the section 3 above is most of it — make it your own).

Once the parts land, you'll be a week from a robot that follows your face, and another two from one you can talk to. That's a great place to be in May.

---

*Good luck — this is one of those projects that's just hard enough to be deeply rewarding and just feasible enough that you'll actually finish it. Build the MVP first; resist the urge to design v2 features into v1.*
