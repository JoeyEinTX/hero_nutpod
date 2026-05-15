"""Hero NutPod long-running motion service.

Loads config, sets up logging, opens the SQLite event log, spawns one worker
thread per camera, and waits for SIGTERM/SIGINT to shut down cleanly. Designed
to run under systemd (see systemd/nutflix.service) but also runnable directly
in the foreground for testing:

    python3 service.py

Phase 3 additions: spawns one extra thread that polls the BME280 sensor every
sensors.bme280.poll_interval_seconds. Sensor failures are logged and skipped
rather than crashing the service. Camera workers gain brightness monitoring
and IR emitter control wired up via build_workers.
"""
import signal
import threading
import time
from pathlib import Path

from cameras.camera_manager import build_workers
from storage.event_log import EventLog
from storage.sensor_log import SensorLog
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
    sensor_log = SensorLog(db_path)

    stop_event = threading.Event()
    _install_signal_handlers(stop_event, logger)

    workers = build_workers(config, event_log, stop_event, logger)
    for worker in workers:
        worker.start()

    sensor_thread = _maybe_start_sensor_thread(
        config, sensor_log, stop_event, logger
    )

    extra = " plus sensor polling" if sensor_thread else ""
    logger.info(
        f"Service running with {len(workers)} camera worker(s){extra}"
    )

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
        if sensor_thread is not None:
            sensor_thread.join(timeout=10.0)
        event_log.close()
        sensor_log.close()
        logger.info("Service stopped")


def _install_signal_handlers(stop_event, logger):
    def _handler(signum, _frame):
        logger.info(f"Received signal {signum}; initiating shutdown")
        stop_event.set()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def _maybe_start_sensor_thread(config, sensor_log, stop_event, logger):
    """Start one BME280 polling thread if enabled and the sensor initializes.

    Returns the started Thread, or None if sensor polling is disabled or the
    sensor is not present. Sensor failures must not crash the service.
    """
    bme_cfg = config["sensors"]["bme280"]
    if not bme_cfg.get("enabled", False):
        logger.info("BME280 polling disabled by config")
        return None

    try:
        from sensors.bme280 import BME280
        sensor = BME280(i2c_bus=1, i2c_address=bme_cfg["i2c_address"])
    except Exception as e:
        logger.warning(
            f"BME280 init failed ({e}); continuing without sensor polling"
        )
        return None

    device_name = config["device"]["name"]
    interval = float(bme_cfg["poll_interval_seconds"])

    def _poll_loop():
        logger.info(
            f"BME280 polling thread started (interval={interval}s)"
        )
        try:
            while not stop_event.is_set():
                try:
                    t_c, h_pct, p_hpa = sensor.read()
                    sensor_log.insert_reading(
                        device_name=device_name,
                        temperature_c=t_c,
                        humidity_percent=h_pct,
                        pressure_hpa=p_hpa,
                    )
                except Exception as exc:
                    logger.warning(f"BME280 read failed: {exc}")
                stop_event.wait(interval)
        finally:
            sensor.close()
            logger.info("BME280 polling thread stopped")

    thread = threading.Thread(target=_poll_loop, name="sensor-bme280", daemon=True)
    thread.start()
    return thread


def _log_startup_summary(config, logger):
    """Log the running configuration so the operator can confirm it from
    the first lines of the journal."""
    device_name = config["device"]["name"]
    cameras = list(config["cameras"].keys())
    pixel_threshold, area_threshold_percent = resolve_motion_thresholds(config)
    motion = config["motion"]
    retention = config["retention"]
    sensors_cfg = config["sensors"]
    ir_cfg = config["ir_emitter"]
    dashboard_cfg = config["dashboard"]

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
    logger.info(
        f"BME280 sensor: enabled={sensors_cfg['bme280']['enabled']} "
        f"address={hex(sensors_cfg['bme280']['i2c_address'])} "
        f"poll_interval={sensors_cfg['bme280']['poll_interval_seconds']}s"
    )
    ir_pins = {
        cam: ir_cfg["cameras"][cam]["gpio_pin"]
        for cam in ir_cfg.get("cameras", {})
    }
    logger.info(
        f"IR emitter: enabled={ir_cfg['enabled']} "
        f"brightness_threshold={ir_cfg['brightness_threshold']} "
        f"smoothing={ir_cfg['threshold_smoothing_seconds']}s "
        f"gpio={ir_pins}"
    )
    logger.info(
        f"Dashboard URL (operator reference): "
        f"http://{dashboard_cfg['host']}:{dashboard_cfg['port']}/"
    )


if __name__ == "__main__":
    main()
