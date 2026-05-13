"""Sequential capture across all configured cameras.

Sequential (not concurrent) is deliberate: prior iterations had resource
conflicts when both CSI cameras ran in parallel. Phase 1 trades throughput
for reliability.
"""
from datetime import datetime
from pathlib import Path

from cameras.camera_device import CameraDevice


# Config keys are lowercase per Section 8; saved filenames use the canonical
# PascalCase camera role names. Mapping lives here, not in config.
CAMERA_DISPLAY_NAMES = {
    "nestcam": "NestCam",
    "crittercam": "CritterCam",
}


class CameraManager:
    def __init__(self, config, logger):
        self.logger = logger
        self.device_name = config["device"]["name"]
        self.resolution = config["capture"]["resolution"]
        self.snapshots_dir = Path(config["paths"]["snapshots"])
        self.cameras_config = config["cameras"]

    def capture_all(self):
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        for key, cam_cfg in self.cameras_config.items():
            display_name = CAMERA_DISPLAY_NAMES[key]
            self._capture_one(display_name, cam_cfg, timestamp)

    def _capture_one(self, display_name, cam_cfg, timestamp):
        filename = f"{self.device_name}_{display_name}_{timestamp}.jpg"
        output_path = self.snapshots_dir / filename

        device = CameraDevice(
            name=display_name,
            port=cam_cfg["port"],
            role=cam_cfg["role"],
            resolution=self.resolution,
        )

        try:
            device.start()
            device.capture(output_path)
            self.logger.info(f"Captured {display_name} -> {output_path}")
        except Exception as e:
            self.logger.error(
                f"{display_name} capture failed: {e}", exc_info=True
            )
        finally:
            device.stop()
