#!/usr/bin/env python3
"""Build the fixed marker/path probe offline; no device access or installation."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import struct
import subprocess
import sys
from elftools.elf.elffile import ELFFile

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent))
from audit_im_modules import IM, IMDB
from audit_ui_contract import Image

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--research', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--text', action='store_true', help='Owned-RAM TextRM trial, fixed distinct pathname')
p.add_argument('--managed', action='store_true', help='TextRM into a private DDS source bitmap; never submit')
p.add_argument('--compose', action='store_true', help='1:1 blit between two private bitmaps, never screen')
p.add_argument('--shared-pool',action='store_true',help='Two private bitmaps in one owned DDS pool')
p.add_argument('--small-pool',action='store_true',help='Two 72x24 private bitmaps in one owned DDS pool')
p.add_argument('--screen-frame',action='store_true',help='Offline-only native-font single-frame DSO; no live probe or installation path')
p.add_argument('--screen-trial',action='store_true',help='Bounded native-font trial with external capture/redraw controller; no installation')
p.add_argument('--event-trial',action='store_true',help='One-shot native event forwarding/TID trial; no graphics or uploader changes')
p.add_argument('--rect-service-trial',action='store_true',help='RAM service indicator and reusable upload mailbox; no persistent install')
p.add_argument('--service-no-idle',action='store_true',help='Service ablation: suppress idle indicator, retain upload progress; experimental only')
p.add_argument('--service-single-buffer',action='store_true',help='Service ablation: reject the added photo double-buffer path; experimental only')
p.add_argument('--service-lifecycle-ack',action='store_true',help='Candidate: acknowledge native IM act/inact after local transition; offline validation first')
p.add_argument('--rect-upload-trial',action='store_true',help='One upload request, existing RAM percent/lifetime; bounded 60-second trial')
p.add_argument('--rect-series-trial',action='store_true',help='Bounded 9-second native rectangle progress; no production install')
p.add_argument('--rect-trial',action='store_true',help='Single native rectangle frame; external capture and redraw retirement')
p.add_argument('--gain-scope-trial',action='store_true',help='One-shot gain CPU rectangle-state observation; no drawing')
p.add_argument('--gain-trial',action='store_true',help='One-shot existing GraphicsSystem gain callback/TID; no custom drawing')
p.add_argument('--present-trial',action='store_true',help='Single pre-generated glyph copy after native completion; external redraw retirement')
p.add_argument('--present-alias-trial',action='store_true',help='Same one-shot copy with immediate read-only physical alias observation')
p.add_argument('--present-sync-trial',action='store_true',help='Single owned finite fence before the alias-trial glyph copy')
p.add_argument('--glyph',type=Path,help='Private native TextRM 20px UD 42%% raw asset (pinned digest)')
p.add_argument('--dds-import-observer',action='store_true',help='Offline passive DDS GOT observer; no live controller or installation')
p.add_argument("--ram-module-path", help="Distinct immutable path for a new rectangle trial in the same boot")
a = p.parse_args()
if (a.service_no_idle or a.service_single_buffer or a.service_lifecycle_ack) and not a.rect_service_trial:
    p.error('service ablations require --rect-service-trial')
if a.rect_service_trial:a.rect_upload_trial=True
if a.rect_upload_trial:a.rect_series_trial=True
if a.rect_series_trial:a.rect_trial=True
if a.ram_module_path and (not a.rect_trial or not re.fullmatch(r"/tmp_bt/a7[A-Z0-9]\.so",a.ram_module_path)):p.error("--ram-module-path requires rect-trial and a 15-byte /tmp_bt/a7X.so path")
if a.rect_trial:
    if a.gain_scope_trial:p.error('--rect-trial and --gain-scope-trial are mutually exclusive')
    a.gain_trial=True
if a.gain_scope_trial:a.gain_trial=True
if a.dds_import_observer:
    if any((a.text,a.managed,a.compose,a.shared_pool,a.small_pool,a.screen_frame,a.screen_trial,a.event_trial,a.gain_trial,a.present_trial,a.present_alias_trial,a.present_sync_trial,a.glyph)):
        p.error('--dds-import-observer is standalone')
    a.event_trial=True
if a.present_sync_trial:a.present_alias_trial=True
if a.present_alias_trial:a.present_trial=True
if a.present_trial:
    if a.event_trial or a.gain_trial:p.error('--present-trial is standalone')
    if not a.glyph:p.error('--present-trial requires --glyph')
    a.event_trial=True
elif a.glyph:p.error('--glyph requires --present-trial')
if a.gain_trial:
    if a.event_trial:p.error('--gain-trial and --event-trial are mutually exclusive')
    a.event_trial=True  # same bounded controller and marker ABI
if a.event_trial and any((a.text,a.managed,a.compose,a.shared_pool,a.small_pool,a.screen_frame,a.screen_trial)):
    p.error('--event-trial is standalone')
if a.screen_trial:a.screen_frame=True
if a.screen_frame:
    if any((a.text,a.managed,a.compose,a.shared_pool,a.small_pool)):p.error('--screen-frame is standalone')
    a.text=True
if a.small_pool:a.shared_pool=True
if a.shared_pool:a.compose=True
if a.compose:a.managed=True
if a.managed:a.text=True
module_path='/tmp_bt/a7X.so' if a.rect_service_trial else '/tmp_bt/a7W.so' if a.rect_upload_trial else '/tmp_bt/a7V.so' if a.rect_series_trial else '/tmp_bt/a7S.so' if a.rect_trial else '/tmp_bt/a7R.so' if a.gain_scope_trial else '/tmp_bt/a7F.so' if a.present_sync_trial else '/tmp_bt/a7A.so' if a.present_alias_trial else '/tmp_bt/a7P.so' if a.present_trial else '/tmp_bt/a7k.so' if a.gain_trial else '/tmp_bt/a7j.so' if a.event_trial else '/tmp_bt/a7q.so' if a.screen_trial else '/tmp_bt/a7i.so' if a.small_pool else '/tmp_bt/a7h.so' if a.shared_pool else '/tmp_bt/a7g.so' if a.compose else '/tmp_bt/a7b.so' if a.managed else '/tmp_bt/a7t.so' if a.text else '/tmp_bt/a7n.so'
if a.ram_module_path:module_path=a.ram_module_path
r, out = a.research.resolve(), a.output.resolve()
dependencies = [IM, IMDB,
    ('evidence/camera-2.00-boot/lib__libc-2.11.2.so',
     '2b294f4c256aebb2746cacddefc39c33c448a0d7f18c2813daa54109c445b910'),
    ('evidence/camera-2.00-power/usr__lib__libosal_uipc.so',
     'eecc322b81ebf63b26829fb2e8beee43af56f571b0ffbfc16d234dee5063becf')]
if a.rect_upload_trial:
    dependencies.append(('evidence/camera-2.00-boot/lib__librt-2.11.2.so','c50f058518dcae9ebb69141cb3b7f7f59d6278e4153020eca00b64ef197b8b40'))
if a.text or a.event_trial:
    dependencies.append(('evidence/camera-2.00-obj/usr__lib__libObj.so',
                         'ac07a5dfb140381bf95813a76794d83437726231a740928e590be8d4ea5dfdbd'))
for name, digest in dependencies:
    if hashlib.sha256((r/name).read_bytes()).hexdigest() != digest:
        raise ValueError('Dependency mismatch: '+name)
out.mkdir(parents=True, exist_ok=False, mode=0o700)
if a.present_trial:
    glyph=a.glyph.read_bytes()
    if len(glyph)!=2840 or hashlib.sha256(glyph).hexdigest()!='23fe782354190a7ebcdb02adc304668ec1e43d3b0539a9a46a05a33b68641d47':
        raise ValueError('Not the verified private native UD 42% glyph')
    (out/'present_glyph.h').write_text('/* Private native-generated glyph; not a distributable font asset. */\nstatic const unsigned short present_glyph[1420]={'+','.join(hex(v) for v in struct.unpack('<1420H',glyph))+'};\n')
env = os.environ.copy()
env['DYLD_LIBRARY_PATH'] = str(r/'tools/lld21/lib')+':/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib'
cc = ['/opt/homebrew/opt/llvm/bin/clang','--target=arm-linux-gnueabi',
      '-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-fPIC','-fno-builtin',
      '-fno-stack-protector','-Wall','-Wextra','-Werror','-nostdlib','-I'+str(out),'-c']
ld = [str(r/'tools/lld21/lld'),'-flavor','gnu','-m','armelf_linux_eabi',
      '--hash-style=sysv','-z','nocombreloc','-z','noexecstack']
cc += (['-DA7C_SERVICE_NO_IDLE'] if a.service_no_idle else []) + (['-DA7C_SERVICE_SINGLE_BUFFER'] if a.service_single_buffer else [])
cc += ['-DA7C_SERVICE_LIFECYCLE_ACK'] if a.service_lifecycle_ack else []
module_source=here/('rect_module.c' if a.rect_trial else 'dds_import_observer.c' if a.dds_import_observer else 'present_module.c' if a.present_trial else 'gain_module.c' if a.gain_trial else 'event_module.c' if a.event_trial else 'progress_module.c' if a.screen_frame else 'text.c' if a.text else 'marker.c')
subprocess.run(cc+(['-DA7C_RECT_SERVICE_TRIAL'] if a.rect_service_trial else [])+(['-DA7C_RECT_UPLOAD_TRIAL'] if a.rect_upload_trial else [])+(['-DA7C_RECT_SERIES_TRIAL'] if a.rect_series_trial else [])+(['-DA7C_RECT_ONCE_TRIAL'] if a.rect_trial else [])+(['-DGAIN_SCOPE_TRIAL'] if a.gain_scope_trial else [])+(['-DPRESENT_SYNC_TRIAL'] if a.present_sync_trial else [])+(['-DPRESENT_ALIAS_TRIAL'] if a.present_alias_trial else [])+(['-DA7C_NATIVE_SCREEN_TRIAL','-DA7C_FRAME_EXTERNAL_REDRAW'] if a.screen_trial else ['-DA7C_NATIVE_SUBMIT_OFFLINE'] if a.screen_frame else [])+(['-DMANAGED_TRIAL'] if a.managed else [])+(['-DCOMPOSE_TRIAL'] if a.compose else [])+(['-DSHARED_POOL_TRIAL'] if a.shared_pool else [])+(['-DSMALL_POOL_TRIAL'] if a.small_pool else [])+[str(module_source),'-o',str(out/'marker.o')],check=True)
subprocess.run(ld+['-shared','-Bsymbolic',str(out/'marker.o')]+
               ([str(r/dependencies[-1][0])] if a.text or a.event_trial else [])+
               ([str(r/dependencies[2][0])] if a.event_trial else [])+
               ['-o',str(out/'marker.so')],env=env,check=True)
with (out/'marker.so').open('rb') as f:
    e = ELFFile(f)
    symbols = {s.name:s for s in e.get_section_by_name('.dynsym').iter_symbols() if s.name}
    module_imports={n for n,s in symbols.items() if s['st_shndx']=='SHN_UNDEF'}
    expected_imports={'TextRM_'+n for n in ('loadFont','unloadFont','createText','getBounds','drawText','deleteText')} if a.text else set()
    if a.event_trial:expected_imports={'TextRM_loadFont','syscall'}
    if a.present_alias_trial:expected_imports|={'open','close','mmap64','munmap'}
    if a.managed:expected_imports|={'GRM_bitmapGetSubRectangle','GRM_bitmapWriteLockBits','GRM_bitmapWriteUnlockBits'}
    if a.compose:expected_imports.add('GRM_gpermRectblit')
    if a.shared_pool:expected_imports.add('GRM_bitmapCreate')
    if module_imports!=expected_imports: raise ValueError('Unexpected module imports: '+repr(module_imports))
    wanted = {'IM_SAMPLE_SO_'+name for name in ('init','exit','sus','res','inact','act')} | {'a7c_native_marker'}
    if set(symbols)-module_imports != wanted: raise ValueError('Unexpected marker exports')
    needed=[t.needed for t in e.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED']
    if needed != (['libObj.so','libc.so.6'] if a.event_trial else ['libObj.so'] if a.text else []): raise ValueError('Unexpected dependencies')
    if any(t.entry.d_tag in ('DT_INIT','DT_INIT_ARRAY','DT_FINI','DT_FINI_ARRAY')
           for t in e.get_section_by_name('.dynamic').iter_tags()):
        raise ValueError('Marker must have no dependencies or constructors')
    marker_offset = symbols['a7c_native_marker']['st_value']
if a.dds_import_observer:
    sources=[module_source,here/'dds_import_handoff.h',here/'build.py']
    manifest={'scope':'Offline passive DDS import observer; no pixel changes or live controller',
              'live_once_enabled':False,'dds_import_observer':True,'path':None,
              'dependencies':dict(dependencies),'marker_offset':marker_offset,
              'sources':{str(s.relative_to(here.parents[2])):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources},
              'binaries':{'marker.so':hashlib.sha256((out/'marker.so').read_bytes()).hexdigest()},
              'marker_imports':sorted(module_imports)}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(out);raise SystemExit(0)
if a.screen_frame and not a.screen_trial:
    sources=[module_source,here/'native_progress_frame.h',here/'native_submit.h',here/'text_state.h',here/'build.py']
    manifest={'scope':'Offline single-source native-font frame, init=42%, exit=transparent clear; no live controller',
              'live_once_enabled':False,'path':None,'dependencies':dict(dependencies),'marker_offset':marker_offset,
              'sources':{str(s.relative_to(here.parents[2])):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources},
              'binaries':{'marker.so':hashlib.sha256((out/'marker.so').read_bytes()).hexdigest()},
              'marker_imports':sorted(module_imports)}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(out)
    raise SystemExit(0)
imdb = Image(r/IMDB[0], IMDB[1])
try:
    words = struct.unpack('<11I',imdb.read(0x105d4,44))
    if words[3] != 2031 or words[4] != 0x60b6 or imdb.read(0x60b6,15) != b'libIMSample.so\0':
        raise ValueError('Unexpected fixed descriptor')
finally:
    imdb.stream.close()
(out/'module_contract.h').write_text(
    '#define MARKER_OFFSET 0x%xU\n#define MODULE_PATH "%s"\n#define MODULE_VERSION %dU\n#define TEXT_TRIAL %d\nstatic const U descriptor_words[11]={%s};\n' %
    (marker_offset,module_path,21 if a.rect_service_trial else 18 if a.rect_upload_trial else 17 if a.rect_series_trial else 16 if a.rect_trial else 15 if a.gain_scope_trial else 14 if a.present_sync_trial else 13 if a.present_alias_trial else 12 if a.present_trial else 11 if a.gain_trial else 10 if a.event_trial else 9 if a.screen_trial else 6 if a.small_pool else 5 if a.shared_pool else 4 if a.compose else 3 if a.managed else 2 if a.text else 1,
     0 if a.screen_trial else 5 if a.small_pool else 4 if a.shared_pool else 3 if a.compose else 2 if a.managed else int(a.text),','.join('0x%xU'%w for w in words))+
    ('#define SCREEN_TRIAL 1\n' if a.screen_trial or a.present_trial or a.rect_trial else '')+
    ('#define PRESENT_ALIAS_TRIAL 1\n' if a.present_alias_trial else '')+
    ('#define PRESENT_SYNC_TRIAL 1\n' if a.present_sync_trial else '')+
    ('#define PRESENT_TRIAL 1\n' if a.present_trial else '')+
    ('#define EVENT_TRIAL 1\n' if a.event_trial else '')+
    ('#define RECT_SERVICE_TRIAL 1\n' if a.rect_service_trial else '')+
    ('#define RECT_UPLOAD_TRIAL 1\n' if a.rect_upload_trial else '')+
    ('#define RECT_SERIES_TRIAL 1\n' if a.rect_series_trial else '')+
    ('#define RECT_TRIAL 1\n' if a.rect_trial else '')+
    ('#define GAIN_SCOPE_TRIAL 1\n' if a.gain_scope_trial else '')+
    ('#define GAIN_TRIAL 1\n' if a.gain_trial else ''))
startup = here.parents[2]/'maintenance/startup.S'
for source,name in ((here/'probe.c','probe'),(startup,'startup')):
    subprocess.run(cc+[str(source),'-o',str(out/(name+'.o'))],check=True)
subprocess.run(ld+['--dynamic-linker=/lib/ld-linux.so.3','--allow-shlib-undefined','-e','_start',
                  str(out/'startup.o'),str(out/'probe.o'),str(r/dependencies[3][0]),
                  str(r/dependencies[2][0])]+([str(r/'evidence/camera-2.00-boot/lib__librt-2.11.2.so')] if a.rect_upload_trial else [])+['-o',str(out/'module-probe')],env=env,check=True)
with (out/'module-probe').open('rb') as f:
    e=ELFFile(f)
    imports={s.name for s in e.get_section_by_name('.dynsym').iter_symbols()
             if s.name and s['st_shndx']=='SHN_UNDEF'}
    allowed={'__libc_start_main','alarm','open','close','read','pread','pwrite','write',
             'readlink','printf','snprintf','sscanf','strcmp','memcmp','memcpy','memset',
             'strtoull','pipe','fork','waitpid','poll','fflush','_exit','osal_snd_sync_direct'}
    if a.screen_trial or a.present_trial or a.rect_trial:allowed|={'mmap64','munmap','execv'}
    if a.event_trial:allowed|={'execv','kill','usleep'}
    if a.rect_upload_trial:allowed|={'access','strlen','clock_gettime','__errno_location','signal'}
    if not imports<=allowed: raise ValueError('Unexpected probe imports: '+repr(imports-allowed))
sources=[module_source,here/'probe.c',here/'path_transaction.h',here.parent/'im_modules.c',startup,here/'build.py']
if a.text:sources.append(here/'text_state.h')
if a.managed:sources.append(here/'managed_buffer.h')
if a.compose:sources.append(here/'owned_blit.h')
if a.screen_trial:sources += [here/n for n in ('native_progress_frame.h','native_submit.h','frame_control.h')]
if a.event_trial:sources += [here/n for n in ('event_handoff.h','event_state.h','event_control.h')]
if a.gain_trial:
    sources.remove(here/'event_handoff.h');sources.append(here/('frame_series.h' if a.rect_series_trial else 'frame_handoff.h'))
if a.rect_trial:sources += [here/n for n in ('native_rect_bar.h','frame_control.h')]
if a.rect_upload_trial:sources += [here/'rect_progress.h',here/'rect_upload_control.h',here.parent/'upload_lifetime.h',here.parents[1]/'uploader/upload_progress.h',here.parents[1]/'uploader/compat.h']
if a.rect_service_trial:sources += [here/'rect_service.h',here/'rect_service_control.h',here/'rpc_guard.h']
if a.gain_scope_trial:sources.append(here/'gain_scope.h')
if a.present_trial:sources += [here/n for n in ('present_state.h','present_blit.h','frame_control.h')]
if a.present_sync_trial:sources.append(here/'present_sync.h')
manifest={'scope':'Bounded single native-font frame with external native redraw; experimental screen trial' if a.screen_trial else '1:1 blit between two owned DDS bitmaps; no screen' if a.compose else 'Owned DDS source bitmap and TextRM; no screen submission' if a.managed else 'Owned-RAM TextRM trial; not a screen renderer' if a.text else 'Fixed no-drawing marker and 15-byte path trial; not production renderer',
          'live_once_enabled':not a.compose,
          'service_no_idle':a.service_no_idle,'service_single_buffer':a.service_single_buffer,
          'service_lifecycle_ack':a.service_lifecycle_ack,
          'dependencies':dict(dependencies),'marker_offset':marker_offset,
          'path':module_path,'module_id':2031,'owner':'0xa7c00001',
          'sources':{str(s.relative_to(here.parents[2])):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources},
          'binaries':{name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ('marker.so','module-probe')},
          'probe_imports':sorted(imports),'marker_imports':sorted(module_imports)}
if a.screen_trial:manifest.update(external_redraw=True,evidence_tmpfs_bytes=4194304,hold_ms=2000)
if a.event_trial:manifest.update(scope='One-shot native event forwarding and thread observation; no GraphicsEngine or drawing writes',event_trial=True,retain_immutable_mapping=True)
if a.gain_trial:manifest.update(scope='One-shot GraphicsSystem gain forwarding and thread observation; no custom graphics or GraphicsEngine writes',event_trial=False,gain_trial=True)
if a.gain_scope_trial:manifest.update(gain_scope_trial=True,scope='One-shot gain-thread CPU rectangle/state/queue observation; no graphics calls')
if a.rect_trial:manifest.update(rect_trial=True,scope='Single native rectangle frame at gain boundary; external capture and native redraw; experimental only',external_redraw=True)
if a.rect_series_trial:manifest.update(rect_series_trial=True,hold_ms=9000,scope='Bounded native 20/42/80 percent frames at gain boundary; automatic retirement; experimental only')
if a.rect_upload_trial:manifest.update(rect_upload_trial=True,hold_ms=60000,scope='One existing upload request, RAM progress mailbox and lifetime; bounded experiment, no production install')
if a.rect_service_trial:manifest.update(rect_service_trial=True,hold_ms=None,upload_deadline="existing request limit",scope='RAM service-owned idle icon and reusable upload progress; no idle worker or power lease')
if a.service_no_idle:manifest['scope']='Experimental upload-only service; idle drawing suppressed, hook retained; not hardware validated'
if a.service_single_buffer:manifest['scope']+='; single aperture target only'
if a.present_trial:manifest.update(scope='One native-generated glyph copy after original presentation completion; external native redraw, experimental only',event_trial=False,present_trial=True,present_alias_trial=a.present_alias_trial,external_redraw=True,glyph_sha256=hashlib.sha256(glyph).hexdigest(),generated_asset_sha256={'present_glyph.h':hashlib.sha256((out/'present_glyph.h').read_bytes()).hexdigest()})
if a.present_sync_trial:manifest.update(present_sync_trial=True,scope='Single finite native fence then glyph copy, with alias observation; experimental only')
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(out)
