"""Camera orchestration.

Phase 1: `CameraManager.capture_all()` performs one-shot stills (used by main.py).

Phase 2: `MotionCamera` wraps a single Picamera2 for motion sampling, snapshot,
and clip recording. `CameraWorker` is a thread that owns one MotionCamera and
runs the motion + heartbeat loop. `CameraWorker` plus `MotionCamera` together
honor the Section 5.2 sequential rule: on a single physical camera, motion
sampling / snapshot / clip recording never overlap.

Picamera2 is configured in motion mode with two streams:
    main  = clip resolution (2304x1296)  -> H.264 encoder + CircularOutput
    lores = motion sampling resolution (1536x864) YUV420 -> grayscale frame source

The CircularOutput maintains a rolling pre-roll seconds of H.264 frames in
memory at all times. When motion fires, opening a fileoutput and calling
start() flushes that buffered pre-roll to disk then continues writing for
post_roll_seconds. The raw .h264 file is then muxed to .mp4 with ffmpeg.

For the full-resolution snapshot (4608x2592) the camera leaves motion mode,
reconfigures to a still configuration, captures, and re-enters motion mode.

Phase 3 additions to CameraWorker (additive only, Phase 2 logic unchanged):
- BrightnessMonitor fed every motion tick; transitions drive an IREmitter
  on()/off() so IR LEDs follow the scene's average brightness.
- Preview-frame writer: every preview_refresh_seconds, the current lores
  Y-plane frame is saved as a grayscale JPEG to output/preview/{name}.jpg
  for the dashboard's live view.
- IR state is published to output/preview/state.json (one shared file across
  both workers, atomic rename) so the dashboard can show it on /status.
"""
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from cameras.camera_device import CameraDevice
from motion.detector import MotionDetector


# Config keys are lowercase per Section 8; saved filenames use the canonical
# PascalCase camera role names. Mapping lives here, not in config.
CAMERA_DISPLAY_NAMES = {
    "nestcam": "NestCam",
    "crittercam": "CritterCam",
}


# AWB preset name -> libcamera AwbMode enum value. Auto wanders, especially
# on IMX708 NoIR (no IR-cut filter means IR bleeds into the red channel and
# pulls auto-WB warm); pinning to a fixed preset keeps clip color consistent.
AWB_MODE_VALUES = {
    "auto": 0,
    "tungsten": 1,
    "fluorescent": 2,
    "indoor": 3,
    "daylight": 4,
    "cloudy": 5,
    "custom": 6,
}


# ---------------------------------------------------------------------------
# Phase 1: one-shot capture (kept for main.py / diagnostics).
# ---------------------------------------------------------------------------


class CameraManager:
    def __init__(self, config, logger):
        self.logger = logger
        self.device_name = config["device"]["name"]
        self.resolution = config["capture"]["snapshot"]["resolution"]
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


# ---------------------------------------------------------------------------
# Phase 2: motion-mode camera + per-camera worker thread.
# ---------------------------------------------------------------------------


