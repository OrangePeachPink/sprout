#
# factory_bin.py - PlatformIO post-build (#271, web-flasher / PRD-0005).
#
# Merges bootloader + partitions + boot_app0 + the app into ONE "factory" image that
# ESP Web Tools flashes at offset 0 from a browser (Chrome/Edge) - no Arduino IDE - and
# emits the matching ESP Web Tools manifest.json next to it. Both land in the build dir:
#   .pio/build/esp32dev/sprout-esp32-factory.bin
#   .pio/build/esp32dev/manifest.json
# DX hosts these on the flasher page (the binary is a release artifact, not committed).
#
# Uses the same esptool (tool-esptoolpy) the upload already uses, so the merge matches a
# real flash exactly. Skips the wedge test build - that image is never distributed.
#
import hashlib
import json
import os
import re
import subprocess

Import("env")  # noqa: F821 - injected by PlatformIO


def _fw_version():
    """Read PLANTS_FW_VERSION from include/config.h so the manifest never drifts."""
    cfg = os.path.join(env.subst("$PROJECT_DIR"), "include", "config.h")  # noqa: F821
    try:
        with open(cfg, encoding="utf-8") as fh:
            m = re.search(r'PLANTS_FW_VERSION\[\]\s*=\s*"([^"]+)"', fh.read())
        return m.group(1) if m else "0.0.0"
    except OSError:
        return "0.0.0"


def _git_rev():
    """Short HEAD (+ "+dirty") for provenance - mirrors scripts/git_rev.py."""
    root = env.subst("$PROJECT_DIR")  # noqa: F821
    try:
        rev = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=root,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        dirty = (
            subprocess.call(
                ["git", "diff", "--quiet"], cwd=root, stderr=subprocess.DEVNULL
            )
            != 0
        )
        return rev + ("+dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def make_factory(source, target, env):
    # Never distribute the watchdog wedge-test build.
    if any("WDT_WEDGE_TEST" in str(f) for f in env.get("BUILD_FLAGS", [])):
        return

    build_dir = env.subst("$BUILD_DIR")
    app_bin = os.path.join(build_dir, env.subst("$PROGNAME") + ".bin")
    factory = os.path.join(build_dir, "sprout-esp32-factory.bin")

    # bootloader / partitions / boot_app0, each at its flash offset, then the app.
    parts = []
    for offset, image in env.get("FLASH_EXTRA_IMAGES", []):
        parts += [str(offset), env.subst(image)]
    app_offset = env.subst(env.BoardConfig().get("upload.offset_address", "0x10000"))
    parts += [app_offset, app_bin]

    flash_mode = env.BoardConfig().get("build.flash_mode", "dio")
    flash_size = env.BoardConfig().get("upload.flash_size", "4MB")
    esptool = os.path.join(
        env.PioPlatform().get_package_dir("tool-esptoolpy") or "", "esptool.py"
    )

    part_args = " ".join(f'"{p}"' for p in parts)
    env.Execute(
        env.VerboseAction(
            f'"$PYTHONEXE" "{esptool}" --chip esp32 merge_bin -o "{factory}" '
            f"--flash_mode {flash_mode} --flash_size {flash_size} {part_args}",
            f"Building ESP Web Tools factory image -> {os.path.basename(factory)}",
        )
    )

    # SHA256 + size of the EXACT image the user flashes - real provenance for the page.
    with open(factory, "rb") as fh:
        data = fh.read()
    digest = hashlib.sha256(data).hexdigest()
    size = len(data)

    # Standard checksum sidecar (release-attachable; `sha256sum -c`-friendly).
    with open(factory + ".sha256", "w", encoding="utf-8") as fh:
        fh.write(f"{digest}  {os.path.basename(factory)}\n")

    manifest = {
        "name": "Sprout",
        "version": _fw_version(),
        "new_install_prompt_erase": True,
        "builds": [
            {
                "chipFamily": "ESP32",
                "parts": [{"path": "sprout-esp32-factory.bin", "offset": 0}],
            }
        ],
        # Extra fields (ESP Web Tools ignores them); the flasher page reads these to
        # show real provenance BEFORE Install (#271, Design ask).
        "provenance": {
            "artifact": os.path.basename(factory),
            "sha256": digest,
            "bytes": size,
            "git": _git_rev(),
        },
    }
    manifest_path = os.path.join(build_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"ESP Web Tools manifest -> {manifest_path}  (sha256 {digest[:12]}...)")


env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", make_factory)  # noqa: F821
