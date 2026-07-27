"""#1664 — rehearse the RELEASE path, which §5.1's dry run cannot reach.

`§5.1` walks draft → sign → verify → publish → delete on a throwaway `v0.0.0-cuttest`
tag. **A throwaway tag is legitimately alpha**, so the walk reported `0.0.0-alpha` as
*expected output* — correctly, for that walk — and was **blind by construction** to the
defect that blocked the v0.8.1 cut for roughly forty minutes.

That defect (#1630/#1640) was caught by §5's manifest check on the **real** draft, one
click from immutable. The walk had run clean immediately before.

**What must stop being true: "the §5.1 walk was green" is not evidence that a release
will label itself correctly.** So this rehearses the half the walk cannot:

1. the pure label logic, driven with *release-shaped* inputs — a real git repo whose
   HEAD is really tagged, not a hand-passed string; and
2. the workflow step that makes (1) reachable in CI at all.

(2) is the one that actually failed. `channel_label` was never wrong — it was fed
`exact_tag=None`, because `actions/checkout` fetches the commit without the tag that
points at it, so `git describe --exact-match` found nothing and the build honestly
reported alpha. A test of the pure function alone would have passed throughout.
"""

from __future__ import annotations

import subprocess
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SIGNER = REPO / ".github" / "workflows" / "sign-release.yml"
_SCRIPT = REPO / "firmware" / "scripts" / "factory_bin.py"


def _load():
    """Import factory_bin with a stub PlatformIO `Import`/`env`.

    Same shim as `tools/analytics/test_factory_channel_label.py` — the module calls
    `Import("env")` at top level, so it cannot be imported outside a build. Reused
    rather than reinvented: two different fakes of the same module is how the two drift
    apart and one of them starts testing a fiction.
    """
    mod = types.ModuleType("factory_bin_under_rehearsal")
    mod.__dict__["Import"] = lambda _name: None
    mod.__dict__["env"] = types.SimpleNamespace(
        subst=lambda s: "", AddPostAction=lambda *a, **k: None
    )
    exec(
        compile(_SCRIPT.read_text(encoding="utf-8"), str(_SCRIPT), "exec"), mod.__dict__
    )
    return mod


_fb = _load()
channel_label = _fb.channel_label
_exact_tag = _fb._exact_tag


def _git(*args: str, cwd: Path) -> None:
    # -c overrides pin the fixture to a known git config. A developer with
    # `tag.gpgSign` or `tag.forceSignAnnotated` set globally makes a bare `git tag`
    # fail with "no tag message?", which would fail this rehearsal on their machine and
    # nowhere else — a test that depends on ambient config is not a rehearsal.
    subprocess.run(
        ["git", "-c", "tag.gpgSign=false", "-c", "commit.gpgSign=false", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def tagged_checkout(tmp_path: Path) -> Path:
    """A real repo whose HEAD is really tagged — the state a signer must be in."""
    _git("init", "-q", cwd=tmp_path)
    _git("config", "user.email", "t@example.com", cwd=tmp_path)
    _git("config", "user.name", "t", cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    _git("add", "f.txt", cwd=tmp_path)
    _git("commit", "-qm", "c", cwd=tmp_path)
    _git("tag", "-a", "v1.2.3", "-m", "release", cwd=tmp_path)
    return tmp_path


def test_a_tagged_clean_checkout_labels_itself_as_a_release(
    tagged_checkout: Path,
) -> None:
    """The release path, end to end, on a real repo — not a hand-passed tag string."""
    tag = _exact_tag(tagged_checkout)
    assert tag == "v1.2.3", "the fixture is not actually tagged; the rehearsal is void"
    channel, label = channel_label("1.2.3", tag, dirty=False)
    assert channel == "stable"
    assert label == "1.2.3", "a release must label itself BARE (#1630)"


def test_an_untagged_checkout_honestly_reports_alpha(tmp_path: Path) -> None:
    """The v0.8.1 failure, reproduced: the code was right, its input was empty.

    This is what CI actually did — `actions/checkout` fetched the commit without the
    tag pointing at it, so `git describe --exact-match` found nothing. Every release
    build then labelled itself alpha, correctly, from a false premise.
    """
    _git("init", "-q", cwd=tmp_path)
    _git("config", "user.email", "t@example.com", cwd=tmp_path)
    _git("config", "user.name", "t", cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    _git("add", "f.txt", cwd=tmp_path)
    _git("commit", "-qm", "c", cwd=tmp_path)

    assert _exact_tag(tmp_path) is None
    channel, label = channel_label("1.2.3", _exact_tag(tmp_path), dirty=False)
    assert (channel, label) == ("alpha", "1.2.3-alpha")


def test_a_dirty_tagged_checkout_is_not_a_release(tagged_checkout: Path) -> None:
    """Tagged is not sufficient — uncommitted bytes are not the tagged bytes."""
    channel, label = channel_label("1.2.3", _exact_tag(tagged_checkout), dirty=True)
    assert channel == "alpha" and label.endswith("-alpha-dirty")


def test_the_signer_tags_its_checkout_before_building() -> None:
    """The step that makes the release path reachable in CI (#1627/#1630).

    Without it the signer's checkout cannot see its own tag and every release build
    labels itself alpha — the exact forty-minute defect. This asserts the fix is still
    present, because a test of `channel_label` alone would stay green if it vanished.
    """
    wf = SIGNER.read_text(encoding="utf-8")
    assert "git tag -f" in wf, (
        "sign-release.yml no longer tags its checkout — the build cannot see the tag "
        "it is signing for, and every release will label itself alpha (#1630)"
    )
    assert "--exact-match" in wf, (
        "the signer no longer verifies the tag it just applied resolves; a silent "
        "failure there is indistinguishable from success"
    )


def test_the_dry_run_tag_is_legitimately_alpha() -> None:
    """Why §5.1 is blind, asserted rather than asserted-about.

    `v0.0.0-cuttest` is a pre-release tag. The walk reporting `0.0.0-alpha` is CORRECT
    output for that walk — which is precisely why a green walk says nothing about how a
    real release will label itself, and why this file exists.
    """
    channel, label = channel_label("0.0.0", "v0.0.0-cuttest", dirty=False)
    assert channel == "stable"
    assert label == "0.0.0-cuttest"
    # The contract's own rule rejects it — a suffix is never a release label.
    from tools.release.contract import check_manifest_labels

    m = {
        "version": label,
        "provenance": {
            "channel": channel,
            "release_tag": "v0.0.0-cuttest",
            "git": "abc1234",
        },
    }
    r = check_manifest_labels("manifest-esp32.json", m, "v0.0.0-cuttest", "abc1234")
    assert not r.passed, "the rehearsal tag must not satisfy the release contract"
