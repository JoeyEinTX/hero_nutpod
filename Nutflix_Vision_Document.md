# Nutflix / NutPod Vision & Architecture Foundation

Purpose: This document defines the long-term vision, architectural principles, naming standards, and phased development strategy for the Nutflix ecosystem. It is intended to serve as a stable reference document that can be handed to any AI coding assistant (Claude Code, Cursor, Copilot, ChatGPT, etc.) to maintain continuity across development sessions.

## 1. Project Vision

Nutflix is a modular wildlife observation and media platform centered around Raspberry Pi-based smart habitat devices.

The long-term vision is:
- Local wildlife observation
- Motion-triggered recording
- Live and historical media access
- Multi-device management
- Community sharing/network features
- Privacy-first operation
- Modular hardware expansion

The system should begin with a single highly reliable device and evolve incrementally into a scalable ecosystem.

The first production-focused device is called Hero.

## 2. Core Product Naming

Canonical naming standards:

Platform:
- Nutflix

Hardware Device Types (current):
- NutPod
- ScoutPod
- GroundPod

Hardware Device Types (future):
- BirdBox
- Others TBD

Enclosure:
- SquirrelBox

Electronics Module:
- NutNode

NutPod camera roles:
- NestCam = interior camera
- CritterCam = exterior camera

Other device types may define their own role names as they are designed (e.g., a BirdBox may use NestCam/PerchCam, a ScoutPod may use directional names). Role names are fixed *per device type*, not globally.

Important:
Hero is NOT a product name.
Hero is the user-defined name of the first device instance.

## 3. Device Philosophy

The project should prioritize:
- Reliability over complexity
- Clarity over cleverness
- Modularity over monolithic design
- Incremental expansion
- Hardware-aware architecture
- Local-first functionality

Every new layer should be added only after the previous layer is stable.

## 4. Current Hardware Foundation

Initial Hero hardware assumptions:

- Raspberry Pi 5
- NVMe storage (recommended; SD card supported but discouraged for sustained writes)
- 2 x IMX708 CSI cameras
- Picamera2 backend
- Local filesystem storage
- Raspberry Pi OS
- Sequential camera operation for reliability

Current camera roles (NutPod):
- NestCam (interior)
- CritterCam (exterior)

## 5. Minimal Camera Foundation (Phase 1)

The first successful milestone is intentionally minimal.

Required functionality:
1. Load config.yaml
2. Initialize NestCam
3. Initialize CritterCam
4. Capture one still image from each
5. Save files locally
6. Log success/failure
7. Shut down cleanly

No dashboard.
No AI.
No motion detection.
No cloud architecture.
No database.

This phase exists to prove the camera pipeline and establish clean architecture foundations.

**Status: complete as of 2026-05-12.**

## 5.2 Motion-Triggered Capture & Clip Recording (Phase 2)

Phase 2 transforms the system from one-shot capture into continuous observation. It introduces motion detection, video clips, heartbeat snapshots, an event database, and retention management.

### Required functionality

1. Run as a long-running systemd service that auto-starts on boot and restarts on failure.
2. Continuously monitor both cameras for motion using a low-resolution sampling stream.
3. On motion detection from a given camera, record a video clip consisting of pre-roll seconds (buffered before the trigger) plus post-roll seconds (after the trigger), plus a full-resolution snapshot from that same camera at trigger time.
4. Capture a heartbeat snapshot from each camera every N minutes (default 15) regardless of motion activity.
5. Log every event — motion or heartbeat — to a SQLite database with the schema defined below.
6. Provide a separate retention script, triggered by a systemd timer (daily), that prunes old media according to configured retention windows.
7. Honor a `keepers/` subdirectory under both `output/snapshots/` and `output/clips/` that the retention script never touches.

### NOT in Phase 2

- No web dashboard or HTTP interface (Phase 3)
- No live streaming (Phase 4+)
- No AI classification or wildlife tagging (Phase 4)
- No cloud sync, remote storage, or networking of any kind (Phase 5)
- No multi-device coordination (Phase 5)

### Capture resolution standards (Phase 2)

