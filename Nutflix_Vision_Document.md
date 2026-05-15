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
- 2 x IMX708 CSI cameras (NoIR)
- Picamera2 backend
- Local filesystem storage
- Raspberry Pi OS
- Sequential camera operation for reliability

Phase 3 hardware additions:
- BME280 environmental sensor (temperature, humidity, pressure) via I2C
- 2 x IR LED emitter boards (Adafruit 940nm or equivalent), one per camera, GPIO-controlled

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

This is the authoritative shape for Phase 2. Phase 3 extends it with new top-level blocks (see Section 5.3) but does not modify existing keys.

**Status: complete as of 2026-05-13.**

## 5.3 Local Dashboard, Environmental Sensors & IR Illumination (Phase 3)

Phase 3 makes the system observable. It adds a local web dashboard, environmental sensing via BME280, and infrared illumination for nighttime capture. All three share a hardware-to-software interface layer and a presentation layer, which is why they are scoped as one phase rather than three.

Phase 3 also relaxes the most consequential ban so far: HTTP / web framework code becomes in-scope. To preserve the architectural discipline that has carried Phases 1 and 2, the dashboard runs as a *separate process* from the motion service. The motion service is critical-path and must not depend on or be destabilized by the dashboard.

### Required functionality

**Dashboard:**
1. Run as a separate long-running systemd service alongside the motion service. Dashboard failures must not affect motion service operation.
2. Serve an HTML interface on the LAN (no authentication; localhost or LAN access only — see Security boundary below).
3. Provide three primary views:
   - **Live** — current camera previews for NestCam and CritterCam, refreshed via simple `<img>` tag reload at the configured `preview_refresh_seconds` interval.
   - **Events** — chronological list of recent events (motion + heartbeat) with thumbnail, timestamp, camera name, and clip play link. Paginated. One filter: by camera (NestCam only / CritterCam only / both).
   - **Status** — system health: service uptime, last heartbeat per camera, latest sensor readings, IR emitter state per camera, disk usage, total event count.
4. Allow marking any event's media file(s) as "keepers" via a UI control. Moves the file(s) into the appropriate `keepers/` subdirectory.
5. Read-only access to clips via standard HTTP file serving (browser playback of `.mp4`).

**Sensors:**
6. Poll the BME280 at `poll_interval_seconds` (default 300 = every 5 min). Store each reading as a row in a new `sensor_readings` table.
7. Sensor polling runs as a worker inside the motion service process (it shares the same hardware-access constraints).
8. If the BME280 is absent or fails to initialize, log a warning and continue running. Sensor failures must not affect motion or dashboard operation.

**IR Illumination:**
9. Monitor scene brightness continuously from each camera's motion-sampling stream (free — uses the frames already being captured).
10. When average frame brightness drops below `brightness_threshold` for `threshold_smoothing_seconds`, switch that camera's IR emitter GPIO HIGH. When brightness rises back above the threshold for the same smoothing window, switch the GPIO LOW.
11. IR emitter state is per-camera (each camera has its own GPIO pin and its own brightness reading).
12. If GPIO is unavailable or `ir_emitter.enabled` is false, log and skip silently.

### NOT in Phase 3

- No live video streaming (MJPEG, HLS, WebSocket, etc.). Preview is still-image refresh only.
- No authentication, user accounts, or password protection (Phase 5 when the platform layer is built).
- No remote access, port forwarding, or cloud sync (Phase 5).
- No AI classification or wildlife identification (Phase 4).
- No WebSocket connections, server-sent events, or any real-time push from server to browser. Refreshes are client-initiated.
- No Flask-SocketIO, Flask-Login, Flask-SQLAlchemy, or other Flask extensions beyond the base framework. Stdlib `sqlite3` continues to handle persistence.

### Security boundary

The dashboard has no authentication by design (per the local-first principle). Operators must:

- Bind the dashboard to LAN-accessible addresses only (`host: 0.0.0.0` is acceptable on trusted home networks; `host: 127.0.0.1` plus SSH tunneling is recommended otherwise).
- Never expose the dashboard port to the public internet via port forwarding, UPnP, or reverse proxy.
- Treat the LAN as a trust boundary. Any device with network access to the Pi can view all footage and toggle keepers.

The README must restate these requirements explicitly.

### Live preview frame source

