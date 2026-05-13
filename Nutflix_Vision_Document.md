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

## 6. Initial Folder Structure

hero_nutpod/
├── main.py
├── config.yaml
├── cameras/
│   ├── __init__.py
│   ├── camera_device.py
│   └── camera_manager.py
├── utils/
│   ├── __init__.py
│   ├── config_loader.py
│   └── logger_setup.py
├── output/
│   ├── snapshots/
│   └── clips/
└── logs/

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
<DeviceName>_<CameraName>_<Timestamp>.<ext>

Examples:
Hero_NestCam_2026-05-08_18-30-00.jpg
Hero_CritterCam_2026-05-08_18-30-00.mp4   (Phase 2+; video is not produced in Phase 1)

## 9. Development Philosophy for AI Assistants

AI assistants working on this project should:
- Prefer simple and maintainable code
- Avoid speculative architecture
- Keep explanations beginner-friendly
- Preserve naming consistency
- Respect phased development
- Avoid adding technologies not requested

AI assistants should not spontaneously add:
- Flask/FastAPI dashboards
- Motion systems
- AI inference
- Databases
- Multi-threading
- Cloud sync
- Distributed systems

…unless specifically requested for the current phase.

## 10. Future Expansion Roadmap

Planned future phases may include:

Phase 2:
- Video recording
- Motion detection
- Clip management
- Event logging

Phase 3:
- Lightweight dashboard
- Device health monitoring
- Environmental sensors
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

All future phases should grow from the stable camera foundation established in Phase 1.

## 11. Non-Negotiable Design Goal

The project should always remain understandable by a motivated novice maker.

The system should never evolve into an opaque "magic" architecture that becomes difficult to debug, maintain, or reason about.

Every layer should have a clear purpose.

---

## Document History

| Date | Changes |
|------|---------|
| 2026-05-08 | NutPod/NutNode split clarified (NutPod = device type, NutNode = electronics module). BirdBox added as future device type. Camera role names scoped per device type rather than global. Phase 2+ note added to .mp4 naming example. |
