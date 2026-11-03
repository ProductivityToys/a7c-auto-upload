"""Display transport client; runs in NAS memory, credentials remain local there."""
import hashlib
import re
import socket
from pathlib import Path

PHASES = {'before', 'during', 'late', 'after', 'first', 'screen'}
ROLES = {'capture', 'action'}


def request(verb, argument='', payload=None, *, host='192.168.5.110', port=21217,
            token_file='/var/services/homes/zee/.local/share/a7c-uploader/token'):
    if verb not in {'FRAME', 'SCREEN', 'PUSH', 'REARM', 'ROLLBACK', 'UPLOAD_ENABLE'}:
        raise ValueError('unsupported display transfer')
    if verb == 'PUSH':
        if argument not in ROLES or not isinstance(payload, bytes) or not 0 < len(payload) <= 65536:
            raise ValueError('invalid update role/size')
        argument += ':' + str(len(payload)) + ':' + hashlib.sha256(payload).hexdigest()
    elif payload is not None:
        raise ValueError('unexpected payload')
    elif ((verb == 'FRAME' and argument not in PHASES) or
          (verb == 'ROLLBACK' and argument not in ROLES) or
          (verb in {'SCREEN', 'REARM', 'UPLOAD_ENABLE'} and argument)):
        raise ValueError('invalid argument')
    token = Path(token_file).read_text().strip()
    if not re.fullmatch('[a-f0-9]{64}', token):
        raise ValueError('invalid token')
    with socket.create_connection((host, port), timeout=4) as s, s.makefile('rb') as f:
        s.settimeout(75)
        hello = f.readline(100).decode('ascii').split()
        if (len(hello) != 3 or hello[0] != 'A7CDBG2' or
                not re.fullmatch('[a-f0-9]{32}', hello[1]) or not hello[2].isdigit()):
            raise ValueError('bad greeting')
        seq = int(hello[2]) + 1
        s.sendall(('AUTH %s %s %d %s%s\n' %
                   (token, hello[1], seq, verb, ' ' + argument if argument else '')).encode())
        del token
        line = f.readline(256).decode('ascii').strip()
        if verb == 'PUSH' and line == 'READY %d %d' % (seq, len(payload)):
            s.sendall(payload)
            line = f.readline(256).decode('ascii').strip()
        result = {'action': verb, 'session': hello[1], 'seq': seq}
        if verb in {'FRAME', 'SCREEN'} and line.startswith('DATA '):
            parts = line.split()
            if (len(parts) != 5 or parts[:4] != ['DATA', str(seq), verb, '614400'] or
                    not re.fullmatch('[a-f0-9]{64}', parts[4])):
                raise ValueError('invalid frame header')
            raw = f.read(614400)
            if len(raw) != 614400 or hashlib.sha256(raw).hexdigest() != parts[4]:
                raise ValueError('incomplete/corrupt frame')
            result.update(data=raw, sha256=parts[4])
            line = f.readline(256).decode('ascii').strip()
        parts = line.split()
        if len(parts) != 4 or parts[:3] != ['RESULT', str(seq), verb] or not parts[3].isdigit():
            raise ValueError('invalid transfer acknowledgment')
        result['rc'] = int(parts[3])
        if f.read(1):
            raise ValueError('unexpected trailing response')
        if result['rc'] == 0 and verb in {'FRAME', 'SCREEN'} and 'data' not in result:
            raise ValueError('missing frame')
        return result
