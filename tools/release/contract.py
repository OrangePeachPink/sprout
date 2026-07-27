#!/usr/bin/env python3
"""#1662 — the exact artifact contract a signed release must satisfy.

`RELEASE_CUT` §5 asserted `assets > 0`. That passes on a release missing a signature,
and at the v0.8.1 cut the real inventory was checked by hand with ad-hoc Python **three
times**, once per signing cycle.

**A declared table, never `assets > 0`.** Adding a board to a release is a deliberate
edit here — the same doctrine the guard family runs on. An unexpected asset fails just
as loudly as a missing one: an extra unsigned `.bin` on a signed release is exactly the
thing a count-based check waves through.

**`WEB_FLASH_VERIFIED` does NOT define this inventory.** That set governs *browser*
flashability (ADR-0026 D6; the C5 is pulled pending #1606). The C5 is still a
first-class release artifact — its signed bin ships and flashes via `pio`/`esptool`. A
contract keyed on web-verification would silently stop verifying the C5 altogether,
which is a worse failure than the uniform check it replaces.

Everything here is PURE: it takes an inventory, a manifest and a body, and returns
findings. The network lives in `verify.py`, so the contract can be tested against
hand-built broken releases without inventing a GitHub.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

SUMS = "SHA256SUMS"


@dataclass(frozen=True)
class Board:
    """One board class's release obligations.

    `web_manifest` is None for a board that ships a signed bin but is not offered from
    the browser — that is a real, supported state, not an omission.
    """

    key: str
    bin_name: str
    web_manifest: str | None

    @property
    def sig_name(self) -> str:
        return f"{self.bin_name}.sig"


BOARDS: tuple[Board, ...] = (
    Board("esp32", "sprout-esp32-factory.bin", "manifest-esp32.json"),
    # C5: signed and shipped, deliberately NO web manifest (ADR-0026 D6, #1606).
    Board("esp32c5", "sprout-esp32c5-factory.bin", None),
)


def expected_assets(boards: tuple[Board, ...] = BOARDS) -> set[str]:
    """Every asset name a complete release carries — including SHA256SUMS itself."""
    names = {SUMS}
    for b in boards:
        names.add(b.bin_name)
        names.add(b.sig_name)
        if b.web_manifest:
            names.add(b.web_manifest)
    return names


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    def ok(self, what: str) -> None:
        self.checked.append(what)

    def fail(self, what: str) -> None:
        self.failures.append(what)

    @property
    def passed(self) -> bool:
        return not self.failures


def check_inventory(names: set[str], boards: tuple[Board, ...] = BOARDS) -> Report:
    """The inventory is EXACT — missing and unexpected both fail."""
    r = Report()
    want = expected_assets(boards)
    missing = sorted(want - names)
    extra = sorted(names - want)
    if missing:
        r.fail(f"missing asset(s): {', '.join(missing)}")
    if extra:
        r.fail(
            f"unexpected asset(s): {', '.join(extra)} — the contract is a declared "
            "table (tools/release/contract.py); adding a board is a deliberate edit, "
            "not something a release discovers at sign time"
        )
    if not missing and not extra:
        r.ok(f"inventory exact ({len(want)} assets)")
    return r


def parse_sums(text: str) -> dict[str, str]:
    """`sha256  name` lines -> {name: sha}.

    Comment lines are skipped, exactly as coreutils does.
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            out[parts[-1]] = parts[0].lower()
    return out


def check_sums_cover(
    sums: dict[str, str], boards: tuple[Board, ...] = BOARDS
) -> Report:
    """SHA256SUMS must cover every expected asset except itself."""
    r = Report()
    want = expected_assets(boards) - {SUMS}
    missing = sorted(want - set(sums))
    if missing:
        r.fail(f"{SUMS} does not cover: {', '.join(missing)}")
    else:
        r.ok(f"{SUMS} covers all {len(want)} assets")
    return r


