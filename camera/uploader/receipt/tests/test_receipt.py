"""Exercise the actual C codec with independent Python records and torn writes.

No camera, filesystem atomicity or physical power-loss claims are made here.
"""
import ctypes as C
import hashlib
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1]
Byte32 = C.c_ubyte * 32
class Receipt(C.Structure):
    _fields_ = [("bytes", C.c_ulonglong), ("destination", Byte32),
                ("identity", Byte32), ("source_sha256", Byte32),
                ("remote_path", Byte32), ("proof", C.c_uint)]
class Slot(C.Structure):
    _fields_ = [("data", C.c_void_p), ("length", C.c_uint), ("state", C.c_uint)]

def digest(s):
    return hashlib.sha256(s.encode()).digest()

def receipt(size=218138371, proof=2):
    r = Receipt()
    r.bytes, r.proof = size, proof
    for field in ("destination", "identity", "source_sha256", "remote_path"):
        setattr(r, field, Byte32.from_buffer_copy(digest(field)))
    return r

def reference(r):
    payload = (b'A7CRCP\r\n' + bytes((1, r.proof)) + struct.pack('<H', 512)
               + b'\0'*4 + struct.pack('<Q', r.bytes)
               + b''.join(bytes(getattr(r, f)) for f in
                           ('destination', 'identity', 'source_sha256', 'remote_path'))
               + b'\0'*328)
    assert len(payload) == 480
    return payload + hashlib.sha256(payload).digest()

def resign(data):
    return bytes(data[:480]) + hashlib.sha256(data[:480]).digest()