| Purpose | Resolution | Framerate | Rationale |
|---------|------------|-----------|-----------|
| Snapshots | 4608×2592 | n/a (still) | Full sensor, no crop; reference-quality stills |
| Clips | 2304×1296 | 30 fps | Smooth playback, full FOV, manageable file size |
| Motion sampling | 1536×864 | 30 fps | Low CPU, sufficient detail for frame deltas |

### Motion detection model

Two configurable thresholds plus a cooldown:

- `pixel_threshold` — per-pixel brightness delta required to count a pixel as "changed."
- `area_threshold_percent` — percentage of the frame's pixels that must cross the pixel threshold to count as motion.
- `cooldown_seconds` — minimum time between consecutive motion triggers per camera (prevents one wandering squirrel from generating 100 events).

A `sensitivity_preset` shortcut (low / medium / high) selects reasonable defaults for the underlying thresholds. The raw thresholds can be overridden explicitly.

### SQLite event schema

A single `events` table:

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | autoincrement |
| timestamp | TEXT | ISO-8601 |
| device_name | TEXT | e.g. "Hero" |
| camera_name | TEXT | e.g. "NestCam" |
| event_type | TEXT | "motion" or "heartbeat" |
| snapshot_path | TEXT | relative path, may be NULL |
| clip_path | TEXT | relative path, may be NULL |
| tags | TEXT | reserved for future classification (Phase 4); empty in Phase 2 |

### Retention policy

| Content | Default window |
|---------|----------------|
| Motion clips | 7 days |
| Motion snapshots | 7 days |
| Heartbeat snapshots | 30 days |
| Log files | Forever (no automatic pruning) |
| SQLite event rows | Forever (no automatic pruning) |

Files inside any `keepers/` subdirectory are exempt from all retention.

### Concurrency policy

Minimal threading is permitted only where required for parallel motion monitoring of both cameras. The recommended approach is one worker thread per camera plus a main thread managing service lifecycle and signal handling. No speculative concurrency, no asyncio, no thread pools beyond what is described.

Sequential operation within a single camera remains the rule: motion sampling, snapshot capture, and clip recording on a given camera never overlap.

### Reference `config.yaml` for Phase 2

```yaml
device:
  name: Hero
  type: NutPod

cameras:
  nestcam:
    port: 0
    role: interior
  crittercam:
    port: 1
    role: exterior

capture:
  snapshot:
    format: jpeg
    resolution: [4608, 2592]
  clip:
    resolution: [2304, 1296]
    framerate: 30
    pre_roll_seconds: 5
    post_roll_seconds: 10
  motion_sampling:
    resolution: [1536, 864]
    framerate: 30

heartbeat:
  interval_minutes: 15

motion:
  sensitivity_preset: medium
  pixel_threshold: 25
  area_threshold_percent: 2.0
  cooldown_seconds: 30

retention:
  clips_days: 7
  snapshots_days: 7
  heartbeats_days: 30
  logs_days: null      # null = never delete
  db_rows_days: null   # null = never delete

paths:
  snapshots: output/snapshots
  clips: output/clips
  database: output/nutflix.db
  logs: logs
  keepers_subdir: keepers
```

This is the authoritative shape. AI assistants implementing Phase 2 must not introduce config keys beyond those listed.

## 6. Folder Structure

Combined structure across Phase 1 and Phase 2. New entries in Phase 2 are noted in the prose summary below.

```
hero_nutpod/
├── main.py
├── service.py
├── retention.py
├── config.yaml
├── cameras/
│   ├── __init__.py
│   ├── camera_device.py
│   └── camera_manager.py
├── motion/
│   ├── __init__.py
│   └── detector.py
├── storage/
│   ├── __init__.py
│   └── event_log.py
├── utils/
│   ├── __init__.py
│   ├── config_loader.py
│   └── logger_setup.py
├── systemd/
│   ├── nutflix.service
│   ├── nutflix-retention.service
│   └── nutflix-retention.timer
├── output/
│   ├── snapshots/
│   │   └── keepers/
│   ├── clips/
│   │   └── keepers/
│   └── nutflix.db
└── logs/
```