def check_bytes(
    blobs: dict[str, bytes], sums: dict[str, str], manifests: dict[str, dict]
) -> Report:
    """The three-way agreement: real bytes == SHA256SUMS == the manifest's claim.

    Any two agreeing is not enough. A manifest can be regenerated from a stale bin, and
    SHA256SUMS can be written from a different build than the one uploaded — the whole
    point of a receipt is that all three describe one artifact.
    """
    r = Report()
    for name, blob in sorted(blobs.items()):
        actual = hashlib.sha256(blob).hexdigest()
        claimed = sums.get(name)
        if claimed is None:
            continue  # covered by check_sums_cover
        if actual != claimed:
            r.fail(f"{name}: bytes sha256 {actual[:12]}… != {SUMS} {claimed[:12]}…")
        else:
            r.ok(f"{name}: bytes match {SUMS}")
    for mname, m in sorted(manifests.items()):
        prov = m.get("provenance", {}) or {}
        artifact, want_sha = prov.get("artifact"), (prov.get("sha256") or "").lower()
        if not artifact or not want_sha:
            r.fail(f"{mname}: provenance has no artifact/sha256 to check")
            continue
        if artifact not in blobs:
            r.fail(f"{mname}: names artifact {artifact!r}, which is not in the release")
            continue
        actual = hashlib.sha256(blobs[artifact]).hexdigest()
        if actual != want_sha:
            r.fail(
                f"{mname}: claims {artifact} sha256 {want_sha[:12]}…, bytes are "
                f"{actual[:12]}…"
            )
        else:
            r.ok(f"{mname}: manifest sha256 matches {artifact}")
    return r


def check_manifest_labels(mname: str, m: dict, tag: str, target: str) -> Report:
    """The #1630 defect, made unmissable.

    Every v0.8.1 release build labelled itself `-alpha` because the signing checkout
    could not see its own tag. It was caught by eye on the real draft, one click from
    immutable.
    """
    r = Report()
    version = str(m.get("version", ""))
    prov = m.get("provenance", {}) or {}
    if not version:
        r.fail(f"{mname}: no version")
    elif "-" in version:
        r.fail(
            f"{mname}: version {version!r} carries a pre-release suffix — a RELEASE "
            "build must label itself bare (#1630)"
        )
    else:
        r.ok(f"{mname}: version {version} is bare")

    channel = prov.get("channel")
    if channel != "stable":
        r.fail(f"{mname}: channel is {channel!r}, expected 'stable'")
    else:
        r.ok(f"{mname}: channel stable")

    rel_tag = prov.get("release_tag")
    if not rel_tag:
        r.fail(f"{mname}: release_tag is empty — the build did not know its own tag")
    elif rel_tag != tag:
        r.fail(f"{mname}: release_tag {rel_tag!r} != the release's tag {tag!r}")
    else:
        r.ok(f"{mname}: release_tag {tag}")

    git = str(prov.get("git", ""))
    if not git:
        r.fail(f"{mname}: provenance has no git rev")
    elif not target:
        r.fail(f"{mname}: cannot check provenance.git — the draft's target is unknown")
    elif not (target.startswith(git) or git.startswith(target)):
        r.fail(
            f"{mname}: provenance.git {git!r} is not the draft's target "
            f"{target[:12]!r} "
            "— the assets describe a commit this release does not point at (a retarget "
            "always implies a re-sign)"
        )
    else:
        r.ok(f"{mname}: provenance.git matches target {git}")
    return r


# A live mention needs an @ that is NOT already inside code/backticks, not part of an
# email or path. Same shape as the RELEASE_CUT §4 recipe, which found `@id` in a PR
# title rendering as a stranger's handle — and listing them as a release contributor.
_MENTION = re.compile(r"(?:^|[^`\w/@])@([A-Za-z0-9][-A-Za-z0-9]*)")

# Handles that legitimately appear in auto-generated notes. Auto-generated bodies read
# "by @someone in #123", so people who actually merged work are EXPECTED mentions —
# flagging them would train the operator to ignore this check, which is how a real stray
# gets through. Declared rather than inferred; extended per run via --allow-mention.
BOT_HANDLES = frozenset({"dependabot", "github-actions", "copilot"})


def find_mentions(body: str, allowed: set[str]) -> list[str]:
    """Handles the body would notify. Backticked text is skipped, as GitHub does."""
    stripped = re.sub(r"`[^`]*`", "", body)
    stripped = re.sub(r"```.*?```", "", stripped, flags=re.S)
    return sorted({m for m in _MENTION.findall(stripped) if m.lower() not in allowed})


def check_body(body: str, allowed: set[str]) -> Report:
    """A body's notifications fire ONCE. The body stays editable; they do not."""
    r = Report()
    stray = find_mentions(body, {a.lower() for a in allowed})
    if stray:
        r.fail(
            "release body would notify: "
            + ", ".join(f"@{s}" for s in stray)
            + " — backtick anything that is not a real participant, then fix the PR "
            "title at the source or the next regeneration reintroduces it (#1639)"
        )
    else:
        r.ok("no unintended @mentions in the body")
    return r


def merge(*reports: Report) -> Report:
    out = Report()
    for r in reports:
        out.failures.extend(r.failures)
        out.checked.extend(r.checked)
    return out
