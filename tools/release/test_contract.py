"""#1662 — the artifact contract, proved against deliberately broken releases.

`assets > 0` is what §5 had, and it passes on a release missing a signature. Every test
here is a release that WOULD have passed that check and must not pass this one.

The contract is pure by design so these need no GitHub. The counterpart proof — that it
also passes on a real signed release — is `just release-verify v0.8.1`, and it is
recorded on #1662 rather than run here: a unit test that reaches the network is a unit
test that fails on a plane.
"""

from __future__ import annotations

import hashlib
import json

from tools.release import contract as c

CLASSIC = "sprout-esp32-factory.bin"
C5 = "sprout-esp32c5-factory.bin"
MANIFEST = "manifest-esp32.json"

BIN = b"\x00factory image bytes\xff"
C5BIN = b"\x00c5 image bytes\xff"
SHA = hashlib.sha256(BIN).hexdigest()
C5SHA = hashlib.sha256(C5BIN).hexdigest()


def _blobs(**over: bytes) -> dict[str, bytes]:
    b = {
        CLASSIC: BIN,
        f"{CLASSIC}.sig": b"sig-classic",
        C5: C5BIN,
        f"{C5}.sig": b"sig-c5",
        MANIFEST: json.dumps(_manifest()).encode(),
        c.SUMS: _sums().encode(),
    }
    b.update(over)
    return b


def _sums(**over: str) -> str:
    rows = {
        CLASSIC: SHA,
        f"{CLASSIC}.sig": hashlib.sha256(b"sig-classic").hexdigest(),
        C5: C5SHA,
        f"{C5}.sig": hashlib.sha256(b"sig-c5").hexdigest(),
        MANIFEST: hashlib.sha256(json.dumps(_manifest()).encode()).hexdigest(),
    }
    rows.update(over)
    return "# sprout v1.2.3\n" + "".join(f"{v}  {k}\n" for k, v in rows.items())


def _manifest(**over) -> dict:
    m = {
        "version": "1.2.3",
        "builds": [{"chipFamily": "ESP32"}],
        "provenance": {
            "artifact": CLASSIC,
            "sha256": SHA,
            "git": "abc1234",
            "channel": "stable",
            "release_tag": "v1.2.3",
        },
    }
    m["provenance"].update(over.pop("provenance", {}))
    m.update(over)
    return m


# ---- inventory -----------------------------------------------------------------


def test_a_complete_release_passes() -> None:
    assert c.check_inventory(set(_blobs())).passed


def test_a_missing_signature_fails() -> None:
    """THE case `assets > 0` waves through: five assets, one of them the signature."""
    names = set(_blobs()) - {f"{CLASSIC}.sig"}
    r = c.check_inventory(names)
    assert not r.passed and "missing asset" in r.failures[0]
    assert f"{CLASSIC}.sig" in r.failures[0]


def test_the_c5_is_still_required_though_it_is_not_web_flashable() -> None:
    """ADR-0026 D6 governs BROWSER flashing, not the release inventory.

    The C5 has no web manifest and is not offered from the flasher — and its signed bin
    still ships and still flashes via pio/esptool. A contract keyed on
    WEB_FLASH_VERIFIED would stop verifying it entirely, which is worse than the
    uniform check it replaces.
    """
    r = c.check_inventory(set(_blobs()) - {C5})
    assert not r.passed and C5 in r.failures[0]


def test_the_c5_needs_no_web_manifest() -> None:
    """The other half: absent-by-design must not read as missing."""
    assert "manifest-esp32c5.json" not in c.expected_assets()
    assert c.check_inventory(set(_blobs())).passed


def test_an_unexpected_asset_fails() -> None:
    """An extra unsigned .bin is exactly what a count-based check cannot see."""
    r = c.check_inventory(set(_blobs()) | {"sprout-esp32s3-factory.bin"})
    assert not r.passed and "unexpected asset" in r.failures[0]


# ---- checksums -----------------------------------------------------------------


def test_sums_must_cover_every_asset() -> None:
    sums = c.parse_sums(_sums())
    del sums[f"{C5}.sig"]
    r = c.check_sums_cover(sums)
    assert not r.passed and f"{C5}.sig" in r.failures[0]


