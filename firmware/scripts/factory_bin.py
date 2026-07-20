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


# --- release channel + label (#1334) ----------------------------------------
# An alpha build is a build of `main` between releases. Today it inherits
# PLANTS_FW_VERSION wholesale, so bytes that are NOT the 0.8.1 release still
# present themselves as "0.8.1" - and a bug report then names a version that
# doesn't identify what was running. That is the drift #1334 closes.
#
# STABLE is not a claim a build gets to make about itself: it requires HEAD to be
# exactly a release tag AND the tree to be clean. Everything else is alpha, and an
# alpha label is built so it CANNOT be mistaken for a release - the "-alpha+<sha>"
# suffix is structural, not cosmetic, so the exact commit always travels and no
# bare release version can appear on a non-release build.
def channel_label(fw_version, exact_tag, dirty):
    """(channel, version_label) from the config version + git state. Pure - the
    git calls live in the caller so this is testable without a repo."""
    if exact_tag and not dirty:
        return "stable", exact_tag.lstrip("v")
    suffix = "-alpha"
    if dirty:
        suffix = "-alpha-dirty"
    return "alpha", f"{fw_version}{suffix}"


def _exact_tag(root):
    """The release tag HEAD points AT, or None. --exact-match means a commit that
    merely descends from a tag is NOT that release."""
    try:
        return (
            subprocess.check_output(
                ["git", "describe", "--tags", "--exact-match"],
                cwd=root,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
            or None
        )
    except (OSError, subprocess.CalledProcessError):
        return None


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


# mcu (BoardConfig build.mcu) -> (esptool --chip, ESP Web Tools chipFamily).
CHIP_MAP = {
    "esp32": ("esp32", "ESP32"),
    "esp32c5": ("esp32c5", "ESP32-C5"),
    "esp32s3": ("esp32s3", "ESP32-S3"),
}

# ADR-0026 Decision 6: only a BENCH-VERIFIED board is offered on the web flasher.
# Default-deny - a board absent here builds a factory bin but gets NO manifest, so the
# doc-only BOARDS.md do-not-flash rule (relay/pump-pin safety) becomes mechanical. The
# bring-up DoD's "add to web flasher" step = add the mcu here once it is bench-verified.
#
# C5 PULLED (#271 bench, 2026-07-11): ESP Web Tools 10.0.0 can't drive the ESP32-C5's
# native-USB flash - "Failed to initialize" at the sync step even with BOOT physically
# held, while esptool/pio flashes the SAME board fine on the same cable + host. So the
# C5 web-flash is NOT verified. Re-add "esp32c5" once EWT is bumped to a C5-supporting
# version and re-verified on the bench; the C5 keeps its documented pio-flash path.
WEB_FLASH_VERIFIED = {"esp32"}  # classic only (C5 pulled - see above)


def make_factory(source, target, env):
    # Never distribute the watchdog wedge-test build.
    if any("WDT_WEDGE_TEST" in str(f) for f in env.get("BUILD_FLAGS", [])):
        return

    mcu = env.BoardConfig().get("build.mcu", "esp32")
    chip, chip_family = CHIP_MAP.get(mcu, (mcu, mcu.upper()))

    build_dir = env.subst("$BUILD_DIR")
    app_bin = os.path.join(build_dir, env.subst("$PROGNAME") + ".bin")
    factory = os.path.join(build_dir, f"sprout-{mcu}-factory.bin")

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
            f'"$PYTHONEXE" "{esptool}" --chip {chip} merge_bin -o "{factory}" '
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

    # Verified-marker gate (ADR-0026 D6): an unverified board's bin is built (a harmless
    # artifact) but gets NO web-flasher manifest - it is never offered from a browser.
    if mcu not in WEB_FLASH_VERIFIED:
        print(
            f"[factory] {mcu}: NOT bench-verified -> factory bin built, NO manifest "
            f"(ADR-0026 D6 verified-marker; do-not-flash held mechanical)"
        )
        return

    root = env.subst("$PROJECT_DIR")
    rev = _git_rev()
    channel, version_label = channel_label(
        _fw_version(), _exact_tag(root), rev.endswith("+dirty")
    )

    manifest = {
        "name": "Sprout",
        "version": version_label,
        "new_install_prompt_erase": True,
        "builds": [
            {
                "chipFamily": chip_family,
                "parts": [{"path": os.path.basename(factory), "offset": 0}],
            }
        ],
        # Extra fields (ESP Web Tools ignores them); the flasher page reads these to
        # show real provenance BEFORE Install (#271, Design ask).
        "provenance": {
            "artifact": os.path.basename(factory),
            "board": mcu,
            "sha256": digest,
            "bytes": size,
            "git": rev,
            # #1334: the channel is explicit, never inferred from the version
            # string. `release_tag` is None on alpha - a consumer that wants "is
            # this a release?" asks this, not a regex over the label.
            "channel": channel,
            "release_tag": _exact_tag(root),
        },
    }
    manifest_path = os.path.join(build_dir, f"manifest-{mcu}.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(
        f"ESP Web Tools manifest ({chip_family}, {channel} {version_label}) -> "
        f"{manifest_path}  (sha256 {digest[:12]}...)"
    )


env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", make_factory)  # noqa: F821
