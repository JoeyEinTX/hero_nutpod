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
03:00 local time. The Phase 3 dashboard adds a third unit — see below.

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
`retention.py`. The Phase 3 dashboard's "Mark as keeper" button does the
same move from the UI.

## Phase 3 — local dashboard, BME280, IR illumination

`dashboard.py` runs the local web dashboard as a separate process from the
motion service. It reads the SQLite database, serves the latest preview
frames written by the motion service, and lets you mark events as keepers.
`service.py` also gains BME280 polling and per-camera IR emitter control,
both of which run inside the existing motion service process.

### Foreground test

```
python3 service.py        # in one terminal
python3 dashboard.py      # in another
```

Then open `http://<pi-host-or-ip>:8080/` in a browser on the same LAN.
You should see the live preview page with both cameras refreshing every
two seconds. The Events page lists motion + heartbeat events with
thumbnails. The Status page shows uptime, latest BME280 reading, IR
emitter state per camera, and total event count.

### Install the dashboard systemd unit

```
sudo cp systemd/nutflix-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nutflix-dashboard.service
```

After this, all three units come up automatically on boot:

```
systemctl status nutflix.service nutflix-dashboard.service nutflix-retention.timer
journalctl -u nutflix-dashboard.service -f
```

Dashboard URL: `http://<host>:<port>/` using the values from
`dashboard.host` / `dashboard.port` in `config.yaml` (defaults
`0.0.0.0:8080`).

### Security boundary (READ THIS)

The dashboard has **no authentication** by design (per the local-first
principle of the project). Operators must:

- Bind the dashboard to LAN-accessible addresses only (`host: 0.0.0.0` is
  acceptable on trusted home networks; `host: 127.0.0.1` plus SSH
  tunneling is recommended otherwise).
- Never expose the dashboard port to the public internet via port
  forwarding, UPnP, or reverse proxy.
- Treat the LAN as a trust boundary. Any device with network access to
  the Pi can view all footage and toggle keepers.

These requirements come from Section 5.3 of the vision document.

### Troubleshooting

**Is the BME280 actually connected?** Check the I2C bus:

```
i2cdetect -y 1
```

You should see `76` (or `77`, depending on the breakout's SDO pin) in
the grid. If absent, recheck wiring (SDA/SCL/3.3V/GND) and that I2C is
enabled (`sudo raspi-config` → Interface Options → I2C).

**Manually toggle an IR emitter for testing.** From a Python shell on
the Pi (with the motion service stopped so it isn't fighting you for
the GPIO):

```python
from gpiozero import DigitalOutputDevice
ir = DigitalOutputDevice(17)  # use the pin from config.yaml
ir.on()                        # LEDs should illuminate
ir.off()
ir.close()
```

If the LEDs don't react, double-check the wiring against the table in
Section 5.3 of the vision document (V+, GND, In) and that the camera
can see the 940nm output (point a phone camera at the array — most
phone cameras render 940nm as a faint purple glow).

## Dependencies

Phase 1 + 2:

- Python 3 with `picamera2`, `numpy`, `pyyaml`
- `ffmpeg` (used by the clip recorder to mux raw H.264 into `.mp4`)
- `sqlite3` (Python stdlib; no extra install)

Phase 3 adds (apt-installable on Pi OS):

```
sudo apt install python3-flask python3-smbus2 python3-gpiozero python3-pil
```

No build step, no npm, no virtualenv required — Pi OS's system Python
plus apt packages is the supported configuration.
