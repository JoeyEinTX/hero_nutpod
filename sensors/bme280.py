"""In-repo BME280 driver via stdlib smbus2.

Implements the Bosch BME280 datasheet protocol: read factory calibration
coefficients at init, perform a forced-mode measurement on each read(),
apply the datasheet compensation formulas. No external Adafruit /
circuit-python dependency.

Refer to the BME280 datasheet (Bosch BST-BME280-DS002) for register and
formula derivations. Variable names match the datasheet (dig_T1, t_fine, etc.)
so the math is auditable against the source.
"""
from smbus2 import SMBus, i2c_msg


# Register addresses (datasheet section 5.3).
REG_CALIB_TP = 0x88   # T1..T3 + P1..P9, 24 bytes
REG_CALIB_H1 = 0xA1   # 1 byte
REG_CALIB_H2 = 0xE1   # H2..H6, 7 bytes
REG_CTRL_HUM = 0xF2
REG_CTRL_MEAS = 0xF4
REG_CONFIG = 0xF5
REG_DATA = 0xF7       # press(3) + temp(3) + hum(2) = 8 bytes


class BME280:
    def __init__(self, i2c_bus, i2c_address):
        self.bus_number = int(i2c_bus)
        self.address = int(i2c_address)
        self._bus = SMBus(self.bus_number)
        self._read_calibration()
        # Filter off, standby 0.5ms, IIR off.
        self._bus.write_byte_data(self.address, REG_CONFIG, 0x00)

    def read(self):
        """Take one forced-mode measurement. Returns (temperature_c,
        humidity_percent, pressure_hpa). Raises on hardware/I2C failure."""
        # Force a single measurement: hum oversample x1, temp x1, press x1.
        self._bus.write_byte_data(self.address, REG_CTRL_HUM, 0x01)
        self._bus.write_byte_data(self.address, REG_CTRL_MEAS, 0x25)

        # Worst-case measurement time at x1 oversample is ~10ms (datasheet 9.1).
        import time
        time.sleep(0.012)

        data = self._bus.read_i2c_block_data(self.address, REG_DATA, 8)
        adc_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        adc_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        adc_h = (data[6] << 8) | data[7]

        temperature_c, t_fine = self._compensate_temperature(adc_t)
        pressure_pa = self._compensate_pressure(adc_p, t_fine)
        humidity_percent = self._compensate_humidity(adc_h, t_fine)
        return temperature_c, humidity_percent, pressure_pa / 100.0

    def close(self):
        try:
            self._bus.close()
        except Exception:
            pass

    def _read_calibration(self):
        c = self._bus.read_i2c_block_data(self.address, REG_CALIB_TP, 24)
        self.dig_T1 = _u16(c, 0)
        self.dig_T2 = _s16(c, 2)
        self.dig_T3 = _s16(c, 4)
        self.dig_P1 = _u16(c, 6)
        self.dig_P2 = _s16(c, 8)
        self.dig_P3 = _s16(c, 10)
        self.dig_P4 = _s16(c, 12)
        self.dig_P5 = _s16(c, 14)
        self.dig_P6 = _s16(c, 16)
        self.dig_P7 = _s16(c, 18)
        self.dig_P8 = _s16(c, 20)
        self.dig_P9 = _s16(c, 22)

        self.dig_H1 = self._bus.read_byte_data(self.address, REG_CALIB_H1)
        h = self._bus.read_i2c_block_data(self.address, REG_CALIB_H2, 7)
        self.dig_H2 = _s16(h, 0)
        self.dig_H3 = h[2]
        # H4 and H5 are 12-bit signed values packed across H4..H6 with the
        # nibble of byte 4 shared (datasheet table 16).
        self.dig_H4 = _sign12((h[3] << 4) | (h[4] & 0x0F))
        self.dig_H5 = _sign12((h[5] << 4) | (h[4] >> 4))
        self.dig_H6 = _s8(h[6])

    def _compensate_temperature(self, adc_T):
        var1 = (adc_T / 16384.0 - self.dig_T1 / 1024.0) * self.dig_T2
        var2 = ((adc_T / 131072.0 - self.dig_T1 / 8192.0) ** 2) * self.dig_T3
        t_fine = var1 + var2
        return t_fine / 5120.0, t_fine

    def _compensate_pressure(self, adc_P, t_fine):
        var1 = (t_fine / 2.0) - 64000.0
        var2 = var1 * var1 * self.dig_P6 / 32768.0
        var2 = var2 + var1 * self.dig_P5 * 2.0
        var2 = (var2 / 4.0) + (self.dig_P4 * 65536.0)
        var1 = (self.dig_P3 * var1 * var1 / 524288.0 + self.dig_P2 * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self.dig_P1
        if var1 == 0:
            return 0.0
        p = 1048576.0 - adc_P
        p = (p - var2 / 4096.0) * 6250.0 / var1
        var1 = self.dig_P9 * p * p / 2147483648.0
        var2 = p * self.dig_P8 / 32768.0
        return p + (var1 + var2 + self.dig_P7) / 16.0

    def _compensate_humidity(self, adc_H, t_fine):
        h = t_fine - 76800.0
        h = (
            (adc_H - (self.dig_H4 * 64.0 + self.dig_H5 / 16384.0 * h))
            * (self.dig_H2 / 65536.0 * (
                1.0 + self.dig_H6 / 67108864.0 * h
                * (1.0 + self.dig_H3 / 67108864.0 * h)
            ))
        )
        h = h * (1.0 - self.dig_H1 * h / 524288.0)
        return max(0.0, min(100.0, h))


def _u16(buf, i):
    return buf[i] | (buf[i + 1] << 8)


def _s16(buf, i):
    v = _u16(buf, i)
    return v - 65536 if v & 0x8000 else v


def _s8(v):
    return v - 256 if v & 0x80 else v


def _sign12(v):
    v &= 0x0FFF
    return v - 4096 if v & 0x0800 else v