class MotionCamera:
    """Picamera2 wrapper that switches between motion-sampling video mode and
    full-resolution still capture for snapshots."""

    def __init__(self, port, snapshot_resolution, clip_resolution,
                 motion_resolution, framerate, pre_roll_seconds, awb_mode,
                 logger):
        self.port = port
        self.snapshot_resolution = tuple(snapshot_resolution)
        self.clip_resolution = tuple(clip_resolution)
        self.motion_resolution = tuple(motion_resolution)
        self.framerate = int(framerate)
        self.pre_roll_seconds = int(pre_roll_seconds)
        self.awb_mode = str(awb_mode)
        self.logger = logger

        self._picam2 = None
        self._encoder = None
        self._circular_output = None
        self._video_config = None
        self._motion_height = self.motion_resolution[1]

    def start_motion_mode(self):
        # Picamera2 imports are local so that Phase 1 / dev environments
        # without the library can still import this module.
        from picamera2 import Picamera2
        from picamera2.encoders import H264Encoder
        from picamera2.outputs import CircularOutput

        self._picam2 = Picamera2(self.port)
        # Pin the framerate by setting FrameDurationLimits to a fixed value
        # (min=max). Without this Picamera2 runs at its default rate and
        # under CPU load may drop frames silently — the resulting .mp4 is
        # tagged with the configured fps but contains fewer frames, so
        # playback looks sped up.
        frame_duration_us = int(1_000_000 / self.framerate)
        awb_value = AWB_MODE_VALUES.get(
            self.awb_mode.lower(), AWB_MODE_VALUES["auto"]
        )
        self._video_config = self._picam2.create_video_configuration(
            main={"size": self.clip_resolution, "format": "RGB888"},
            lores={"size": self.motion_resolution, "format": "YUV420"},
            controls={
                "FrameDurationLimits": (frame_duration_us, frame_duration_us),
                "AwbMode": awb_value,
            },
        )
        self._picam2.configure(self._video_config)

        # Buffer pre_roll_seconds worth of frames at the configured framerate.
        buffer_size = max(1, self.framerate * self.pre_roll_seconds)
        self._encoder = H264Encoder()
        self._circular_output = CircularOutput(buffersize=buffer_size)

        self._picam2.start()
        self._picam2.start_encoder(self._encoder, self._circular_output)

    def read_motion_frame(self):
        """Return the current lores Y plane as a 2D uint8 numpy array."""
        # YUV420 layout: full-res Y plane stacked above half-res U and V.
        # capture_array("lores") returns the full YUV buffer; the top
        # motion_height rows are the grayscale Y plane.
        yuv = self._picam2.capture_array("lores")
        return yuv[: self._motion_height, :]

    def record_clip(self, mp4_path, post_roll_seconds):
        """Flush pre-roll, record post_roll seconds, mux to MP4."""
        h264_path = Path(str(mp4_path)).with_suffix(".h264")

        # Opening fileoutput on the still-running CircularOutput dumps the
        # buffered pre-roll into the file, then continues writing live frames.
        self._circular_output.fileoutput = str(h264_path)
        self._circular_output.start()
        try:
            time.sleep(post_roll_seconds)
        finally:
            self._circular_output.stop()
            self._circular_output.fileoutput = None

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-loglevel", "error",
                    "-r", str(self.framerate),
                    "-i", str(h264_path),
                    "-c", "copy",
                    str(mp4_path),
                ],
                check=True,
            )
            h264_path.unlink(missing_ok=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            # ffmpeg failed or is not installed; preserve raw H.264 next to
            # the would-be mp4 so the clip is not lost.
            self.logger.error(
                f"ffmpeg mux failed for {mp4_path}: {e}; "
                f"raw H.264 left at {h264_path}"
            )

    def capture_snapshot(self, jpg_path):
        """Switch to still mode, capture, return to motion mode.

        Stops the encoder + camera so the still configuration can be applied,
        captures the JPEG, then re-enters motion mode with a fresh
        CircularOutput. The new buffer starts empty; the next motion event's
        pre-roll will only have whatever has accumulated since this call.
        """
        from picamera2.encoders import H264Encoder
        from picamera2.outputs import CircularOutput

        self._picam2.stop_encoder()
        self._picam2.stop()

        still_config = self._picam2.create_still_configuration(
            main={"size": self.snapshot_resolution}
        )
        self._picam2.configure(still_config)
        self._picam2.start()
        try:
            self._picam2.capture_file(str(jpg_path))
        finally:
            self._picam2.stop()

        self._picam2.configure(self._video_config)
        buffer_size = max(1, self.framerate * self.pre_roll_seconds)
        self._encoder = H264Encoder()
        self._circular_output = CircularOutput(buffersize=buffer_size)
        self._picam2.start()
        self._picam2.start_encoder(self._encoder, self._circular_output)

    def stop(self):
        if self._picam2 is None:
            return
        try:
            self._picam2.stop_encoder()
        except Exception:
            pass
        try:
            self._picam2.stop()
        except Exception:
            pass
        try:
            self._picam2.close()
        except Exception:
            pass
        self._picam2 = None
        self._encoder = None
        self._circular_output = None


class IRStatePublisher:
    """Shared writer for output/preview/state.json.

    Both CameraWorkers call publish() when their IR state transitions; we
    serialize the file write under a lock and rename atomically so the
    dashboard never sees a half-written JSON. Per Section 5.3 the dashboard
    is a separate process, so the filesystem is the only sync channel.
    """

    def __init__(self, state_path):
        self.state_path = Path(state_path)
        self._lock = threading.Lock()
        self._state = {}

    def publish(self, camera_key, ir_state):
        with self._lock:
            self._state[camera_key] = ir_state
            payload = {
                **self._state,
                "updated": datetime.now().isoformat(timespec="seconds"),
            }
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload))
            os.replace(tmp, self.state_path)