def test_bytes_that_disagree_with_the_receipt_fail() -> None:
    """A receipt that describes different bytes is worse than no receipt."""
    r = c.check_bytes(_blobs(**{CLASSIC: b"different"}), c.parse_sums(_sums()), {})
    assert not r.passed and "!=" in r.failures[0]


def test_a_manifest_claiming_the_wrong_sha_fails() -> None:
    """The three-way check. SHA256SUMS and the bytes can agree while the manifest —
    the thing the flasher actually reads — was generated from a different build."""
    m = _manifest(provenance={"sha256": "0" * 64})
    r = c.check_bytes(_blobs(), c.parse_sums(_sums()), {MANIFEST: m})
    assert not r.passed and "claims" in r.failures[0]


def test_a_manifest_naming_an_absent_artifact_fails() -> None:
    m = _manifest(provenance={"artifact": "sprout-ghost-factory.bin"})
    r = c.check_bytes(_blobs(), c.parse_sums(_sums()), {MANIFEST: m})
    assert not r.passed and "not in the release" in r.failures[0]


# ---- labels: the #1630 defect --------------------------------------------------


def test_a_labelled_release_passes() -> None:
    assert c.check_manifest_labels(MANIFEST, _manifest(), "v1.2.3", "abc1234").passed


def test_an_alpha_suffix_on_a_release_fails() -> None:
    """#1630, and the reason #1664 exists.

    EVERY v0.8.1 release build labelled itself `-alpha` because the signing checkout
    could not see its own tag. It was caught by eye on the real draft, one click from
    immutable — the §5.1 dry run is blind to it by construction, because a throwaway
    tag is legitimately alpha.
    """
    r = c.check_manifest_labels(
        MANIFEST, _manifest(version="1.2.3-alpha"), "v1.2.3", "abc1234"
    )
    assert not r.passed and "pre-release suffix" in r.failures[0]


def test_an_alpha_channel_on_a_release_fails() -> None:
    r = c.check_manifest_labels(
        MANIFEST, _manifest(provenance={"channel": "alpha"}), "v1.2.3", "abc1234"
    )
    assert not r.passed and "channel" in r.failures[0]


def test_an_empty_release_tag_fails() -> None:
    """The build not knowing its own tag is the root cause, not just a symptom."""
    r = c.check_manifest_labels(
        MANIFEST, _manifest(provenance={"release_tag": None}), "v1.2.3", "abc1234"
    )
    assert not r.passed and "did not know its own tag" in r.failures[0]


def test_provenance_from_a_different_commit_fails() -> None:
    """A retarget always implies a re-sign (§5.0).

    Retargeting leaves the old assets attached, and they now describe a commit the
    release does not point at — not merely stale, actively misdescribing it.
    """
    r = c.check_manifest_labels(MANIFEST, _manifest(), "v1.2.3", "deadbee")
    assert not r.passed and "does not point at" in r.failures[0]


# ---- the body ------------------------------------------------------------------


def test_a_stray_mention_fails() -> None:
    """v0.8.1's real one: schema.org's `@id` in a PR title became a live mention of an
    unrelated user, who was then listed as a release contributor. The body stays
    editable; the notification fires once."""
    r = c.check_body("- Person @id mirror by @realdev in #1495", {"realdev"})
    assert not r.passed and "@id" in r.failures[0]


def test_backticked_at_signs_are_not_mentions() -> None:
    """GitHub does not notify from code spans, and neither do we — a check that cries
    wolf on `@media` is one the operator learns to skim."""
    assert c.check_body("uses `@media` and ```@decorator``` freely", set()).passed


def test_real_participants_are_not_flagged() -> None:
    """Auto-generated notes read 'by @someone in #123'. Flagging every merger would
    train the operator to ignore the check — which is how a real stray gets through."""
    body = "* fix things by @OrangePeachPink in #1\n* bump by @dependabot in #2"
    allowed = {"orangepeachpink"} | {b.lower() for b in c.BOT_HANDLES}
    assert c.check_body(body, allowed).passed


def test_an_email_is_not_a_mention() -> None:
    assert c.check_body("reach us at hello@example.com", set()).passed
