"""link_check - the per-PR internal-link gate (#913).

Fails a commit/PR when a Markdown or HTML doc links to something that isn't
there: a *relative* path that resolves to no tracked file, or a GitHub
*self-link* with a broken ref (the `/blob/HEAD/` class that produced the #908
error/404 pages). Runs in `pre-commit`, so it fires identically on a local
commit and in CI (`pre-commit run --all-files`) - the local==CI parity this
repo treats as load-bearing (#524).

Why uv-Python, not lychee (Workflow ruling on #913; cite #259/#524):
The GitHub-native link checker is `lychee`, and it earns its keep - but only
for what it uniquely does: *external* links, on the internet's rot schedule,
in `weekly-battery.yml`. The per-PR gate is *internal / relative / offline*,
which needs none of lychee's network machinery - and lychee is a Rust binary,
so wiring it into the local+CI gate would add an ambient Rust/Docker toolchain
this repo deliberately does without (#259, "no ambient compiler"; everything
runs through uv-Python or pinned node). So the internal gate follows the
established uv-native custom-check pattern (identifier_guard.py #558 is the
precedent): a stdlib-only `tools/dx/*.py` hook, zero new toolchain, offline.
That named toolchain gap is what justifies a custom check over the standard
tool here - recorded in ADR-0002 section 10.

Doctrine (#895, "prove the class is empty"): a single broken link is never a
one-off, it's a class. This gate is the automated form of that house rule for
the link class; see the DX review lens (docs/contributing/dx-review-lens.md).

Scope / non-goals (deliberate, per the #913 fence):
- Internal links only. External http(s) links are skipped (weekly lychee's).
- Site-absolute `/...` targets are the served dashboard's runtime routes
  (e.g. `/lab`, `/#capture`) - app-resolved, not repo paths - skipped.
- Template placeholders (`<!--__EID__-->`, `{{ }}`) are skipped.
- URL-encoded targets (`%20`) are decoded before resolving (.dc.html style).

Known-broken links tracked by another ticket live in link_check_allowlist.txt
(one "<file> -> <target>" key per line). Remove an entry when its fix lands.

    uv run python tools/dx/link_check.py            # report
    uv run python tools/dx/link_check.py --check    # non-zero on any finding
"""

from __future__ import annotations

import os
import posixpath
import re
import subprocess
import sys
from urllib.parse import unquote

SELF = "github.com/OrangePeachPink/sprout"

# Frozen design provenance - matches the pre-commit top-level exclude. (That
# exclude filters a hook's *filenames*; this hook scans the tree itself, so the
# prefix is replicated here.)
EXCLUDE_PREFIXES = ("docs/design/_archive/",)

SCHEME_SKIP = ("#", "mailto:", "tel:", "data:", "javascript:")
PLACEHOLDER_MARKERS = ("<!--", "-->", "{{", "}}")

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MD_REF = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)", re.M)
HTML_LINK = re.compile(r"(?:href|src)=\"([^\"]+)\"")
SELF_REF = re.compile(re.escape(SELF) + r"/(?:blob|tree|raw)/([^/]+)/(\S*)")

ALLOWLIST_PATH = os.path.join(os.path.dirname(__file__), "link_check_allowlist.txt")


def extract_links(text: str, is_html: bool) -> list:
    """Every link target in a doc (href/src for HTML; inline+ref for Markdown)."""
    if is_html:
        return HTML_LINK.findall(text)
    return MD_LINK.findall(text) + MD_REF.findall(text)


def check_link(srcfile: str, raw: str, tracked: set, tracked_dirs: set):
    """Return a finding dict for a broken internal link, else None.

    tracked / tracked_dirs are tracked file paths and their ancestor dirs.
    """
    t = raw.strip()
    if not t or t.startswith(SCHEME_SKIP):
        return None
    if any(m in t for m in PLACEHOLDER_MARKERS):
        return None
    if t.startswith("/"):  # served-dashboard runtime route, not a repo path
        return None
    if SELF in t:
        m = SELF_REF.search(t)
        if m:
            ref, path = m.group(1), unquote(m.group(2).split("#")[0].split("?")[0])
            if ref in ("HEAD", "master", ""):
                return {
                    "file": srcfile,
                    "target": raw,
                    "kind": "bad-ref (self-link missing/HEAD ref)",
                }
            if (
                ref == "main"
                and path
                and path not in tracked
                and path.rstrip("/") not in tracked_dirs
            ):
                return {
                    "file": srcfile,
                    "target": raw,
                    "kind": "missing-path (self-link /blob/main)",
                }
        return None  # non-blob self-links (/issues, /discussions) run-time
    if t.startswith(("http://", "https://")):
        return None  # external - weekly lychee's job, not this gate's
    tgt = unquote(t.split("#")[0].split("?")[0])
    if not tgt:
        return None
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(srcfile), tgt))
    if resolved in tracked or resolved in tracked_dirs:
        return None
    if any(x.startswith(resolved + "/") for x in tracked):
        return None
    return {"file": srcfile, "target": raw, "kind": "broken-relative"}


def find_findings(file_texts: dict, tracked: set, tracked_dirs: set) -> list:
    """All findings across a {srcfile: text} map. Pure - the unit-test seam."""
    out = []
    for srcfile, text in file_texts.items():
        is_html = srcfile.endswith(".html")
        for raw in extract_links(text, is_html):
            finding = check_link(srcfile, raw, tracked, tracked_dirs)
            if finding:
                out.append(finding)
    return out


def finding_key(f: dict) -> str:
    return f"{f['file']} -> {f['target']}"


def load_allowlist(path: str = ALLOWLIST_PATH) -> set:
    keys = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                s = line.strip()
                if s and not s.startswith("#"):
                    keys.add(s)
    return keys


def _git_tracked() -> list:
    r = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    return r.stdout.splitlines()


def scan_repo() -> list:
    """Scan the tracked tree; return findings (allowlist not yet applied)."""
    tracked_list = _git_tracked()
    tracked = set(tracked_list)
    tracked_dirs = set()
    for f in tracked_list:
        d = posixpath.dirname(f)
        while d:
            tracked_dirs.add(d)
            d = posixpath.dirname(d)
    texts = {}
    for f in tracked_list:
        if not f.endswith((".md", ".html")) or f.startswith(EXCLUDE_PREFIXES):
            continue
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                texts[f] = fh.read()
        except OSError:
            pass
    return find_findings(texts, tracked, tracked_dirs)


def main(argv: list) -> int:
    check = "--check" in argv
    allow = load_allowlist()
    findings = scan_repo()
    active = [f for f in findings if finding_key(f) not in allow]
    allowed = len(findings) - len(active)
    for f in active:
        print(f"  {f['kind']}: {finding_key(f)}")
    if allowed:
        print(f"  ({allowed} allowlisted - see tools/dx/link_check_allowlist.txt)")
    if active:
        print(
            f"link-check: {len(active)} broken internal link(s)."
            " Fix, or allowlist with a tracking ticket."
        )
        return 1 if check else 0
    print("link-check: no broken internal links.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