class CameraWorker(threading.Thread):
    """One thread per camera. Runs motion sampling, fires clip + snapshot on
    motion, takes a heartbeat snapshot every heartbeat_interval_seconds.

    Phase 3: also runs brightness monitoring (drives IR emitter) and writes
    a preview frame to disk every preview_refresh_seconds. Both happen
    inline in the motion tick — no extra threads."""

    def __init__(self, *, display_name, device_name, motion_camera, detector,
                 event_log, snapshots_dir, clips_dir,
                 heartbeat_interval_seconds, post_roll_seconds,
                 motion_framerate, stop_event, logger,
                 brightness_monitor, ir_emitter, ir_state_publisher,
                 preview_dir, preview_refresh_seconds):
        super().__init__(name=f"camera-{display_name}", daemon=True)
        self.display_name = display_name
        self.device_name = device_name
        self.motion_camera = motion_camera
        self.detector = detector
        self.event_log = event_log
        self.snapshots_dir = Path(snapshots_dir)
        self.clips_dir = Path(clips_dir)
        self.heartbeat_interval_seconds = float(heartbeat_interval_seconds)
        self.post_roll_seconds = int(post_roll_seconds)
        self.motion_framerate = int(motion_framerate)
        self.stop_event = stop_event
        self.logger = logger

        self.brightness_monitor = brightness_monitor
        self.ir_emitter = ir_emitter
        self.ir_state_publisher = ir_state_publisher
        self.preview_dir = Path(preview_dir)
        self.preview_refresh_seconds = float(preview_refresh_seconds)
        self._preview_path = self.preview_dir / f"{display_name.lower()}.jpg"
        self._last_preview_write = 0.0
        # Track committed brightness state so we only fire IR transitions
        # on actual changes, not every tick.
        self._last_ir_state = "light"

        # Cap the motion loop near the actual frame rate. Picamera2's
        # capture_array("lores") returns the most recent frame immediately
        # rather than blocking for a new one, so without this the loop
        # re-processes the same frame thousands of times per second and
        # pegs the CPU.
        self._frame_interval = 1.0 / float(self.motion_framerate)

        self._next_heartbeat = time.monotonic() + self.heartbeat_interval_seconds

    def run(self):
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.preview_dir.mkdir(parents=True, exist_ok=True)

        # Seed the shared IR-state file with this camera's initial state so
        # the dashboard's /status page has something to read even before the
        # first transition.
        self._publish_ir_state(self._last_ir_state)

        try:
            self.motion_camera.start_motion_mode()
            self.logger.info(f"{self.display_name} entered motion mode")
        except Exception as e:
            self.logger.error(
                f"{self.display_name} failed to start motion mode: {e}",
                exc_info=True,
            )
            return

        try:
            while not self.stop_event.is_set():
                try:
                    self._tick()
                except Exception as e:
                    self.logger.error(
                        f"{self.display_name} loop error: {e}", exc_info=True
                    )
                    # Brief pause before retrying so a persistent error
                    # doesn't spin the CPU.
                    self.stop_event.wait(1.0)
                    # Skip the frame-interval wait below — we already paused.
                    continue
                # Rate-limit to the motion sampling framerate so we don't
                # re-process the same lores frame. stop_event.wait (vs
                # time.sleep) keeps shutdown latency to one frame interval.
                self.stop_event.wait(self._frame_interval)
        finally:
            try:
                self.ir_emitter.off()
                self.ir_emitter.close()
            except Exception:
                pass
            self.motion_camera.stop()
            self.logger.info(f"{self.display_name} stopped")

    def _tick(self):
        frame = self.motion_camera.read_motion_frame()

        # Brightness monitoring + IR emitter follow the same lores frame the
        # detector sees, so we get this for free without a second camera read.
        new_state = self.brightness_monitor.update(frame)
        if new_state != self._last_ir_state:
            self.logger.info(
                f"{self.display_name} brightness state -> {new_state}"
            )
            if new_state == "dark":
                self.ir_emitter.on()
            else:
                self.ir_emitter.off()
            self._last_ir_state = new_state
            self._publish_ir_state(new_state)

        # Throttled preview write for the dashboard's live view.
        now = time.monotonic()
        if (now - self._last_preview_write) >= self.preview_refresh_seconds:
            self._write_preview(frame)
            self._last_preview_write = now

        triggered = self.detector.update(frame)

        if triggered:
            self._handle_motion()
        elif time.monotonic() >= self._next_heartbeat:
            self._handle_heartbeat()

    def _write_preview(self, frame):
        """Save the current Y-plane frame as a grayscale JPEG preview."""
        try:
            from PIL import Image
        except ImportError:
            # PIL absent on a dev machine — skip silently. The dashboard's
            # /preview route will just 404 until PIL is installed.
            return
        try:
            tmp = self._preview_path.with_suffix(".jpg.tmp")
            Image.fromarray(frame, mode="L").save(tmp, "JPEG", quality=80)
            os.replace(tmp, self._preview_path)
        except Exception as e:
            self.logger.warning(
                f"{self.display_name} preview write failed: {e}"
            )

    def _publish_ir_state(self, ir_state):
        if self.ir_state_publisher is None:
            return
        try:
            self.ir_state_publisher.publish(self.display_name.lower(), ir_state)
        except Exception as e:
            self.logger.warning(
                f"{self.display_name} IR state publish failed: {e}"
            )

    def _handle_motion(self):
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base = f"{self.device_name}_{self.display_name}_{timestamp_str}"
        clip_path = self.clips_dir / f"{base}.mp4"
        snapshot_path = self.snapshots_dir / f"{base}.jpg"

        self.logger.info(f"{self.display_name} motion -> {clip_path.name}")

        # Order: clip first (so the pre-roll buffer is preserved), then
        # snapshot (which requires reconfiguring to still mode). Both files
        # share the trigger timestamp.
        self.motion_camera.record_clip(clip_path, self.post_roll_seconds)
        self.motion_camera.capture_snapshot(snapshot_path)

        # Reset detector so the first frame after the reconfigure doesn't
        # diff against a stale pre-trigger reference.
        self.detector.reset()

        self.event_log.insert_motion_event(
            device_name=self.device_name,
            camera_name=self.display_name,
            snapshot_path=str(snapshot_path).replace("\\", "/"),
            clip_path=str(clip_path).replace("\\", "/"),
        )

    def _handle_heartbeat(self):
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        snapshot_path = (
            self.snapshots_dir
            / f"{self.device_name}_{self.display_name}_{timestamp_str}.jpg"
        )

        self.logger.info(
            f"{self.display_name} heartbeat -> {snapshot_path.name}"
        )

        self.motion_camera.capture_snapshot(snapshot_path)
        self.detector.reset()

        self.event_log.insert_heartbeat_event(
            device_name=self.device_name,
            camera_name=self.display_name,
            snapshot_path=str(snapshot_path).replace("\\", "/"),
        )

        self._next_heartbeat = (
            time.monotonic() + self.heartbeat_interval_seconds
        )


