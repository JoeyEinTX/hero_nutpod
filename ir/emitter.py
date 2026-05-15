"""IR emitter GPIO control via gpiozero.

Wraps gpiozero.DigitalOutputDevice so the rest of the codebase doesn't have
to know whether GPIO is actually available. On a dev machine without
gpiozero (or without /dev/gpiochip*), the import / construction will fail
gracefully and a no-op stub is returned instead. The motion service then
runs to completion exactly as it would on the Pi, just without IR output.
"""
import logging


def make_ir_emitter(gpio_pin, enabled=True, logger=None):
    """Build an IR emitter for the given pin.

    Returns a real IREmitter on a Pi with gpiozero available, or a NoOpIREmitter
    otherwise (or if `enabled` is False). Either object exposes the same
    on() / off() / is_on / close() interface so callers don't branch.
    """
    log = logger or logging.getLogger("nutflix")

    if not enabled:
        log.info(f"IR emitter on GPIO {gpio_pin} disabled by config")
        return NoOpIREmitter(gpio_pin)

    try:
        return IREmitter(gpio_pin)
    except Exception as e:
        log.warning(
            f"IR emitter on GPIO {gpio_pin} unavailable ({e}); "
            f"continuing without IR control"
        )
        return NoOpIREmitter(gpio_pin)


class IREmitter:
    """Real GPIO-backed emitter. Drives the pin HIGH for ON, LOW for OFF."""

    def __init__(self, gpio_pin):
        from gpiozero import DigitalOutputDevice

        self.gpio_pin = int(gpio_pin)
        self._device = DigitalOutputDevice(self.gpio_pin, initial_value=False)

    def on(self):
        self._device.on()

    def off(self):
        self._device.off()

    @property
    def is_on(self):
        return bool(self._device.value)

    def close(self):
        try:
            self._device.close()
        except Exception:
            pass


class NoOpIREmitter:
    """Stub used when GPIO is unavailable or IR is disabled. Tracks state in
    memory so callers can still query is_on for status reporting."""

    def __init__(self, gpio_pin):
        self.gpio_pin = int(gpio_pin)
        self._is_on = False

    def on(self):
        self._is_on = True

    def off(self):
        self._is_on = False

    @property
    def is_on(self):
        return self._is_on

    def close(self):
        pass
