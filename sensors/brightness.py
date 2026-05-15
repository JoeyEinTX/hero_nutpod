"""Frame-brightness monitor used to drive the IR emitter.

Holds a rolling time-weighted average of mean Y-plane brightness. The state
("light" / "dark") only flips after the smoothed average has been on the
new side of `threshold` for at least `smoothing_seconds`. That dampens
porch-light flicker, lightning, and fast cloud transitions so the IR
emitter doesn't thrash on/off every few frames.
"""
import time

import numpy as np


class BrightnessMonitor:
    def __init__(self, threshold, smoothing_seconds, initial_state="light"):
        self.threshold = float(threshold)
        self.smoothing_seconds = float(smoothing_seconds)
        self.state = initial_state
        # The time at which the smoothed brightness first crossed to the
        # "other side" of the threshold; None while it agrees with self.state.
        self._cross_started_at = None

    def update(self, frame):
        """Feed one grayscale frame; return current state ("light"/"dark")."""
        mean = float(np.mean(frame))
        below = mean < self.threshold
        in_dark_zone = below
        target_state = "dark" if in_dark_zone else "light"

        if target_state == self.state:
            # No crossing in progress; reset any pending one.
            self._cross_started_at = None
            return self.state

        # Brightness disagrees with our committed state. Hold the crossing
        # for smoothing_seconds before flipping.
        now = time.monotonic()
        if self._cross_started_at is None:
            self._cross_started_at = now
        elif (now - self._cross_started_at) >= self.smoothing_seconds:
            self.state = target_state
            self._cross_started_at = None

        return self.state
