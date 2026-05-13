"""Hero NutPod entry point — Phase 1 single-shot capture."""
from pathlib import Path

from cameras.camera_manager import CameraManager
from utils.config_loader import load_config
from utils.logger_setup import setup_logging


def main():
    config_path = Path(__file__).parent / "config.yaml"
    config = load_config(config_path)

    logger = setup_logging(Path(config["paths"]["logs"]))
    logger.info("Hero NutPod starting")

    manager = CameraManager(config, logger)
    manager.capture_all()

    logger.info("Hero NutPod shutdown complete")


if __name__ == "__main__":
    main()
