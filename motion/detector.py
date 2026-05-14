"""Frame-delta motion detector.

One MotionDetector instance per camera. Holds the previous frame and the
last trigger timestamp so that consecutive triggers respect the per-camera
cooldown.

Algorithm (Section 5.2):
1. Take the absolute per-pixel difference between the current frame and the
   previous frame (both grayscale, same shape).
2. Count pixels whose delta exceeds `pixel_threshold`.
3. If that count exceeds `area_threshold_percent` of the total pixels in the
   frame, motion has occurred.
4. After a trigger, suppress further triggers for `cooldown_seconds`.
"""
import time

import numpy as np


class MotionDetector:
    def __init__(self, pixel_threshold, area_threshold_percent, cooldown_seconds):
        self.pixel_threshold = int(pixel_threshold)
        self.area_threshold_percent = float(area_threshold_percent)
        self.cooldown_seconds = float(cooldown_seconds)
        self._previous = None
        self._last_trigger_time = 0.0

    def update(self, frame):
        """Feed one grayscale frame. Return True if motion fired this frame."""
        # First frame seeds the comparison; cannot trigger on it.
        if self._previous is None:
            self._previous = frame
            return False

        # int16 cast prevents uint8 underflow on the subtraction.
        delta = np.abs(frame.astype(np.int16) - self._previous.astype(np.int16))
        self._previous = frame

        changed_pixels = int(np.count_nonzero(delta > self.pixel_threshold))
        total_pixels = frame.size
        changed_percent = (changed_pixels / total_pixels) * 100.0

        if changed_percent < self.area_threshold_percent:
            return False

        now = time.monotonic()
        if (now - self._last_trigger_time) < self.cooldown_seconds:
            return False

        self._last_trigger_time = now
        return True

    def reset(self):
        """Drop the cached previous frame.

        Call after the camera leaves and re-enters motion sampling mode (e.g.
        after a clip recording) so the first frame back doesn't compare against
        a stale reference and false-trigger.
        """
        self._previous = None
