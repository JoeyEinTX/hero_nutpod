"""Flask app factory for the dashboard.

Opens its own EventLog and SensorLog connections (the motion service has
its own; SQLite handles the concurrent access via filesystem locking). The
config dict is attached to app.config so route handlers can read paths and
pagination settings without re-loading the YAML.
"""
from pathlib import Path

from flask import Flask

from dashboard.routes import register_routes
from storage.event_log import EventLog
from storage.sensor_log import SensorLog


def create_app(config, logger):
    pkg_dir = Path(__file__).parent
    app = Flask(
        "nutflix_dashboard",
        template_folder=str(pkg_dir / "templates"),
        static_folder=str(pkg_dir / "static"),
        static_url_path="/static",
    )
    app.config["NUTFLIX_CONFIG"] = config
    app.config["NUTFLIX_LOGGER"] = logger

    db_path = Path(config["paths"]["database"])
    app.config["NUTFLIX_EVENT_LOG"] = EventLog(db_path)
    app.config["NUTFLIX_SENSOR_LOG"] = SensorLog(db_path)

    register_routes(app)
    return app