The dashboard does not open its own Picamera2 instance (which would conflict with the motion service). Instead, each `CameraWorker` in the motion service writes its current grayscale lores frame to `output/preview/{camera_name}.jpg` every `preview_refresh_seconds` seconds. The dashboard serves these files via a standard route.

Preview frames are:
- **Grayscale** (the Y plane of the lores YUV stream, converted directly to JPEG via PIL). This honestly represents what the motion detector sees.
- **Overwritten in place** (no history retained for previews).
- **Excluded from retention** (the retention script does not scan `output/preview/`).
- **Excluded from version control** (added to `.gitignore`).

Preview file path is fixed: `output/preview/{display_name}.jpg`. The dashboard route `/preview/{camera_name}` returns the corresponding file with appropriate cache headers (`Cache-Control: no-store`) so browser refresh always shows the latest frame.

### Dashboard route plan

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Redirect to `/live` |
| GET | `/live` | Live view page |
| GET | `/events` | Event list (paginated, optional `?camera=` filter) |
| GET | `/events/<id>` | Single event detail page with embedded clip player |
| GET | `/status` | System status page |
| GET | `/preview/<camera_name>` | Latest preview frame (JPEG) |
| GET | `/snapshot/<id>` | Event snapshot file (JPEG) |
| GET | `/clip/<id>` | Event clip file (MP4) |
| POST | `/events/<id>/keep` | Move event's snapshot + clip to keepers/ |
| POST | `/events/<id>/unkeep` | Move event's snapshot + clip back out of keepers/ |

All routes return HTML except for the file-serving routes and POSTs (which redirect back to the referrer after action).

### BME280 protocol and driver

The BME280 is a Bosch I2C sensor at address `0x76` or `0x77` (board-dependent). It produces 16-bit + 20-bit raw readings that require calibration via factory-programmed coefficients read from the chip itself.

**Driver implementation:** an in-repo `sensors/bme280.py` using stdlib `smbus2` (apt: `python3-smbus2`). No external Adafruit / circuit-python dependency. ~80 lines including calibration math from the Bosch datasheet. This keeps Phase 3 dependency-clean and matches the Phase 1/2 philosophy of minimal external libraries.

**Where BME280 lives physically:** inside the SquirrelBox enclosure. Dashboard labels for the reading should make this clear ("Enclosure: 72°F / 45% RH") so the operator understands it is not outdoor weather data.

### IR emitter control

Each Adafruit 940nm IR emitter board takes three connections to the Pi:

| Board Pin | Pi Pin | Notes |
|-----------|--------|-------|
| V+ | 3.3V or 5V rail | 5V brighter, 3.3V safer |
| GND | GND rail | |
| In | A GPIO pin | Driven HIGH to emit |

Configuration assigns one GPIO pin per camera. The Pi 5's BCM GPIO numbering is used throughout.

The brightness-detection algorithm: each `CameraWorker` maintains a rolling average of mean frame brightness (the mean of the Y plane). When the smoothed average crosses `brightness_threshold` (downward or upward) and stays there for `threshold_smoothing_seconds`, the IR GPIO is toggled. The smoothing prevents thrashing from clouds passing or a porch light flickering.

**Library:** `gpiozero` (apt: `python3-gpiozero`, preinstalled on Pi OS). Use `DigitalOutputDevice` for clean on/off semantics. RPi.GPIO is also acceptable but `gpiozero` has a friendlier API for this use case.

### SQLite schema additions

A new table alongside the existing `events` table. Both live in the same `nutflix.db` file:

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PRIMARY KEY | autoincrement |
| timestamp | TEXT | ISO-8601 |
| device_name | TEXT | e.g. "Hero" |
| temperature_c | REAL | nullable |
| humidity_percent | REAL | nullable |
| pressure_hpa | REAL | nullable |

Reading values are nullable because a partial sensor failure may produce only some of the three. NULL is the explicit "we don't know" signal.

Two processes (motion service and dashboard) accessing the same SQLite file is safe — SQLite handles concurrent access via filesystem locking. Each process opens its own connection.

### Retention policy additions

| Content | Default window |
|---------|----------------|
| Sensor readings | Forever (no automatic pruning) |
| Preview frames | n/a (overwritten in place, no accumulation) |

Sensor readings are tiny (~50 bytes per row, ~288 rows/day at 5-min polling = ~14KB/day). No retention pressure for years.

### Concurrency policy (Phase 3)

The motion service process retains its Phase 2 model: one worker thread per camera, plus a main thread. Phase 3 adds:

- **Sensor polling thread** inside the motion service. Wakes every `poll_interval_seconds`, reads BME280, writes a row, sleeps. One thread total (the BME280 is one device, not per-camera).
- **Brightness monitoring** runs inside each existing `CameraWorker`. No new threads. It's a few extra lines added to the motion tick.
- **IR emitter toggling** runs inside each `CameraWorker`. No new threads. Driven by the brightness monitor's output.

The dashboard process is a *separate Python process* started by its own systemd unit. It runs single-threaded Flask development server in production (gunicorn is not required at this scale — one user, low request rate). No threading inside the dashboard process either.

### Reference `config.yaml` additions for Phase 3

The Phase 2 reference config remains unchanged. Phase 3 appends three new top-level blocks and one addition to `paths`:

```yaml
dashboard:
  host: 0.0.0.0
  port: 8080
  preview_refresh_seconds: 2
  events_per_page: 50

sensors:
  bme280:
    enabled: true
    i2c_address: 0x76
    poll_interval_seconds: 300

ir_emitter:
  enabled: true
  brightness_threshold: 50
  threshold_smoothing_seconds: 30
  cameras:
    nestcam:
      gpio_pin: 17
    crittercam:
      gpio_pin: 27

paths:
  # ... existing keys preserved ...
  preview: output/preview
```

This is the authoritative shape. AI assistants implementing Phase 3 must not introduce config keys beyond those listed.

### Visual design language for the dashboard

Phase 3 borrows the Nutflix brand's design system without recreating the marketing site:

- **Color palette:** cream background (~`#FAF3E4`), warm browns (~`#8A4B2A`), olive greens (~`#6B7F3A`, `#4E5E29`), near-black text (~`#2B1D14`). Saturated earth tones, not muddy nature-doc tones.
- **Typography:** system sans-serif stack with Helvetica Neue / Helvetica / Arial fallbacks. Heavy weights (700–900) for headings, normal (400) for body. Negative letter-spacing on large headlines for the brand wordmark.
- **Voice:** dry, confident, slightly playful, never twee. "Latest events" not "Wildlife observations"; "Mark as keeper" not "Save permanently to favorites archive."
- **Layout:** dense and information-rich is acceptable. This is an operator tool, not a marketing page. Prioritize legibility and quick scanning over visual flourish.

A minimal `dashboard/static/style.css` codifies these tokens. No CSS framework (no Bootstrap, no Tailwind). Hand-written CSS that any future maintainer can read and edit in one sitting.

### Migration from Phase 2

Phase 3 does not break Phase 2. The motion service continues to operate identically. Three additive code changes touch Phase 2 files:

- `service.py` — spawns a sensor polling thread on startup, joins it on shutdown. Skips gracefully if `sensors.bme280.enabled` is false or the BME280 is absent.
- `cameras/camera_manager.py` — `CameraWorker` gains a brightness monitor, a preview-frame writer, and an IR emitter handle. All additive. Existing motion / heartbeat / clip logic is unchanged.
- `config.yaml` — adds the three new blocks plus the `preview` path.

The existing `nutflix.service` systemd unit continues to point at `service.py`. A new `nutflix-dashboard.service` unit is added for the dashboard process. Both are enabled and started independently.

## 6. Folder Structure

Combined structure across Phase 1, Phase 2, and Phase 3. Phase 3 additions are noted in the prose summary below.

```
hero_nutpod/
├── main.py
├── service.py
├── retention.py
├── dashboard.py
├── config.yaml
├── cameras/
│   ├── __init__.py
│   ├── camera_device.py
│   └── camera_manager.py
├── motion/
│   ├── __init__.py
│   └── detector.py
├── sensors/
│   ├── __init__.py
│   ├── bme280.py
│   └── brightness.py
├── ir/
│   ├── __init__.py
│   └── emitter.py
├── storage/
│   ├── __init__.py
│   ├── event_log.py
│   └── sensor_log.py
├── dashboard/
│   ├── __init__.py
│   ├── app.py
│   ├── routes.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── live.html
│   │   ├── events.html
│   │   ├── event_detail.html
│   │   └── status.html
│   └── static/
│       ├── style.css
│       └── nutflix.svg
├── utils/
│   ├── __init__.py
│   ├── config_loader.py
│   └── logger_setup.py
├── systemd/
│   ├── nutflix.service
│   ├── nutflix-retention.service
│   ├── nutflix-retention.timer
│   └── nutflix-dashboard.service
├── output/
│   ├── snapshots/
│   │   └── keepers/
│   ├── clips/
│   │   └── keepers/
│   ├── preview/
│   └── nutflix.db
└── logs/
```

