# Hero NutPod

Raspberry Pi 5 wildlife observation device. See `Nutflix_Vision_Document.md`
for the full architecture; this README covers operation.

## Phase 1 — one-shot capture

```
python3 main.py
```

Captures one full-resolution still from each camera into `output/snapshots/`.
Useful for verifying the camera pipeline.

## Phase 2 — long-running motion service

`service.py` runs continuously: monitors both cameras for motion, records
clips with pre/post-roll plus a full-resolution snapshot on every trigger,
captures heartbeat snapshots every 15 minutes, and logs every event to
`output/nutflix.db`. `retention.py` is a separate script that prunes old
media according to the windows in `config.yaml`.

### Foreground test

Before installing the systemd units, confirm the service runs by hand:

```
python3 service.py
```

The first lines of output should report the cameras detected, motion
thresholds in effect, heartbeat interval, and retention windows. Wave a
hand in front of NestCam — within a few seconds you should see a motion
event logged, a `.mp4` in `output/clips/`, a `.jpg` in `output/snapshots/`,
and a new row in `output/nutflix.db`. Heartbeat snapshots appear at the
configured interval. Press Ctrl+C for clean shutdown.

### Install the systemd units

The units assume the repository lives at `/home/joey/hero_nutpod` and runs
as user `joey`. Edit the unit files first if your paths differ.

```
sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nutflix.service nutflix-retention.timer
```

`nutflix.service` is the always-on motion service and restarts on failure.
`nutflix-retention.timer` fires `nutflix-retention.service` once per day at
03:00 local time.

### Monitoring

```
systemctl status nutflix.service
systemctl status nutflix-retention.timer
journalctl -u nutflix.service -f
journalctl -u nutflix-retention.service --since today
```

The application log is also written to `logs/nutflix.log` regardless of
how the service was started.

### Keepers

Move any file into `output/snapshots/keepers/` or `output/clips/keepers/`
to exempt it from retention. Those subdirectories are never touched by
`retention.py`.

## Dependencies

- Python 3 with `picamera2`, `numpy`, `pyyaml`
- `ffmpeg` (used by the clip recorder to mux raw H.264 into `.mp4`)
- `sqlite3` (Python stdlib; no extra install)
