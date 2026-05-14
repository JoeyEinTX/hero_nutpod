"""Retention cleanup script.

Reads retention windows from config.yaml and prunes:

  - clips older than retention.clips_days from output/clips/
  - motion snapshots older than retention.snapshots_days from output/snapshots/
  - heartbeat snapshots older than retention.heartbeats_days from
    output/snapshots/

Snapshot type is looked up in the SQLite event log so the two retention
windows can be applied. Files inside any `keepers/` subdirectory are exempt.

Idempotent: safe to run any time, including immediately after a previous run.
Deletes are logged. Designed to be invoked by systemd timer
(systemd/nutflix-retention.timer) but runnable manually:

    python3 retention.py
"""
import time
from pathlib import Path

from storage.event_log import EventLog
from utils.config_loader import load_config
from utils.logger_setup import setup_logging


def main():
    config_path = Path(__file__).parent / "config.yaml"
    config = load_config(config_path)

    logger = setup_logging(Path(config["paths"]["logs"]))
    logger.info("Retention cleanup starting")

    retention = config["retention"]
    clips_dir = Path(config["paths"]["clips"])
    snapshots_dir = Path(config["paths"]["snapshots"])
    keepers_subdir = config["paths"]["keepers_subdir"]
    db_path = Path(config["paths"]["database"])

    event_log = EventLog(db_path) if db_path.exists() else None

    try:
        deleted_clips = _prune_clips(
            clips_dir, retention["clips_days"], keepers_subdir, logger
        )
        deleted_snaps = _prune_snapshots(
            snapshots_dir,
            retention["snapshots_days"],
            retention["heartbeats_days"],
            keepers_subdir,
            event_log,
            logger,
        )
    finally:
        if event_log is not None:
            event_log.close()

    logger.info(
        f"Retention cleanup complete: "
        f"deleted {deleted_clips} clip(s), {deleted_snaps} snapshot(s)"
    )


def _prune_clips(clips_dir, max_age_days, keepers_subdir, logger):
    if max_age_days is None or not clips_dir.exists():
        return 0

    cutoff = _cutoff_seconds(max_age_days)
    deleted = 0
    for path in clips_dir.iterdir():
        if not path.is_file():
            continue
        if _is_in_keepers(path, clips_dir, keepers_subdir):
            continue
        if path.stat().st_mtime < cutoff:
            _delete(path, "clip", logger)
            deleted += 1
    return deleted


def _prune_snapshots(snapshots_dir, motion_days, heartbeat_days,
                     keepers_subdir, event_log, logger):
    if not snapshots_dir.exists():
        return 0

    motion_cutoff = (
        _cutoff_seconds(motion_days) if motion_days is not None else None
    )
    heartbeat_cutoff = (
        _cutoff_seconds(heartbeat_days) if heartbeat_days is not None else None
    )

    deleted = 0
    for path in snapshots_dir.iterdir():
        if not path.is_file():
            continue
        if _is_in_keepers(path, snapshots_dir, keepers_subdir):
            continue

        rel_path = str(path).replace("\\", "/")
        event_type = (
            event_log.event_type_for_snapshot(rel_path)
            if event_log is not None
            else None
        )

        # Pick the cutoff for this file. Orphans (no DB row) fall back to the
        # motion-snapshot window — the shorter of the two, which is the safer
        # default for unknown files.
        if event_type == "heartbeat":
            cutoff = heartbeat_cutoff
            label = "heartbeat snapshot"
        else:
            cutoff = motion_cutoff
            label = "motion snapshot" if event_type == "motion" else "snapshot (orphan)"

        if cutoff is None:
            continue
        if path.stat().st_mtime < cutoff:
            _delete(path, label, logger)
            deleted += 1
    return deleted


def _cutoff_seconds(max_age_days):
    return time.time() - (max_age_days * 86400)


def _is_in_keepers(path, root, keepers_subdir):
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return keepers_subdir in relative.parts


def _delete(path, label, logger):
    try:
        path.unlink()
        logger.info(f"Deleted {label}: {path}")
    except OSError as e:
        logger.error(f"Failed to delete {path}: {e}")


if __name__ == "__main__":
    main()
