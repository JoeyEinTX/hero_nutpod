"""Load config.yaml as a plain dict, plus motion-threshold resolution.

The Phase 2 config nests capture settings under capture.snapshot/clip/motion_sampling
and adds heartbeat, motion, and retention blocks. The structure is the canonical
shape from Section 5.2 of the vision document. No keys beyond those defined there.
"""
import yaml


# Sensitivity preset -> (pixel_threshold, area_threshold_percent).
# These are the "reasonable defaults" referenced in Section 5.2.
# Explicit pixel_threshold / area_threshold_percent values in config override.
SENSITIVITY_PRESETS = {
    "low":    (40, 4.0),
    "medium": (25, 2.0),
    "high":   (15, 1.0),
}


def load_config(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def resolve_motion_thresholds(config):
    """Return (pixel_threshold, area_threshold_percent) for the current config.

    Preset supplies defaults; explicit values in the motion block override.
    """
    motion = config["motion"]
    preset = motion.get("sensitivity_preset", "medium")
    if preset not in SENSITIVITY_PRESETS:
        raise ValueError(
            f"unknown sensitivity_preset '{preset}'; "
            f"expected one of {sorted(SENSITIVITY_PRESETS)}"
        )
    default_pixel, default_area = SENSITIVITY_PRESETS[preset]
    pixel_threshold = motion.get("pixel_threshold", default_pixel)
    area_threshold_percent = motion.get("area_threshold_percent", default_area)
    return pixel_threshold, area_threshold_percent
