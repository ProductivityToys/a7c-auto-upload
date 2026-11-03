"""Desktop USB lifetime: one connection through configuration, test and install."""
from contextlib import contextmanager


class DesktopSession:
    def __init__(self):
        self.transport = None
        self.camera = None

    @property
    def is_open(self):
        return self.transport is not None

    @contextmanager
    def use(self, log):
        if self.transport is None:
            from .sony_usb import SonyUsb
            transport = SonyUsb(log)
            camera = transport.__enter__()
            self.transport, self.camera = transport, camera
        # Each action has its own Qt worker. Never retain the previous worker's
        # signal as the logger when reusing its USB connection.
        self.transport.log = log
        try:
            yield self.camera
        except BaseException:
            self.close(log)
            raise

    def close(self, log=lambda _: None):
        transport = self.transport
        self.transport = self.camera = None
        if transport is not None:
            transport.log = log
            transport.__exit__(None, None, None)