class Receipts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.tool = Path(cls.tmp.name)/'receipt'
        lib = Path(cls.tmp.name)/'receipt.so'
        flags = ['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror']
        subprocess.run(flags + ['-shared', '-fPIC', str(SRC/'receipt.c'), '-o', str(lib)], check=True)
        subprocess.run(flags + [str(SRC/'receipt.c'), str(SRC/'tool.c'), '-o', str(cls.tool)], check=True)
        cls.lib = C.CDLL(str(lib))
        cls.lib.a7c_receipt_encode.argtypes = [C.POINTER(Receipt), C.c_void_p]
        cls.lib.a7c_receipt_decode.argtypes = [C.c_void_p, C.c_uint, C.POINTER(Receipt)]
        cls.lib.a7c_receipt_recover.argtypes = [C.POINTER(Slot), C.POINTER(Receipt), C.c_uint, C.POINTER(C.c_int)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def decode(self, data):
        out = Receipt()
        rc = self.lib.a7c_receipt_decode(C.create_string_buffer(data), len(data), C.byref(out))
        return rc, out

    def recover(self, a, b=None, expected=None, minimum=2, states=None):
        data = [a, b]
        buffers = [C.create_string_buffer(d) if d is not None else None for d in data]
        slots = (Slot*2)(*(Slot(C.cast(buf, C.c_void_p), len(d) if d is not None else 0,
                              states[i] if states else (1 if d is not None else 0))
                          for i, (buf, d) in enumerate(zip(buffers, data))))
        chosen = C.c_int(999)
        rc = self.lib.a7c_receipt_recover(slots, C.byref(expected or receipt()), minimum, C.byref(chosen))
        return rc, chosen.value

    def test_reference_encoding_and_64bit_boundaries(self):
        for size in (1, 2**32-1, 2**32, 2**32+1, 2**63, 2**64-1):
            for proof in (1, 2):
                r = receipt(size, proof)
                out = C.create_string_buffer(512)
                self.assertEqual(self.lib.a7c_receipt_encode(C.byref(r), out), 0)
                self.assertEqual(out.raw, reference(r))
                status, decoded = self.decode(out.raw)
                self.assertEqual(status, 0)
                self.assertEqual(decoded.bytes, size)
                self.assertEqual(decoded.proof, proof)

    def test_every_truncation_and_trailing_data_rejected(self):
        raw = reference(receipt())
        for n in range(512):
            self.assertNotEqual(self.decode(raw[:n])[0], 0)
            self.assertEqual(self.recover(raw[:n]), (0, -1))
        for tail in (b'\0', raw, b'garbage'):
            self.assertNotEqual(self.decode(raw+tail)[0], 0)

    def test_every_single_bit_error_rejected(self):
        raw = reference(receipt())
        for pos in range(512):
            for bit in range(8):
                changed = bytearray(raw)
                changed[pos] ^= 1 << bit
                self.assertNotEqual(self.decode(bytes(changed))[0], 0)

    def test_each_interrupted_redundant_write_keeps_prior_receipt(self):
        raw = reference(receipt())
        for n in range(512):
            self.assertEqual(self.recover(raw, raw[:n]), (1, 0))
            self.assertEqual(self.recover(raw[:n], raw), (1, 1))
        self.assertEqual(self.recover(raw, raw), (1, 0))

    def test_full_length_torn_overwrites_do_not_invent_success(self):
        a = reference(receipt())
        other = receipt()
        other.source_sha256 = Byte32.from_buffer_copy(digest('different content'))
        b = reference(other)
        for n in range(513):
            torn = b[:n] + a[n:]
            status, decoded = self.decode(torn)
            if status == 0:
                self.assertIn(torn, (a, b))
                self.assertIn(bytes(decoded.source_sha256),
                              (bytes(receipt().source_sha256), bytes(other.source_sha256)))
            else:
                self.assertEqual(self.recover(torn), (0, -1))

    def test_conflicting_content_holds_both_slots(self):
        other = receipt()
        other.source_sha256 = Byte32.from_buffer_copy(digest('different content'))
        self.assertEqual(self.recover(reference(receipt()), reference(other)), (3, -1))

    def test_destination_identity_size_and_remote_path_are_bound(self):
        raw = reference(receipt())
        for field in ('destination', 'identity', 'remote_path'):
            expected = receipt()
            setattr(expected, field, Byte32.from_buffer_copy(digest('changed '+field)))
            self.assertEqual(self.recover(raw, expected=expected), (2, -1))
        self.assertEqual(self.recover(raw, expected=receipt(999)), (2, -1))
        # A valid matching slot never masks a valid foreign/colliding slot.
        foreign = receipt()
        foreign.destination = Byte32.from_buffer_copy(digest('other server'))
        self.assertEqual(self.recover(raw, reference(foreign)), (2, -1))

    def test_proof_strength_never_silently_downgraded(self):
        weak, strong = reference(receipt(proof=1)), reference(receipt())
        self.assertEqual(self.recover(weak), (4, -1))
        self.assertEqual(self.recover(weak, minimum=1), (1, 0))
        self.assertEqual(self.recover(weak, strong), (1, 1))
        self.assertEqual(self.recover(strong, weak), (1, 0))
        self.assertEqual(self.recover(strong, minimum=0), (2, -1))

    def test_size_proof_without_content_hash_and_strong_proof_requirement(self):
        r = receipt(proof=1)
        r.source_sha256 = Byte32()
        out = C.create_string_buffer(512)
        self.assertEqual(self.lib.a7c_receipt_encode(C.byref(r), out), 0)
        self.assertEqual(self.decode(out.raw)[0], 0)
        self.assertEqual(self.recover(out.raw, minimum=1), (1, 0))
        self.assertEqual(self.recover(out.raw, minimum=2), (4, -1))
        strong = reference(receipt())
        self.assertEqual(self.recover(out.raw, strong, minimum=1), (1, 1))
        self.assertEqual(self.recover(strong, out.raw, minimum=1), (1, 0))
        r.proof = 2
        self.assertNotEqual(self.lib.a7c_receipt_encode(C.byref(r), out), 0)
        self.assertNotEqual(self.decode(reference(r))[0], 0)

    def test_io_unknown_is_not_absent(self):
        raw = reference(receipt())
        self.assertEqual(self.recover(raw, None, states=[1, 2]), (2, -1))
        self.assertEqual(self.recover(None, None), (0, -1))
        self.assertEqual(self.recover(raw, None, states=[999, 0]), (2, -1))

    def test_future_version_or_proof_not_overwritten(self):
        raw = reference(receipt())
        for pos in (8, 9):
            newer = bytearray(raw)
            newer[pos] = 3
            newer = resign(newer)
            self.assertEqual(self.decode(newer)[0], 2)
            self.assertEqual(self.recover(raw, newer), (2, -1))

    def test_semantically_invalid_signed_records(self):
        raw = reference(receipt())
        for pos in (0, 10, 11, 12, 15, 152, 479):
            changed = bytearray(raw)
            changed[pos] ^= 1
            self.assertEqual(self.decode(resign(changed))[0], 1)
        for start, length in ((16, 8), (24, 32), (56, 32), (88, 32), (120, 32)):
            changed = bytearray(raw)
            changed[start:start+length] = b'\0'*length
            self.assertEqual(self.decode(resign(changed))[0], 1)

    def test_random_input_is_not_success(self):
        rng = random.Random(7)
        for _ in range(500):
            data = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 1025)))
            self.assertNotEqual(self.decode(data)[0], 0)

    def test_cli_uses_same_record_and_checks_key(self):
        r = receipt(2**32+1)
        fields = [bytes(getattr(r, f)).hex() for f in
                  ('destination', 'identity', 'source_sha256', 'remote_path')]
        result = subprocess.run([str(self.tool), 'encode', *fields[:2], str(r.bytes),
                                 *fields[2:], 'remote-sha256'], capture_output=True, check=True)
        self.assertEqual(result.stdout, reference(r))
        command = [str(self.tool), 'verify', *fields[:2], str(r.bytes), fields[3], 'remote-sha256']
        self.assertEqual(subprocess.run(command, input=result.stdout).returncode, 0)
        self.assertNotEqual(subprocess.run(command, input=result.stdout+b'\0').returncode, 0)
        command[2] = digest('wrong destination').hex()
        self.assertNotEqual(subprocess.run(command, input=result.stdout).returncode, 0)

    def test_cli_rejects_bad_arguments(self):
        fields = [digest(f).hex() for f in ('destination', 'identity', 'source', 'path')]
        for size in (1, 2**32, 2**64-1):
            cmd = [str(self.tool), 'encode', *fields[:2], str(size), *fields[2:], 'remote-sha256']
            result = subprocess.run(cmd, capture_output=True, check=True)
            self.assertEqual(self.decode(result.stdout)[1].bytes, size)
        for size in ('0', '-1', '+1', '1x', '01', str(2**64), ''):
            cmd = [str(self.tool), 'encode', *fields[:2], size, *fields[2:], 'remote-sha256']
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 64)
        for bad in ('', '0', 'g'*64, 'a'*63, 'a'*65):
            cmd = [str(self.tool), 'encode', bad, fields[1], '123', *fields[2:], 'remote-sha256']
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 64)

if __name__ == '__main__':
    unittest.main()