def build_workers(config, event_log, stop_event, logger):
    """Construct one CameraWorker per camera defined in config.

    Returns the list of (not-yet-started) workers. service.py owns starting
    and joining them.
    """
    from ir.emitter import make_ir_emitter
    from sensors.brightness import BrightnessMonitor
    from utils.config_loader import resolve_motion_thresholds

    device_name = config["device"]["name"]
    snapshot_resolution = config["capture"]["snapshot"]["resolution"]
    clip_cfg = config["capture"]["clip"]
    motion_cfg = config["capture"]["motion_sampling"]
    awb_mode = config["capture"].get("awb_mode", "auto")

    pixel_threshold, area_threshold_percent = resolve_motion_thresholds(config)
    cooldown_seconds = config["motion"]["cooldown_seconds"]
    heartbeat_interval_seconds = (
        config["heartbeat"]["interval_minutes"] * 60.0
    )

    snapshots_dir = Path(config["paths"]["snapshots"])
    clips_dir = Path(config["paths"]["clips"])
    preview_dir = Path(config["paths"]["preview"])

    dashboard_cfg = config["dashboard"]
    ir_cfg = config["ir_emitter"]

    # One shared publisher for the IR-state JSON file: both workers write
    # into it, so they need a common lock.
    ir_state_publisher = IRStatePublisher(preview_dir / "state.json")

    workers = []
    for key, cam_cfg in config["cameras"].items():
        display_name = CAMERA_DISPLAY_NAMES[key]
        motion_camera = MotionCamera(
            port=cam_cfg["port"],
            snapshot_resolution=snapshot_resolution,
            clip_resolution=clip_cfg["resolution"],
            motion_resolution=motion_cfg["resolution"],
            framerate=clip_cfg["framerate"],
            pre_roll_seconds=clip_cfg["pre_roll_seconds"],
            awb_mode=awb_mode,
            logger=logger,
        )
        detector = MotionDetector(
            pixel_threshold=pixel_threshold,
            area_threshold_percent=area_threshold_percent,
            cooldown_seconds=cooldown_seconds,
        )
        brightness_monitor = BrightnessMonitor(
            threshold=ir_cfg["brightness_threshold"],
            smoothing_seconds=ir_cfg["threshold_smoothing_seconds"],
        )
        ir_emitter = make_ir_emitter(
            gpio_pin=ir_cfg["cameras"][key]["gpio_pin"],
            enabled=ir_cfg["enabled"],
            logger=logger,
        )
        worker = CameraWorker(
            display_name=display_name,
            device_name=device_name,
            motion_camera=motion_camera,
            detector=detector,
            event_log=event_log,
            snapshots_dir=snapshots_dir,
            clips_dir=clips_dir,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            post_roll_seconds=clip_cfg["post_roll_seconds"],
            motion_framerate=motion_cfg["framerate"],
            stop_event=stop_event,
            logger=logger,
            brightness_monitor=brightness_monitor,
            ir_emitter=ir_emitter,
            ir_state_publisher=ir_state_publisher,
            preview_dir=preview_dir,
            preview_refresh_seconds=dashboard_cfg["preview_refresh_seconds"],
        )
        workers.append(worker)
    return workers
