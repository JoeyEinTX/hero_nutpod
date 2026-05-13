"""Hero NutPod long-running motion service.

Loads config, sets up logging, opens the SQLite event log, spawns one worker
thread per camera, and waits for SIGTERM/SIGINT to shut down cleanly. Designed
to run under systemd (see systemd/nutflix.service) but also runnable directly
in the foreground for testing:

    python3 service.py
"""
import signal
import threading
from pathlib import Path

from cameras.camera_manager import build_workers
from storage.event_log import EventLog
from utils.config_loader import load_config, resolve_motion_thresholds
from utils.logger_setup import setup_logging


def main():
    config_path = Path(__file__).parent / "config.yaml"
    config = load_config(config_path)

    logger = setup_logging(Path(config["paths"]["logs"]))
    _log_startup_summary(config, logger)

    db_path = Path(config["paths"]["database"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    event_log = EventLog(db_path)

    stop_event = threading.Event()
    _install_signal_handlers(stop_event, logger)

    workers = build_workers(config, event_log, stop_event, logger)
    for worker in workers:
        worker.start()

    logger.info(f"Service running with {len(workers)} camera worker(s)")

    # Main thread blocks here until a signal flips the stop_event. Worker
    # threads are daemons so we still join them explicitly to give each
    # camera a chance to release the Picamera2 hardware cleanly.
    try:
        while not stop_event.is_set():
            stop_event.wait(1.0)
    finally:
        logger.info("Shutdown requested; joining camera workers")
        for worker in workers:
            worker.join(timeout=30.0)
        event_log.close()
        logger.info("Service stopped")


def _install_signal_handlers(stop_event, logger):
    def _handler(signum, _frame):
        logger.info(f"Received signal {signum}; initiating shutdown")
        stop_event.set()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def _log_startup_summary(config, logger):
    """Log the running configuration so the operator can confirm it from
    the first lines of the journal."""
    device_name = config["device"]["name"]
    cameras = list(config["cameras"].keys())
    pixel_threshold, area_threshold_percent = resolve_motion_thresholds(config)
    motion = config["motion"]
    retention = config["retention"]

    logger.info(f"Hero NutPod motion service starting (device={device_name})")
    logger.info(f"Cameras configured: {cameras}")
    logger.info(
        f"Motion thresholds: preset={motion.get('sensitivity_preset')} "
        f"pixel_threshold={pixel_threshold} "
        f"area_threshold_percent={area_threshold_percent} "
        f"cooldown_seconds={motion['cooldown_seconds']}"
    )
    logger.info(
        f"Heartbeat interval: {config['heartbeat']['interval_minutes']} min"
    )
    logger.info(
        f"Retention windows: clips={retention['clips_days']}d "
        f"snapshots={retention['snapshots_days']}d "
        f"heartbeats={retention['heartbeats_days']}d "
        f"logs={retention['logs_days']} db_rows={retention['db_rows_days']}"
    )


if __name__ == "__main__":
    main()
