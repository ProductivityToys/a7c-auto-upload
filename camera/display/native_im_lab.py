#!/usr/bin/env python3
"""Offline original im module lifecycle experiment, never a camera installer.

Maps the pinned ET_EXEC image in an isolated ARM process and invokes only selected
native dispatch/load/exit functions. OSAL semaphore allocation is simulated;
lookup can use original IMDB with private descriptor replacement. Unexpected
imports abort. Original dynamic linker executes a
purpose-built marker library, without any Sony startup, threads or hardware.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from audit_im_modules import IM, IMDB
from audit_ui_contract import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--research', type=Path, required=True)
parser.add_argument('--runtime', type=Path, required=True,
                    help='Existing successful native_text_lab output')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--native-imdb', action='store_true',
                    help='Use original IMDB lookup with a private descriptor replacement, then restore')
parser.add_argument('--standalone-marker', action='store_true',
                    help='Path-only trial uses the no-import camera marker module')
args = parser.parse_args()
if args.standalone_marker and not args.native_imdb:
    parser.error('--standalone-marker requires --native-imdb')
research, runtime, output = [p.resolve() for p in (args.research, args.runtime, args.output)]
manifest = json.loads((runtime/'manifest.json').read_text())
for name in ('libc.so.6', 'libdl.so.2', 'libgcc_s.so.1', 'ld.so',
             'libpthread.so.0', 'libstdc++.so.6', 'libm.so.6', 'librt.so.1'):
    if hashlib.sha256((runtime/name).read_bytes()).hexdigest() != manifest['sources'][name]['sha256']:
        raise ValueError('Runtime mismatch: '+name)
image = Image(research/IM[0], IM[1])
try:
    flat = bytearray(0xe000)
    for seg in image.loads:
        offset = seg['p_vaddr']-0x8000
        if offset < 0 or offset+seg['p_memsz'] > len(flat):
            raise ValueError('Unexpected im mapping')
        flat[offset:offset+seg['p_filesz']] = image.read(seg['p_vaddr'], seg['p_filesz'])
    imports = [(address, rel['symbol']) for address, rel in image.relocations.items()
               if rel['type'] == 22]
    # No application constructors or ELF entry point are executed. The copied
    # text is byte-identical; only these import slots are bound by the fixture.
    lines = []
    for i, (address, name) in enumerate(imports):
        lines.append('static void unsupported_%d(void){printf(%s);fflush(0);_exit(88);}' %
                     (i, json.dumps('UNSUPPORTED:'+name+'\n')))
    lines.append('static const struct {U address; const char *name; void *fallback;} imports[] = {')
    for i, (address, name) in enumerate(imports):
        lines.append('{0x%x,%s,unsupported_%d},' % (address, json.dumps(name), i))
    lines.append('};')
finally:
    image.stream.close()
output.mkdir(mode=0o700, parents=True, exist_ok=False)
if args.native_imdb:
    data = (research/IMDB[0]).read_bytes()
    if hashlib.sha256(data).hexdigest() != IMDB[1]:
        raise ValueError('Original IMDB library mismatch')
    (output/'libIMDB.so').write_bytes(data)
(output/'im-flat.bin').write_bytes(flat)
(output/'im_imports.h').write_text('\n'.join(lines)+'\n')
here = Path(__file__).resolve().parent
cc = ['/opt/homebrew/opt/llvm/bin/clang', '--target=arm-linux-gnueabi',
      '-mcpu=cortex-a9', '-marm', '-mfloat-abi=soft', '-Os', '-fPIC',
      '-Wall', '-Wextra', '-Werror', '-fno-stack-protector', '-fno-builtin', '-nostdlib', '-c',
      '-I'+str(output)]
if args.native_imdb:
    cc += ['-DNATIVE_IMDB=1']
if args.standalone_marker:
    cc += ['-DSTANDALONE_MARKER=1']
sources = [(here/'tests/native_im_arm_fixture.c', 'fixture'),
           (here/'tests/native_im_marker.c', 'marker'),
           (here.parents[1]/'maintenance/startup.S', 'startup')]
if args.standalone_marker:
    sources.append((here/'module/marker.c','standalone'))
for src, name in sources:
    subprocess.run(cc+[str(src), '-o', str(output/(name+'.o'))], check=True)
env = os.environ.copy()
env['DYLD_LIBRARY_PATH'] = str(research/'tools/lld21/lib')+':/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib'
ld = [str(research/'tools/lld21/lld'), '-flavor', 'gnu', '-m', 'armelf_linux_eabi',
      '--hash-style=sysv', '-z', 'nocombreloc', '-z', 'noexecstack']
subprocess.run(ld+['-shared', str(output/'marker.o'), '-o', str(output/'marker.so')], env=env, check=True)
if args.native_imdb:
    if args.standalone_marker:
        subprocess.run(ld+['-shared','-Bsymbolic',str(output/'standalone.o'),
                           '-o',str(output/'nt.so')],env=env,check=True)
    else:
        (output/'nt.so').write_bytes((output/'marker.so').read_bytes())
subprocess.run(ld+['--image-base=0x1000000', '--export-dynamic', '--dynamic-linker=/lab/ld.so',
                  '-e', '_start', str(output/'startup.o'), str(output/'fixture.o'),
                  str(runtime/'libc.so.6'), str(runtime/'libdl.so.2'), str(runtime/'libgcc_s.so.1'),
                  '-o', str(output/'fixture')], env=env, check=True)
(output/'fixture').chmod(0o755)
container = 'a7c-im-lab-'+uuid.uuid4().hex[:12]
cmd = ['docker', 'run', '--rm', '--init', '--pull', 'never', '--name', container,
       '--platform', 'linux/arm/v7', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
       '--security-opt', 'no-new-privileges', '--memory', '256m', '--cpus', '1',
       '--pids-limit', '32', '--ulimit', 'core=0',
       '--mount', f'type=bind,src={runtime},dst=/lab,readonly',
       '--mount', f'type=bind,src={output},dst=/probe,readonly', '--entrypoint', '/lab/ld.so',
       'alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc',
       '--library-path', '/lab', '/probe/fixture']
try:
    result = subprocess.run(cmd, capture_output=True, timeout=20)
except subprocess.TimeoutExpired:
    subprocess.run(['docker', 'rm', '-f', container], stdout=subprocess.DEVNULL)
    raise
stdout = result.stdout.decode(errors='replace')
report = {
    'scope': ('Offline original im lifecycle and original IMDB lookup; descriptor replacement/restoration confined to private container. OSAL semaphores simulated.'
              if args.native_imdb else 'Offline original im lifecycle; simulated module lookup and OSAL semaphores.') + ' No im startup, graphics, camera or live install.',
    'native_imdb': args.native_imdb,
    'standalone_marker': args.standalone_marker,
    'imdb_sha256': IMDB[1] if args.native_imdb else None,
    'source_sha256': IM[1],
    'fixture_sources': {src.name: hashlib.sha256(src.read_bytes()).hexdigest() for src, _ in sources},
    'native_entries': ['0x97ec', '0xb698', '0xb594', '0xb3b8', '0xb8a8', '0xb86e', '0xacd8'],
    'exit': result.returncode, 'stdout': stdout, 'stderr': result.stderr.decode(errors='replace'),
    'passed': (result.returncode == 0 and 'A7C_NATIVE_IM_LAB_OK 12' in stdout and
               (not args.native_imdb or ('NATIVE_IMDB_RESTORED all_words=2343' in stdout and
                                        'NATIVE_IMDB_PATH_ONLY_OK cases=2' in stdout))),
}
(output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
print(stdout)
print(output/'result.json')
if not report['passed']:
    raise SystemExit('Offline im lifecycle experiment failed')
