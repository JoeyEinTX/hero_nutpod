"""Hero NutPod local dashboard process.

Loads config, builds the Flask app from dashboard.app, and runs the dev
server bound to dashboard.host:dashboard.port. Honors SIGTERM/SIGINT for
clean shutdown via Werkzeug's reloader-aware shutdown path.

Per Section 5.3: this is a separate process from the motion service. It
never opens a Picamera2 instance, never writes to events/, and never holds
a write lock on the database. It only reads SQLite and serves files from
output/.
"""
import signal
import sys
from pathlib import Path

from dashboard.app import create_app
from utils.config_loader import load_config
from utils.logger_setup import setup_logging


def main():
    config_path = Path(__file__).parent / "config.yaml"
    config = load_config(config_path)

    logger = setup_logging(Path(config["paths"]["logs"]))
    dashboard_cfg = config["dashboard"]
    host = dashboard_cfg["host"]
    port = int(dashboard_cfg["port"])
    logger.info(f"Hero NutPod dashboard starting on http://{host}:{port}/")

    app = create_app(config, logger)

    def _shutdown(signum, _frame):
        logger.info(f"Dashboard received signal {signum}; exiting")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Werkzeug's dev server. Per Section 5.3 / Section 9 we deliberately do
    # not use gunicorn/waitress — one user, low request rate.
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=False)


if __name__ == "__main__":
    main()
