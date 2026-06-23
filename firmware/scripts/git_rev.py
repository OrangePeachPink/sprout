# pre-build: inject the git revision (+ "+dirty") as the compile-time string macro
# GIT_REV, so each firmware image and its log header name the exact source commit.
# Falls back to "nogit" if git is unavailable or this isn't a repo. (PlatformIO
# runs this in its own Python env; cross-platform.)
import subprocess

Import("env")  # noqa: F821 - provided by PlatformIO/SCons


def _git(args):
    return subprocess.check_output(["git"] + args, stderr=subprocess.DEVNULL).decode().strip()


try:
    rev = _git(["rev-parse", "--short", "HEAD"])
    try:
        # Non-zero exit => working tree differs from HEAD (staged or unstaged).
        subprocess.check_call(["git", "diff", "--quiet", "HEAD"], stderr=subprocess.DEVNULL)
        dirty = ""
    except subprocess.CalledProcessError:
        dirty = "+dirty"
    git_rev = rev + dirty
except Exception:
    git_rev = "nogit"

env.Append(CPPDEFINES=[("GIT_REV", env.StringifyMacro(git_rev))])  # noqa: F821
print("git_rev.py: GIT_REV = %s" % git_rev)
