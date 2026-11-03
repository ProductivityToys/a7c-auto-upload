"""Bounded libusb ownership diagnostics; no packet content or Qt callbacks."""
from collections import deque
import ctypes


CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p)


class NativeUsbLog:
    def __init__(self, backend):
        self.backend = backend
        self.messages = deque(maxlen=24)
        self.callback = CALLBACK(self.receive)
        setter = backend.lib.libusb_set_log_cb
        setter.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        setter.restype = None
        backend.lib.libusb_set_debug.argtypes = [ctypes.c_void_p, ctypes.c_int]
        backend.lib.libusb_set_debug.restype = None
        setter(backend.ctx, ctypes.cast(self.callback, ctypes.c_void_p), 2)
        backend.lib.libusb_set_debug(backend.ctx, 4)

    def receive(self, context, level, message):
        text = message.decode('utf-8', errors='replace').strip()
        ownership = ('darwin_claim_interface', 'darwin_set_configuration',
                     'darwin_get_interface', 'darwin_detach_kernel_driver',
                     'darwin_restore_state')
        if level <= 2 or any(name in text for name in ownership):
            self.messages.append(text[:600])

    def close(self):
        if self.backend is not None:
            backend, self.backend = self.backend, None
            backend.lib.libusb_set_log_cb(backend.ctx, None, 2)
            backend.lib.libusb_set_debug(backend.ctx, 0)
