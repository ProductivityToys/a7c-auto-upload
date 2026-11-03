import importlib.util
import threading
import time
import test_listener as base
SRC = base.SRC


class TraceListenerTests(base.ListenerTests):
    additional_flags = ['-DMAINTENANCE_SECONDS=30', '-DACTION_TRACE']

    def client(self):
        path = SRC.parents[1] / 'nas/debugger/trace_client.py'
        spec = importlib.util.spec_from_file_location('trace_client', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def gated_action(self):
        (self.p / 'action.sh').write_text(
            '#!/bin/sh\nif [ "$1" = START ]; then\n'
            'echo BEFORE_NATIVE_CALL\n'
            'while [ ! -e "' + str(self.p / 'release') + '" ]; do sleep .01; done\n'
            'echo AFTER_NATIVE_CALL\nelse\n'
            'printf "A7C_DEBUG_V2\\nA7C_DEBUG_END\\n"\nfi\n')

    def test_trace_arrives_before_action_finishes(self):
        self.gated_action()
        chunks = []
        arrived = threading.Event()
        result = []
        def save(chunk):
            chunks.append(chunk)
            if b'BEFORE_NATIVE_CALL' in b''.join(chunks):
                arrived.set()
        worker = threading.Thread(target=lambda: result.append(self.client().request_trace(
            save, host='127.0.0.1', port=self.port, token_file=self.t)))
        worker.start()
        try:
            self.assertTrue(arrived.wait(3))
            self.assertTrue(worker.is_alive())
        finally:
            (self.p / 'release').touch()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(result[0]['complete'])
        self.assertEqual(result[0]['rc'], 0)
        self.assertIn(b'AFTER_NATIVE_CALL', b''.join(chunks))
        self.assertIn('STATUS 0', self.call())

    def test_timeout_preserves_stages_without_retry(self):
        self.gated_action()
        chunks = []
        try:
            log = self.p / 'operator-trace.log'
            result = self.client().capture_trace(log, host='127.0.0.1',
                port=self.port, token_file=self.t, response_timeout=.15)
            chunks.append(log.read_bytes())
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)
            self.assertFalse(result['complete'])
            self.assertEqual(result['outcome'], 'unknown')
            self.assertIsNone(result['rc'])
            self.assertIn(b'BEFORE_NATIVE_CALL', b''.join(chunks))
            self.assertNotIn(b'AFTER_NATIVE_CALL', b''.join(chunks))
        finally:
            (self.p / 'release').touch()
        time.sleep(.15)
        self.assertIn('RESULT 2 STATUS 0', self.call())

    def test_trace_still_requires_authentication(self):
        self.assertEqual(self.call(action='START_TRACE', token='b'*64), 'REJECTED\n')
        self.assertFalse((self.r / 'action.out').exists())
