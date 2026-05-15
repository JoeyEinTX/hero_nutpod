"""HTTP route handlers for the dashboard (Section 5.3 route plan).

All HTML routes render Jinja2 templates from dashboard/templates/. File
serving uses Flask's send_from_directory with explicit, configured roots
so an attacker can't escape into the rest of the filesystem via a crafted
event id or path.

Mutating routes (/events/<id>/keep, /unkeep) move files between the
default media directory and the keepers/ subdirectory, then update the
events row to point at the new locations.
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from flask import (
    abort, current_app, redirect, render_template, request,
    send_from_directory, url_for,
)


CAMERA_KEYS = ("nestcam", "crittercam")


def register_routes(app):
    @app.route("/")
    def root():
        return redirect(url_for("live"))

    @app.route("/live")
    def live():
        cfg = _cfg()
        return render_template(
            "live.html",
            cameras=CAMERA_KEYS,
            preview_refresh_seconds=cfg["dashboard"]["preview_refresh_seconds"],
            active_page="live",
        )

    @app.route("/events")
    def events_list():
        cfg = _cfg()
        per_page = int(cfg["dashboard"]["events_per_page"])
        page = max(1, _int_arg("page", 1))
        camera_filter = request.args.get("camera") or None
        if camera_filter and camera_filter not in CAMERA_KEYS:
            camera_filter = None

        offset = (page - 1) * per_page
        log = _event_log()
        rows = log.query_events_page(per_page, offset, camera_filter)
        total = log.count_events(camera_filter)
        total_pages = max(1, (total + per_page - 1) // per_page)

        return render_template(
            "events.html",
            events=[_row_to_event(r) for r in rows],
            camera_filter=camera_filter,
            camera_keys=CAMERA_KEYS,
            page=page,
            total_pages=total_pages,
            total=total,
            active_page="events",
        )

    @app.route("/events/<int:event_id>")
    def event_detail(event_id):
        row = _event_log().get_event_by_id(event_id)
        if row is None:
            abort(404)
        event = _row_to_event(row)
        return render_template(
            "event_detail.html",
            event=event,
            active_page="events",
        )

    @app.route("/status")
    def status():
        cfg = _cfg()
        event_log = _event_log()
        sensor_log = _sensor_log()

        latest_heartbeats = {
            key: event_log.latest_heartbeat(_display_name(key))
            for key in CAMERA_KEYS
        }
        latest_sensor = sensor_log.latest_reading()
        ir_state = _read_ir_state(Path(cfg["paths"]["preview"]) / "state.json")
        disk_bytes = _output_disk_usage(Path("output"))
        total_events = event_log.count_events()
        uptime_seconds, uptime_source = _service_uptime_seconds()

        return render_template(
            "status.html",
            device_name=cfg["device"]["name"],
            latest_heartbeats=latest_heartbeats,
            latest_sensor=latest_sensor,
            ir_state=ir_state,
            ir_pins={
                key: cfg["ir_emitter"]["cameras"][key]["gpio_pin"]
                for key in CAMERA_KEYS
            },
            disk_bytes=disk_bytes,
            total_events=total_events,
            uptime_seconds=uptime_seconds,
            uptime_source=uptime_source,
            sensor_enabled=cfg["sensors"]["bme280"]["enabled"],
            ir_enabled=cfg["ir_emitter"]["enabled"],
            active_page="status",
        )

    @app.route("/preview/<camera_name>")
    def preview(camera_name):
        cfg = _cfg()
        if camera_name not in CAMERA_KEYS:
            abort(404)
        preview_dir = Path(cfg["paths"]["preview"]).resolve()
        filename = f"{camera_name}.jpg"
        if not (preview_dir / filename).exists():
            abort(404)
        # No-store so every refresh shows the latest frame even when the
        # browser would otherwise cache the JPEG.
        response = send_from_directory(str(preview_dir), filename)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/snapshot/<int:event_id>")
    def snapshot(event_id):
        return _serve_event_file(event_id, "snapshot")

    @app.route("/clip/<int:event_id>")
    def clip(event_id):
        return _serve_event_file(event_id, "clip")

    @app.route("/events/<int:event_id>/keep", methods=["POST"])
    def keep(event_id):
        _move_event_files(event_id, to_keepers=True)
        return _redirect_back(event_id)

    @app.route("/events/<int:event_id>/unkeep", methods=["POST"])
    def unkeep(event_id):
        _move_event_files(event_id, to_keepers=False)
        return _redirect_back(event_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg():
    return current_app.config["NUTFLIX_CONFIG"]


def _event_log():
    return current_app.config["NUTFLIX_EVENT_LOG"]


def _sensor_log():
    return current_app.config["NUTFLIX_SENSOR_LOG"]


def _logger():
    return current_app.config["NUTFLIX_LOGGER"]


def _int_arg(name, default):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _display_name(camera_key):
    return {"nestcam": "NestCam", "crittercam": "CritterCam"}[camera_key]


def _row_to_event(row):
    """Map a DB row tuple into a dict the templates consume."""
    snapshot_path = row[5]
    clip_path = row[6]
    keepers_subdir = _cfg()["paths"]["keepers_subdir"]
    is_keeper = (snapshot_path and f"/{keepers_subdir}/" in snapshot_path) or (
        clip_path and f"/{keepers_subdir}/" in clip_path
    )
    return {
        "id": row[0],
        "timestamp": row[1],
        "device_name": row[2],
        "camera_name": row[3],
        "event_type": row[4],
        "snapshot_path": snapshot_path,
        "clip_path": clip_path,
        "tags": row[7],
        "is_keeper": is_keeper,
    }


def _serve_event_file(event_id, kind):
    row = _event_log().get_event_by_id(event_id)
    if row is None:
        abort(404)
    path_str = row[5] if kind == "snapshot" else row[6]
    if not path_str:
        abort(404)

    cfg = _cfg()
    if kind == "snapshot":
        allowed_roots = [Path(cfg["paths"]["snapshots"]).resolve()]
    else:
        allowed_roots = [Path(cfg["paths"]["clips"]).resolve()]

    target = Path(path_str).resolve()
    if not target.exists():
        abort(404)
    for root in allowed_roots:
        try:
            target.relative_to(root)
        except ValueError:
            continue
        return send_from_directory(str(target.parent), target.name)
    abort(404)


def _move_event_files(event_id, to_keepers):
    """Move the snapshot and clip into keepers/ (or back out). Update the
    events row to point at the new locations. Missing files are logged and
    skipped — keep should not 500 if a file is already gone."""
    row = _event_log().get_event_by_id(event_id)
    if row is None:
        abort(404)
    logger = _logger()
    cfg = _cfg()
    keepers_subdir = cfg["paths"]["keepers_subdir"]

    new_snapshot = _move_one(row[5], keepers_subdir, to_keepers, logger)
    new_clip = _move_one(row[6], keepers_subdir, to_keepers, logger)
    _event_log().update_paths(event_id, new_snapshot, new_clip)


def _move_one(path_str, keepers_subdir, to_keepers, logger):
    """Move one file into / out of its parent's keepers/ subdir.

    Returns the new relative-path string for the DB (with forward slashes),
    or None if path_str was already None. If the file doesn't exist on disk,
    still rewrites the stored path so a subsequent unkeep can locate it once
    the file is restored — but logs the missing file.
    """
    if not path_str:
        return None
    src = Path(path_str)
    if to_keepers:
        # output/snapshots/foo.jpg -> output/snapshots/keepers/foo.jpg
        if src.parent.name == keepers_subdir:
            return path_str  # already a keeper
        dst = src.parent / keepers_subdir / src.name
    else:
        # output/snapshots/keepers/foo.jpg -> output/snapshots/foo.jpg
        if src.parent.name != keepers_subdir:
            return path_str  # not a keeper, nothing to do
        dst = src.parent.parent / src.name

    new_path_str = str(dst).replace("\\", "/")
    dst.parent.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        logger.warning(
            f"keeper move: source {src} missing; updating DB path anyway"
        )
        return new_path_str

    try:
        shutil.move(str(src), str(dst))
        logger.info(f"keeper move: {src} -> {dst}")
    except OSError as e:
        logger.error(f"keeper move failed for {src}: {e}")
        return path_str
    return new_path_str


def _redirect_back(event_id):
    referrer = request.referrer
    if referrer:
        return redirect(referrer)
    return redirect(url_for("event_detail", event_id=event_id))


def _read_ir_state(state_path):
    """Read the shared IR state file written by the motion service.

    Missing file means the motion service hasn't started yet, or IR is
    disabled — both render as "unknown" in the template.
    """
    try:
        return json.loads(state_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _output_disk_usage(root):
    if not root.exists():
        return 0
    total = 0
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return total


def _service_uptime_seconds():
    """Return (seconds, source) where source describes how we measured.

    Prefer systemctl for nutflix.service's ActiveEnterTimestamp. If
    unavailable, walk /proc for the service.py process and use its
    start_time. If neither works, return (None, "unavailable").
    """
    seconds = _systemctl_uptime("nutflix.service")
    if seconds is not None:
        return seconds, "systemd"
    seconds = _proc_uptime_for("service.py")
    if seconds is not None:
        return seconds, "/proc"
    return None, "unavailable"


def _systemctl_uptime(unit):
    try:
        out = subprocess.run(
            ["systemctl", "show", unit, "--property=ActiveEnterTimestampMonotonic"],
            capture_output=True, text=True, check=True, timeout=2.0,
        ).stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None
    if "=" not in out:
        return None
    _, _, value = out.partition("=")
    try:
        active_us = int(value)
    except ValueError:
        return None
    if active_us == 0:
        return None
    # ActiveEnterTimestampMonotonic is microseconds since boot; compare to
    # /proc/uptime which is seconds since boot.
    try:
        with open("/proc/uptime") as f:
            now_s = float(f.read().split()[0])
    except OSError:
        return None
    return max(0.0, now_s - (active_us / 1_000_000.0))


def _proc_uptime_for(script_name):
    """Best-effort: find a python3 process whose cmdline mentions script_name
    and compute its uptime from /proc/<pid>/stat."""
    try:
        clock_ticks = os.sysconf("SC_CLK_TCK")
        with open("/proc/uptime") as f:
            system_uptime_s = float(f.read().split()[0])
    except (OSError, ValueError, AttributeError):
        return None

    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as f:
                cmdline = f.read().decode("utf-8", errors="ignore")
        except OSError:
            continue
        if script_name not in cmdline:
            continue
        try:
            with open(f"/proc/{entry}/stat") as f:
                stat = f.read()
        except OSError:
            continue
        # /proc/<pid>/stat field 22 is starttime in clock ticks since boot.
        # comm (field 2) is parenthesized and may contain spaces, so split
        # from the right end of the comm field.
        rparen = stat.rfind(")")
        if rparen < 0:
            continue
        fields = stat[rparen + 2:].split()
        if len(fields) < 20:
            continue
        try:
            starttime_ticks = int(fields[19])
        except ValueError:
            continue
        process_start_s = starttime_ticks / clock_ticks
        return max(0.0, system_uptime_s - process_start_s)
    return None
