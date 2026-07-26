"""#1648: the two flasher channels must serve DIFFERENT bytes, from different sources.

Before this, `pages.yml` built current `main` once and wrote it under both names, so
the default CTA — no checkbox, the thing a stranger clicks — served an UNSIGNED build
that existed in no release and labelled itself alpha. Measured post-v0.8.1: the front
door served `0.8.1-alpha` sha bcba7293..., the release carried `0.8.1` sha ec0b98d6....

These are the three properties that keep the channels honest. They are asserted against
declared facts (the workflow text, the page markup, the combiner's behaviour) rather
than a live fetch, so a refactor that quietly re-merges the channels fails here.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pages"))

from build_flash_manifest import combine

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "pages.yml"
PAGE = REPO / "docs" / "flash" / "index.html"


def _manifest(tmp_path: Path, name: str = "manifest-esp32.json") -> str:
    p = tmp_path / name
    p.write_text(
        '{"name": "Sprout", "version": "0.8.1", "provenance": {"git": "abc1234"},'
        ' "builds": [{"chipFamily": "ESP32", "parts":'
        ' [{"path": "sprout-esp32-factory.bin", "offset": 0}]}]}',
        encoding="utf-8",
    )
    return str(p)


def test_parts_prefix_repoints_a_manifest_at_its_own_payload(tmp_path: Path) -> None:
    """Both channels emit the SAME bin filenames, so only one can win at flash/<name>.

    ESP Web Tools resolves `parts[].path` relative to the manifest URL, and the page
    fetches both manifests from flash/. The prefix is what lets stable's manifest stay
    at ./manifest.json while its bytes live in flash/stable/.
    """
    src = _manifest(tmp_path)
    plain = combine(src, [])
    prefixed = combine(src, [], parts_prefix="stable/")

    assert plain["builds"][0]["parts"][0]["path"] == "sprout-esp32-factory.bin"
    assert (
        prefixed["builds"][0]["parts"][0]["path"] == "stable/sprout-esp32-factory.bin"
    )
    # The offset must survive untouched — rewriting a flash offset would brick a board.
    assert prefixed["builds"][0]["parts"][0]["offset"] == 0


def test_stable_is_downloaded_from_the_release_not_rebuilt_from_main() -> None:
    """The whole defect in one assertion: stable's source is a release, not a build."""
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert "gh release download" in wf, (
        "the stable channel must fetch the release's signed assets; if this is gone, "
        "stable is being rebuilt from main again (#1648)"
    )
    assert "sha256sum -c SHA256SUMS" in wf, (
        "downloaded assets must be verified against the release's own receipt"
    )
    # The alpha manifest is the ONLY thing the from-main build may write. If a second
    # --out ever names manifest.json off the pio build, the channels have re-merged.
    from_main = wf.split("#1648")[0]
    assert '--out "$site/flash/manifest.json"' not in from_main


def test_neither_channel_is_offered_before_it_is_published() -> None:
    """A button that 404s teaches the reader the page lies.

    Alpha has always been gated on its manifest fetching. #1648 makes stable symmetric:
    fail-closed on the server (no release assets -> no manifest) is only honest if the
    page also declines to offer the channel.
    """
    page = PAGE.read_text(encoding="utf-8")
    assert 'id="stable-gate" hidden' in page, (
        "the stable Install button must start hidden and be revealed only once "
        "manifest.json is proven fetchable (#1648)"
    )
    assert 'id="alpha-gate" hidden' in page
    assert 'getElementById("stable-gate").hidden = false' in page
