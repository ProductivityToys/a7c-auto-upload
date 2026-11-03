#!/usr/bin/env python3
"""Run original A7C 2.00 text code in an offline ARM container.

Private firmware/font inputs remain outside the repository. Disables constructors
in a COPY of libObj and substitutes unrelated device dependencies with aborting
stubs; only two fixed Backup settings are simulated. No camera connections,
network, hardware access or writable container mounts. Not a deployable renderer.
Requires the existing pinned ARM image, LLVM/LLD and owner-extracted resources.
"""
from pathlib import Path
import os,struct,shutil,subprocess,json,hashlib,argparse,uuid
from native_font import extract_embedded
from elftools.elf.elffile import ELFFile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--research',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();R=a.research.resolve();O=a.output.resolve()
IMAGE='alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc'
subprocess.run(['docker','image','inspect',IMAGE],check=True,stdout=subprocess.DEVNULL)
O.mkdir(mode=0o700,parents=True,exist_ok=False)
firm=R/'extracted-dat/firmware.tar_unpacked/0700_part_image/dev'
sources={'ld.so':R/'evidence/camera-2.00-resume/lib__ld-2.11.2.so','libc.so.6':R/'evidence/camera-2.00-boot/lib__libc-2.11.2.so','libdl.so.2':R/'evidence/camera-2.00-display-runtime/lib__libdl-2.11.2.so','libpthread.so.0':firm/'nflasha7_unpacked/lib/libpthread-2.11.2.so','libgcc_s.so.1':firm/'nflasha7_unpacked/lib/libgcc_s.so.1','libm.so.6':firm/'nflasha7_unpacked/lib/libm-2.11.2.so','libstdc++.so.6':firm/'nflasha15_unpacked/lib/libstdc++.so.6.0.14','librt.so.1':R/'evidence/camera-2.00-boot/lib__librt-2.11.2.so'}
provided=set()
for n,p in sources.items():
 shutil.copyfile(p,O/n)
 with p.open('rb') as f:
  e=ELFFile(f);provided|={s.name for s in e.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']!='SHN_UNDEF'}
src=R/'evidence/camera-2.00-obj/usr__lib__libObj.so';raw=bytearray(src.read_bytes());assert hashlib.sha256(raw).hexdigest()=='ac07a5dfb140381bf95813a76794d83437726231a740928e590be8d4ea5dfdbd'
with src.open('rb') as f:
 e=ELFFile(f);sym=list(e.get_section_by_name('.dynsym').iter_symbols());dyn=e.get_section_by_name('.dynamic');needed=[]
 for i,t in enumerate(dyn.iter_tags()):
  if t.entry.d_tag=='DT_NEEDED':needed.append(t.needed)
  if t.entry.d_tag in ('DT_INIT','DT_FINI'):struct.pack_into('<II',raw,dyn['sh_offset']+8*i,21,0)
  if t.entry.d_tag in ('DT_INIT_ARRAYSZ','DT_FINI_ARRAYSZ'):struct.pack_into('<I',raw,dyn['sh_offset']+8*i+4,0)
 (O/'libObj.so').write_bytes(raw)
 missing={s.name:s for s in sym if s.name and s['st_shndx']=='SHN_UNDEF' and s.name not in provided and s['st_info']['bind']!='STB_WEAK'}
lines=['extern int puts(const char *); extern void _exit(int); extern int fflush(void*);']
for i,(n,s) in enumerate(sorted(missing.items())):
 if n in ('Backup_read','Backup_get_datasize'):continue
 if s['st_info']['type']=='STT_OBJECT' or n.startswith(('_ZTI','_ZTV','_ZTT')):
  lines.append('unsigned char data_%d[%d] __asm__(%s);'%(i,max(s['st_size'],256),json.dumps(n)))
 else:
  lines.append('void fn_%d(void) __asm__(%s); void fn_%d(void){puts(%s);fflush(0);_exit(88);}'%(i,json.dumps(n),i,json.dumps('UNSUPPORTED:'+n)))
lines += [
 'static const char fontlist[]="/usr/share/app/fontlist.dat";',
 'int Backup_get_datasize(unsigned key){return key==0x810000?sizeof(fontlist):key==0x810001?4:-1;}',
 'int Backup_read(unsigned key,void *out){if(key==0x810000){char *p=out;for(unsigned i=0;i<sizeof(fontlist);i++)p[i]=fontlist[i];return sizeof(fontlist);}if(key==0x810001){*(unsigned*)out=0;return 4;}puts("UNEXPECTED_BACKUP_KEY");fflush(0);_exit(89);return -1;}'
]
(O/'stubs.c').write_text('\n'.join(lines)+'\n')
cc=['/opt/homebrew/opt/llvm/bin/clang','--target=arm-linux-gnueabi','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-fPIC','-fno-stack-protector','-fno-builtin','-nostdlib','-c']
subprocess.run(cc+[str(O/'stubs.c'),'-o',str(O/'stubs.o')],check=True)
env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(R/'tools/lld21/lib')+':/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib'
ld=[str(R/'tools/lld21/lld'),'-flavor','gnu','-m','armelf_linux_eabi','--hash-style=sysv','-z','nocombreloc']
subprocess.run(ld+['-shared','-soname','libfontlab-stub.so',str(O/'stubs.o')]+[str(O/n) for n in sources if n!='ld.so']+['-o',str(O/'libfontlab-stub.so')],env=env,check=True)
for n in needed:
 if n not in sources:(O/n).symlink_to('libfontlab-stub.so')
for n in sources:(O/n).chmod(0o755)
fontdir=O/'fonts';fontdir.mkdir();font, font_report=extract_embedded((R/'evidence/native-text-20261023/live-2.00-UniversOTS-SJ_wIcon.ltt').read_bytes());(fontdir/'UniversOTS-SJ.ttf').write_bytes(font)
(fontdir/'fontlist.dat').write_text('FONT_UNIVERS\t/usr/share/app/UniversOTS-SJ.ttf\t0\t0\n')
(O/'manifest.json').write_text(json.dumps({'scope':'Offline lab ONLY. Original native text code; library constructors disabled and unrelated hardware dependencies replaced by fail-fast stubs. Never install this library on camera.','source':str(src),'stub_symbols':len(missing),'sources':{n:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for n,p in sources.items()}},indent=2)+'\n')
print(O, 'stub_symbols=',len(missing))

for src,n in [(Path(__file__).resolve().parent/'tests/native_text_arm_fixture.c','fixture.o'),(Path(__file__).resolve().parents[2]/'maintenance/startup.S','startup.o')]:subprocess.run(cc+[str(src),'-o',str(O/n)],check=True)
env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(R/'tools/lld21/lib')+':/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib'
subprocess.run([str(R/'tools/lld21/lld'),'-flavor','gnu','-m','armelf_linux_eabi','--hash-style=sysv','-z','nocombreloc','--dynamic-linker=/lab/ld.so','-e','_start',str(O/'startup.o'),str(O/'fixture.o'),str(O/'libc.so.6'),str(O/'libdl.so.2'),'-o',str(O/'fixture')],env=env,check=True);(O/'fixture').chmod(0o755)
name='a7c-font-lab-'+uuid.uuid4().hex[:12]
cmd=['docker','run','--rm','--init','--pull','never','--name',name,'--platform','linux/arm/v7','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--cpus','1','--pids-limit','32','--ulimit','core=0','--mount',f'type=bind,src={O},dst=/lab,readonly','--mount',f'type=bind,src={O}/fonts,dst=/usr/share/app,readonly','--entrypoint','/lab/ld.so','alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc','--library-path','/lab','/lab/fixture']
try:r=subprocess.run(cmd,capture_output=True,timeout=25)
except subprocess.TimeoutExpired:
 subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL);raise
out=r.stdout.decode(errors='replace');err=r.stderr.decode(errors='replace')
report={'scope':'Offline modified-library lab; not a camera execution or installable payload',
        'exit':r.returncode,'stdout':out,'stderr':err,'font':font_report,
        'passed':r.returncode==0 and 'A7C_NATIVE_TEXT_LAB_OK 101' in out}
(O/'result.json').write_text(json.dumps(report,indent=2)+'\n')
if not report['passed']: raise SystemExit('Native font lab failed; see '+str(O/'result.json'))
for size in (20,24):
 raw=bytes.fromhex(out.split('PIXELS_%d '%size)[1].split('\n')[0]);(O/('native-%d.raw'%size)).write_bytes(raw)
print('PASS: 100 progress labels at 20px plus 24px reference; guard bytes and cleanup verified.')
print(O/'result.json')
