#!/usr/bin/env python3
"""Build an experimental display diagnostic; never contacts a camera."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from elftools.elf.elffile import ELFFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=("framebuffer", "ui-help", "ui-layout", "detached-launch",
                                         "ui-listener", "wireless-launch", "ui-layout-all",
                                         "ui-widgets-playback", "dds-once", "dds-text-once", "dds-edge-once",
                                         "dds-listener", "dds-launch", "dds-blink-launch", "redraw-once", "im-modules", "im-identity", "frame-context", "progress-sampler"), default="framebuffer")
    parser.add_argument("--upload-font", choices=("compact30", "small24", "progress24", "bar24"), default="compact30")
    parser.add_argument("--native-rect-sampling", action="store_true", help="Read-only 1ms nominal/4000-sample window without an active DDS slot")
    args = parser.parse_args()
    if args.native_rect_sampling and args.kind != "progress-sampler":parser.error("--native-rect-sampling requires progress-sampler")
    if args.upload_font != "compact30" and args.kind != "dds-edge-once":
        parser.error("--upload-font requires dds-edge-once")
    text_probe = args.kind in ("dds-text-once", "dds-edge-once")
    dds_probe = args.kind == "dds-once" or text_probe
    root = args.research.resolve()
    out = args.output.resolve()
    src = Path(__file__).resolve().parent
    libc = root / "evidence/camera-2.00-boot/lib__libc-2.11.2.so"
    linker = root / "tools/lld21/lld"
    for path in (libc, linker):
        if not path.is_file():
            parser.error("Missing dependency: " + str(path))
    verified = {}
    if args.kind in ("im-modules", "im-identity", "frame-context", "progress-sampler"):
        from audit_im_modules import IM, IMDB
        for relative, digest in (IM, IMDB, ("evidence/camera-2.00-boot/lib__libc-2.11.2.so",
                                 "2b294f4c256aebb2746cacddefc39c33c448a0d7f18c2813daa54109c445b910")):
            if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
                parser.error("Unverified module inventory dependency: " + relative)
            verified[relative] = digest
        if args.kind == "im-identity":
            relative = "evidence/camera-2.00-power/usr__lib__libosal_uipc.so"
            digest = "eecc322b81ebf63b26829fb2e8beee43af56f571b0ffbfc16d234dee5063becf"
            if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
                parser.error("Unverified OSAL library")
            verified[relative] = digest
    if args.kind in ("frame-context", "progress-sampler"):
        from audit_ui_contract import IMAGES
        relative, digest = IMAGES["obj"]
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
            parser.error("Unverified graphics image")
        verified[relative] = digest
    if args.kind.startswith("ui-"):
        expected = {
            "camera-2.00-obj/usr__lib__libObj.so":
                "ac07a5dfb140381bf95813a76794d83437726231a740928e590be8d4ea5dfdbd",
            "camera-2.00-ui-test-frontend/usr__bin__testcmd.elf":
                "dac753cfff36ab2e1c74a91a57874bd92f605e93046636bb232cb56d6d0291b1",
            "camera-2.00-ui-test-tools/usr__lib__libtestcmd.so":
                "ebd2afaab57d26a2e3d93637768a8bb2e0fd2467f4ccbcf27707b53a64545ad5",
        }
        for relative, digest in expected.items():
            path = root / "evidence" / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                parser.error("Unverified 2.00 dependency: " + str(path))
            verified[relative] = digest
    if dds_probe or args.kind == "redraw-once":
        expected = {
            "camera-2.00-obj/usr__lib__libObj.so": "ac07a5dfb140381bf95813a76794d83437726231a740928e590be8d4ea5dfdbd",
            "camera-2.00-power/usr__lib__libosal_uipc.so": "eecc322b81ebf63b26829fb2e8beee43af56f571b0ffbfc16d234dee5063becf",
            "camera-2.00-timer/usr__kmod__utimer.ko": "5e7e945f4d33789e3fc4d16ee625e94c4d55813038e8ffbdca7d594cc3d77c04",
            "camera-2.00-boot/lib__libc-2.11.2.so": "2b294f4c256aebb2746cacddefc39c33c448a0d7f18c2813daa54109c445b910",
            "camera-2.00-boot/lib__librt-2.11.2.so": "c50f058518dcae9ebb69141cb3b7f7f59d6278e4153020eca00b64ef197b8b40",
        }
        if args.kind == "redraw-once":
            expected.update({
                "camera-2.00-ui-test-frontend/usr__bin__testcmd.elf": "dac753cfff36ab2e1c74a91a57874bd92f605e93046636bb232cb56d6d0291b1",
                "camera-2.00-ui-test-tools/usr__lib__libtestcmd.so": "ebd2afaab57d26a2e3d93637768a8bb2e0fd2467f4ccbcf27707b53a64545ad5",
            })
        for relative, digest in expected.items():
            path = root / "evidence" / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                parser.error("Unverified 2.00 dependency: " + str(path))
            verified[relative] = digest
    source_name = {"ui-help": "ui_help", "ui-layout": "ui_layout", "framebuffer": "fb_info",
                   "detached-launch": "detached_launch", "ui-listener": "ui_listener",
                   "wireless-launch": "wireless_launch", "ui-layout-all": "ui_layout_all",
                   "ui-widgets-playback": "ui_widgets_playback", "dds-once": "dds_once",
                   "dds-text-once": "dds_text_once", "dds-edge-once": "dds_edge_once",
                   "dds-listener": "dds_wireless_listener", "dds-launch": "dds_wireless_launch", "dds-blink-launch": "dds_blink_launch",
                   "redraw-once": "redraw_once", "im-modules": "im_modules", "im-identity": "im_identity", "frame-context": "module/frame_context", "progress-sampler": "progress_sampler"}[args.kind]
    out.mkdir(parents=True, exist_ok=False)
    if args.kind == "frame-context":
        (out / "module").mkdir()
    generated = {}
    if text_probe:
        from audit_ui_contract import Image, IMAGES
        from audit_dds_text import audit
        from dds_text_plan import compile_text, compile_compact_upload
        image = Image(root / IMAGES["obj"][0], IMAGES["obj"][1])
        try:
            audit(image)
            if args.kind == "dds-edge-once":
                from audit_dds_edge import audit as audit_edge
                audit_edge(image)
            original = image.read(0x13eb2e0, 128)
        finally:
            image.stream.close()
        replacement, marker, _ = (compile_compact_upload() if args.kind == "dds-edge-once"
                                   else compile_text(["UPLOAD", "TEST"]))
        if args.kind == "dds-edge-once" and args.upload_font == "small24":
            from dds_small_text_plan import compile_upload_24
            replacement, marker = compile_upload_24()
        if args.kind == "dds-edge-once" and args.upload_font == "progress24":
            from dds_small_text_plan import compile_progress_24
            replacement, marker = compile_progress_24()
        if args.kind == "dds-edge-once" and args.upload_font == "bar24":
            from dds_small_text_plan import compile_progress_bar_24
            replacement, marker = compile_progress_bar_24()
        header = out / "dds_text_asset.h"
        header.write_text("/* Private build asset; generated from verified firmware. */\n" +
                          ("#define DDS_PROGRESS_EXPERIMENT 1\n" if args.upload_font in ("progress24", "bar24") else "") +
                          ("#define DDS_PROGRESS_BAR 1\n" if args.upload_font == "bar24" else "") +
                          "\n".join("static const unsigned char %s[%d]={%s};" %
                                    (name, len(data), ",".join(str(b) for b in data))
                                    for name, data in (("original_font", original),
                                                       ("replacement_font", replacement),
                                                       ("text_marker", marker))) + "\n")
        generated[header.name] = hashlib.sha256(header.read_bytes()).hexdigest()
    base = ["/opt/homebrew/opt/llvm/bin/clang", "--target=arm-linux-gnueabi",
            "-mcpu=cortex-a9", "-marm", "-mfloat-abi=soft", "-Os",
            "-Wall", "-Wextra", "-Werror", "-fno-stack-protector",
            "-fno-builtin", "-fno-pic", "-nostdlib", "-I", str(out)]
    if args.native_rect_sampling:base.append("-DNATIVE_RECT_SAMPLE")
    for name, source in (("startup", src.parents[1] / "maintenance/startup.S"),
                         (source_name, src / (source_name + ".c"))):
        subprocess.run(base + ["-c", str(source), "-o", str(out / (name + ".o"))], check=True)
    env = os.environ.copy()
    env["DYLD_LIBRARY_PATH"] = (str(root / "tools/lld21/lib") +
                               ":/opt/homebrew/opt/llvm/lib:/opt/homebrew/opt/zstd/lib")
    binary = out / ("fb-info" if args.kind == "framebuffer" else args.kind)
    libraries = [str(libc)]
    if dds_probe or args.kind in ("ui-listener", "dds-listener", "redraw-once", "progress-sampler"):
        libraries.append(str(root / "evidence/camera-2.00-boot/lib__librt-2.11.2.so"))
    if dds_probe or args.kind == "im-identity":
        libraries.insert(0, str(root / "evidence/camera-2.00-power/usr__lib__libosal_uipc.so"))
    subprocess.run([str(linker), "-flavor", "gnu", "-m", "armelf_linux_eabi",
                    "--hash-style=sysv", "-z", "noexecstack",
                    *(["-z", "nocombreloc"] if dds_probe or args.kind in ("redraw-once", "im-identity") else []),
                    "--dynamic-linker=/lib/ld-linux.so.3", "--allow-shlib-undefined",
                    "-e", "_start", str(out / "startup.o"), str(out / (source_name + ".o")),
                    *libraries, "-o", str(binary)], env=env, check=True)
    with binary.open("rb") as stream:
        elf = ELFFile(stream)
        assert elf["e_machine"] == "EM_ARM" and elf.elfclass == 32
        imports = sorted(s.name for s in elf.get_section_by_name(".dynsym").iter_symbols()
                         if s["st_shndx"] == "SHN_UNDEF" and s.name)
        allowed = ({"__libc_start_main", "alarm", "execv", "printf", "fflush"}
                   if args.kind.startswith("ui-") else
                   {"__libc_start_main", "__errno_location", "alarm", "open",
                    "close", "ioctl", "printf", "fflush"})
        if args.kind.endswith("-launch"):
            allowed = {"__libc_start_main", "fork", "setsid", "waitpid", "close",
                       "open", "dup2", "chdir", "execv", "_exit", "signal"}
        if args.kind in ("im-modules", "frame-context"):
            allowed = {"__libc_start_main", "alarm", "open", "close", "read", "pread",
                       "readlink", "printf", "snprintf", "sscanf", "strcmp", "memcmp", "memset", "strtoull"}
        if args.kind == "frame-context":
            allowed |= {"mmap64", "munmap", "usleep"}
        if args.kind == "im-identity":
            allowed = {"__libc_start_main", "alarm", "printf", "osal_snd_sync_direct", "memcpy"}
        if args.kind in ("ui-listener", "dds-listener"):
            allowed = {"__libc_start_main", "__errno_location", "fork", "waitpid",
                       "close", "open", "dup2", "execv", "_exit", "signal", "fcntl",
                       "socket", "bind", "listen", "accept", "setsockopt", "sscanf",
                       "htons", "inet_addr", "read", "write", "poll", "pipe",
                       "getpid", "snprintf", "strcmp", "strlen", "access", "unlink",
                       "usleep", "kill", "clock_gettime", "memset"}
            if args.kind == "dds-listener":
                allowed |= {"lseek", "memcpy"}
        if dds_probe or args.kind == "redraw-once":
            allowed = {"__libc_start_main", "open", "close", "pread", "read", "write",
                       "readlink", "printf", "fflush", "sscanf", "snprintf", "strcmp",
                       "strstr", "strlen", "strtoull", "atoi", "memcpy", "memset", "memcmp",
                       "usleep", "sleep", "clock_gettime", "pipe", "fork", "getpid",
                       "getppid", "poll", "kill", "_exit", "signal", "waitpid",
                       "access", "execv",
                       "osal_valloc_msg_wait", "osal_snd_msg", "osal_free_msg",
                       "osal_snd_sync_direct"}
            if dds_probe:
                allowed |= {"mmap64", "munmap", "__errno_location"}
            if args.kind == "redraw-once":
                allowed -= {"osal_valloc_msg_wait", "osal_snd_msg", "osal_free_msg", "osal_snd_sync_direct"}
                allowed |= {"pwrite", "execv"}
            if text_probe:
                allowed |= {"pwrite"}
        if args.kind == "progress-sampler":
            allowed = {"__libc_start_main", "open", "close", "pread", "readlink", "printf", "fflush",
                       "snprintf", "strcmp", "strtoull", "atoi", "mmap64", "munmap", "clock_gettime", "usleep", "_exit"}
        if args.native_rect_sampling:allowed.add("memset")
        assert set(imports) <= allowed, imports
    manifest = {
        "native_rect_sampling": args.native_rect_sampling,
        "scope": ("read-only<=20s/4000samples, nominal1ms native rectangle observation; no IPC/writes; not atomic LCD scanout" if args.native_rect_sampling else "read-only<=20s/1000samples: border values, native controls and redraw counter; no IPC/writes; not atomic LCD scanout"
                  if args.kind == "progress-sampler" else
                  "experimental fixed corner UPLOAD; shared RAM font and four coordinate bytes; not runtime validated"
                  if args.kind == "dds-edge-once" else
                  "experimental fixed UPLOAD / TEST shared RAM font replacement; guardian recovery; not runtime validated"
                  if args.kind == "dds-text-once" else
                  "experimental native redraw RAM countdown request; fixed UI query; not runtime validated"
                  if args.kind == "redraw-once" else
                  "experimental one-shot native numeric overlay; RAM only; independent cleanup; not runtime validated"
                  if args.kind == "dds-once" else
                  "temporary fixed collector launcher; no autostart"
                  if args.kind.endswith("-launch") else
                  "temporary authenticated STATUS/PROBE listener; fixed action script required"
                  if args.kind in ("ui-listener", "dds-listener") else
                  "native UI help or fixed layout/widget-list query; build does not verify runtime"
                  if args.kind.startswith("ui-") else
                  "read-only frame callback/context snapshot; no IPC, hook or process writes"
                  if args.kind == "frame-context" else
                  "read-only im module inventory; no IPC or process writes; not runtime verified"
                  if args.kind == "im-modules" else
                  "fixed read-only im identity request; no load/unload; not runtime verified"
                  if args.kind == "im-identity" else
                  "read-only framebuffer metadata; not a display overlay"),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256((src / (source_name + ".c")).read_bytes()).hexdigest(),
        "libc_sha256": hashlib.sha256(libc.read_bytes()).hexdigest(),
        "imports": imports,
        "verified_local_dependencies": verified,
        "generated_asset_sha256": generated,
        "upload_font": args.upload_font if args.kind == "dds-edge-once" else None,
    }
    included = {"ui-listener": [src.parent / "debugger/listener.c", src.parent / "uploader/compat.h"],
                "wireless-launch": [src / "detached_launch.c"],
                "dds-once": [src / "capture_mapping.h", src.parent / "uploader/compat.h"],
                "dds-text-once": [src / "dds_once.c", src / "dds_font_adapter.h",
                                  src / "font_transaction.h", src / "dds_text_plan.py", src / "capture_mapping.h",
                                  src.parent / "uploader/compat.h"],
                "redraw-once": [src.parent / "uploader/compat.h"]}.get(args.kind, [])
    if args.kind == "frame-context":
        included = [src / "im_modules.c", src / "module/native_phase_snapshot.h"]
    if args.kind == "progress-sampler":
        included = [src.parent / "uploader/compat.h"]
    if args.kind == "dds-edge-once":
        included = [src / name for name in ("dds_text_once.c", "dds_once.c",
                    "dds_font_adapter.h", "dds_position_adapter.h", "font_transaction.h",
                    "dds_text_plan.py", "capture_mapping.h")] + [src.parent / "uploader/compat.h"]
    if args.kind == "dds-edge-once" and args.upload_font in ("small24", "progress24", "bar24"):
        included.append(src / "dds_small_text_plan.py")
    if args.kind == "dds-edge-once" and args.upload_font in ("progress24", "bar24"):
        included.append(src.parent / "uploader/upload_progress.h")
    if args.kind == "dds-listener":
        included = [src.parent / "debugger/listener.c", src.parent / "uploader/compat.h",
                    src / "transfer_protocol.h", src.parent / "uploader/sha256.h"]
    if args.kind in ("dds-launch", "dds-blink-launch"):
        included = [src / "detached_launch.c"]
    if dds_probe:
        included += [src / "capture_physical.h", src / "upload_lifetime.h"]
    manifest["included_source_sha256"] = {str(p.relative_to(src.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in included}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Built display diagnostic:", binary)


if __name__ == "__main__":
    main()
