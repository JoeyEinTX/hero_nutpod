"""Single-camera lifecycle wrapper around Picamera2."""
from picamera2 import Picamera2


class CameraDevice:
    def __init__(self, name, port, role, resolution):
        self.name = name
        self.port = port
        self.role = role
        self.resolution = tuple(resolution)
        self._camera = None

    def start(self):
        self._camera = Picamera2(self.port)
        still_config = self._camera.create_still_configuration(
            main={"size": self.resolution}
        )
        self._camera.configure(still_config)
        self._camera.start()

    def capture(self, output_path):
        self._camera.capture_file(str(output_path))

    def stop(self):
        if self._camera is not None:
            self._camera.stop()
            self._camera.close()
            self._camera = None