Phase 2 additions:
- `service.py` — long-running motion service entry point
- `retention.py` — cleanup script run by systemd timer
- `motion/detector.py` — motion detection logic
- `storage/event_log.py` — SQLite event log interface
- `systemd/*` — unit files for the always-running service and the retention timer/service pair
- `output/*/keepers/` — permanent-save subdirectories exempt from retention
- `output/nutflix.db` — SQLite event log

`main.py` is retained as a one-shot capture utility for testing and diagnostics.

## 7. Architectural Principles

The architecture should remain:
- Beginner-readable
- AI-collaboration friendly
- Modular
- Extensible
- Hardware-conscious

Avoid:
- Premature abstraction
- Over-engineering
- Massive monolithic files
- Framework sprawl
- "Enterprise architecture" before needed

Preferred development style:
- Small vertical slices
- One feature at a time
- Stable foundations before scaling

## 8. Naming Standards

Rules:

1. Product/platform names use PascalCase
2. Internal config keys use lowercase
3. Python class names use PascalCase
4. Python files use lowercase_with_underscores
5. Camera role names remain fixed per device type:
   - NutPod: NestCam, CritterCam

Saved media naming:
`<DeviceName>_<CameraName>_<Timestamp>.<ext>`

Examples:
- `Hero_NestCam_2026-05-12_21-34-35.jpg` (Phase 1 snapshot)
- `Hero_CritterCam_2026-05-12_21-34-35.jpg` (Phase 1 snapshot)
- `Hero_NestCam_2026-05-15_08-12-04.mp4` (Phase 2 motion clip)

Snapshot and clip filenames produced by the same motion event share a timestamp.

## 9. Development Philosophy for AI Assistants

AI assistants working on this project should:
- Prefer simple and maintainable code
- Avoid speculative architecture
- Keep explanations beginner-friendly
- Preserve naming consistency
- Respect phased development
- Avoid adding technologies not requested for the current phase

### Banned across all phases (until explicitly relaxed in a future phase)

- Flask, FastAPI, or any other web framework or HTTP interface (Phase 3 may introduce a lightweight dashboard)
- AI / ML inference (Phase 4)
- Cloud sync, remote storage, or any external networking (Phase 5)
- Distributed systems patterns (Phase 5)

### In scope as of Phase 2

- Motion detection
- SQLite database (single file, in-process; no client-server DBs)
- Minimal threading, only where required for parallel per-camera motion monitoring

The bans list narrows as phases progress. Anything not explicitly in scope for the current phase is out of scope.

## 10. Future Expansion Roadmap

Planned future phases:

Phase 2 (specified in detail in Section 5.2):
- Motion-triggered capture
- Video clip recording with pre/post-roll
- Heartbeat snapshots
- SQLite event log
- Retention management

Phase 3:
- Lightweight local dashboard
- Device health monitoring
- Environmental sensors (BME280)
- Live preview

Phase 4:
- AI classification
- Wildlife tagging
- Event filtering
- Smart notifications

Phase 5:
- Multi-device management
- Nutflix cloud/network architecture
- Shared wildlife feeds
- Community ecosystem

All future phases should grow from the stable foundations established in earlier phases.

## 11. Non-Negotiable Design Goal

The project should always remain understandable by a motivated novice maker.

The system should never evolve into an opaque "magic" architecture that becomes difficult to debug, maintain, or reason about.

Every layer should have a clear purpose.

---

## Document History

| Date | Changes |
|------|---------|
| 2026-05-08 | NutPod/NutNode split clarified (NutPod = device type, NutNode = electronics module). BirdBox added as future device type. Camera role names scoped per device type rather than global. Phase 2+ note added to .mp4 naming example. |
| 2026-05-12 | Phase 1 marked complete. Section 5.2 added with full Phase 2 specification: motion-triggered capture, video clips with pre/post-roll, heartbeat snapshots, SQLite event log, retention policy with keepers exemption, systemd service model. Section 6 folder structure expanded. Section 8 naming examples updated to include clip filename. Section 9 reorganized into permanent bans vs. per-phase scope. NVMe noted as recommended storage in Section 4. |