Phase 3 additions:
- `dashboard.py` — dashboard process entry point (starts the Flask app)
- `dashboard/` — Flask app, routes, templates, static assets
- `sensors/bme280.py` — in-repo BME280 driver via smbus2
- `sensors/brightness.py` — frame-brightness monitoring for IR control decisions
- `ir/emitter.py` — GPIO control for the IR LED boards
- `storage/sensor_log.py` — SQLite interface for the `sensor_readings` table
- `systemd/nutflix-dashboard.service` — long-running unit for the dashboard process
- `output/preview/` — ephemeral preview frames (overwritten every 2s, gitignored)

`main.py` is still retained as a one-shot capture utility for testing and diagnostics.

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
6. Dashboard route paths are lowercase, hyphenated where multi-word (`/events`, `/event-detail` if needed). No trailing slashes.
7. HTML template files use lowercase_with_underscores and `.html` extension.

Saved media naming:
`<DeviceName>_<CameraName>_<Timestamp>.<ext>`

Examples:
- `Hero_NestCam_2026-05-12_21-34-35.jpg` (Phase 1 snapshot)
- `Hero_CritterCam_2026-05-12_21-34-35.jpg` (Phase 1 snapshot)
- `Hero_NestCam_2026-05-15_08-12-04.mp4` (Phase 2 motion clip)

Preview frame naming (Phase 3, no timestamp because it's overwritten in place):
- `nestcam.jpg`
- `crittercam.jpg`

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

- AI / ML inference (Phase 4)
- Cloud sync, remote storage, or external networking (Phase 5)
- Distributed systems patterns (Phase 5)
- Flask extensions beyond base Flask: Flask-SocketIO, Flask-SQLAlchemy, Flask-Login, etc. (Phase 5 may revisit if user accounts are needed)
- Real-time push from server to client: WebSockets, Server-Sent Events, long polling (Phase 4+ if ever needed)
- Frontend frameworks: React, Vue, Svelte, etc. The dashboard is server-rendered HTML with minimal vanilla JS.
- CSS frameworks: Bootstrap, Tailwind, Bulma, etc. The dashboard uses hand-written CSS.

### In scope as of Phase 2

- Motion detection
- SQLite database (single file, in-process; no client-server DBs)
- Minimal threading, only where required for parallel per-camera motion monitoring

### In scope as of Phase 3

- Flask (base framework only, no SocketIO, no async)
- HTTP serving on the local network (no external exposure)
- GPIO output via gpiozero
- I2C sensor reading via smbus2
- A small amount of vanilla JavaScript for dashboard interactivity (form submissions, image refresh timers). No JS frameworks, no transpilation, no build step.
- Hand-written CSS

The bans list narrows as phases progress. Anything not explicitly in scope for the current phase is out of scope.

## 10. Future Expansion Roadmap

Planned future phases:

Phase 2 (Section 5.2):
- Motion-triggered capture
- Video clip recording with pre/post-roll
- Heartbeat snapshots
- SQLite event log
- Retention management

Phase 3 (Section 5.3):
- Local Flask dashboard
- BME280 environmental sensing
- IR illumination for nighttime capture
- Brightness-aware IR control
- Keeper marking via UI

Phase 4:
- AI classification
- Wildlife tagging
- Event filtering by species
- Smart notifications
- MJPEG / live video streaming (if useful by then)

Phase 5:
- Multi-device management
- Nutflix cloud/network architecture
- User accounts and authentication
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
| 2026-05-14 | Phase 2 marked complete. Section 5.3 added with full Phase 3 specification: local Flask dashboard (separate process, no auth, LAN-only), BME280 environmental sensing via in-repo smbus2 driver, IR illumination via Adafruit 940nm boards with brightness-aware GPIO toggling, preview-frame architecture for live view, sensor_readings SQLite table, keeper marking via UI. Section 4 lists Phase 3 hardware additions (BME280, IR emitters). Section 6 folder structure expanded. Section 8 adds rules for dashboard route and template naming. Section 9 relaxes for Flask + GPIO + I2C in scope, explicitly bans Flask extensions and real-time push. Section 10 Phase 3 entry now points to 5.3. |
