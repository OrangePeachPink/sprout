# pre-build: inject the build's IDENTITY as compile-time string macros, so each
# firmware image and its log header name the exact source it came from.
#
#   GIT_REV              commit hash (+ "+dirty")
#   PLANTS_BUILD_CHANNEL "stable" | "alpha"        (#1614)
#   PLANTS_BUILT_UTC     ISO-8601 UTC build stamp  (#1614)
#
# #1614: version + commit alone could not distinguish "the stable v0.8.0 release"
# from "an alpha build sitting on a commit tagged 0.8.0". On the #1334 B3 bench the
# honest answer was alpha and nothing on the wire said so, which makes the release-
# channel doctrine unverifiable at the device: a channel that cannot be read back is
# a claim, not a fact. These two macros are stamped by the build that PRODUCES the
# artifact, so they cannot drift from how the image was actually made.
#
# The channel rule is NOT re-implemented here - it is imported from build_channel.py,
# the same definition factory_bin.py stamps into the web-flasher manifest. One rule,
# two consumers; the manifest and the board can never disagree.
#
# Falls back to "nogit" if git is unavailable or this isn't a repo. (PlatformIO runs
# this in its own Python env; cross-platform.)
import datetime
import os
import re
import subprocess
import sys

Import("env")  # noqa: F821 - provided by PlatformIO/SCons

# PlatformIO execs extra_scripts WITHOUT setting __file__, so the sibling module is
# located via $PROJECT_DIR (which the build always provides) rather than this file's
# own path. Learned the hard way: __file__ here is a NameError at build time.
sys.path.insert(0, os.path.join(env.subst("$PROJECT_DIR"), "scripts"))  # noqa: F821
from build_channel import channel_label  # noqa: E402


def _git(args):
    return (
        subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)
        .decode()
        .strip()
    )


try:
    rev = _git(["rev-parse", "--short", "HEAD"])
    try:
        # Non-zero exit => working tree differs from HEAD (staged or unstaged).
        subprocess.check_call(
            ["git", "diff", "--quiet", "HEAD"], stderr=subprocess.DEVNULL
        )
        dirty = False
    except subprocess.CalledProcessError:
        dirty = True
    git_rev = rev + ("+dirty" if dirty else "")
except Exception:
    git_rev = "nogit"
    dirty = True  # an unknown tree is never treated as a clean release tree


def _exact_tag():
    """The release tag HEAD points AT, or None. --exact-match means a commit that
    merely DESCENDS from a tag is not that release."""
    try:
        return _git(["describe", "--tags", "--exact-match"]) or None
    except Exception:
        return None


def _fw_version():
    """PLANTS_FW_VERSION from include/config.h - the same source the manifest reads."""
    cfg = os.path.join(env.subst("$PROJECT_DIR"), "include", "config.h")  # noqa: F821
    try:
        with open(cfg, encoding="utf-8") as fh:
            m = re.search(r'PLANTS_FW_VERSION\[\]\s*=\s*"([^"]+)"', fh.read())
        return m.group(1) if m else "0.0.0"
    except OSError:
        return "0.0.0"


channel, _label = channel_label(_fw_version(), _exact_tag(), dirty)

# FAIL CLOSED (#1614 AC4). Defaulting an unknown channel to "stable" is exactly how
# an alpha build comes to call itself a release - the trusted value is never the safe
# default. If the rule ever returns something unusable, stop the build rather than
# ship an image that misidentifies itself.
if channel not in ("stable", "alpha"):
    raise SystemExit(
        f"git_rev.py: refusing to build - build channel is {channel!r}, expected "
        "'stable' or 'alpha'. An unset channel must never default to stable (#1614)."
    )

# Stamped once, here, at build time - not read from the clock at runtime (a board with
# no RTC would invent one) and not derived from __DATE__/__TIME__, which are the
# compiler's LOCAL time and therefore not comparable across machines.
built_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

env.Append(  # noqa: F821
    CPPDEFINES=[
        ("GIT_REV", env.StringifyMacro(git_rev)),  # noqa: F821
        ("PLANTS_BUILD_CHANNEL", env.StringifyMacro(channel)),  # noqa: F821
        ("PLANTS_BUILT_UTC", env.StringifyMacro(built_utc)),  # noqa: F821
    ]
)
print(f"git_rev.py: GIT_REV = {git_rev}  channel = {channel}  built_utc = {built_utc}")
