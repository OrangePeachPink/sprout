"""#1334 — the release-channel label a build gives itself.

`factory_bin.py` is a PlatformIO extra_script (it imports an injected `env`), so the
channel decision is kept as a pure function and tested here without a build.

What is being defended: an alpha build is a build of `main` BETWEEN releases. It used
to inherit `PLANTS_FW_VERSION` wholesale, so bytes that are not the 0.8.1 release still
presented themselves as "0.8.1" — and a bug report then names a version that does not
identify what was running. "You can use 0.7.1 or 0.7.3 but skip 0.7.2" is only an easy
support answer if a version string means exactly one set of bytes.
"""

import pathlib
import types

_SCRIPT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "firmware"
    / "scripts"
    / "factory_bin.py"
)


def _load():
    """Import factory_bin with a stub PlatformIO `Import`/`env` so the module body
    (which calls Import("env") at top level) can run outside a build."""
    src = _SCRIPT.read_text(encoding="utf-8")
    mod = types.ModuleType("factory_bin_under_test")
    mod.__dict__["Import"] = lambda _name: None
    # $PROJECT_DIR must resolve: factory_bin locates its sibling build_channel module
    # through it (#1614). PlatformIO sets no __file__, so this IS the real mechanism,
    # not a convenience — stubbing it wrong is how the build broke once already.
    _fw = str(_SCRIPT.parent.parent)
    mod.__dict__["env"] = types.SimpleNamespace(
        subst=lambda s: _fw if s == "$PROJECT_DIR" else "",
        AddPostAction=lambda *a, **k: None,
    )
    exec(compile(src, str(_SCRIPT), "exec"), mod.__dict__)
    return mod


fb = _load()


def test_exact_clean_tag_is_stable():
    """Only an exact tag on a clean tree earns the release version string."""
    ch, label = fb.channel_label("0.8.1", "v0.8.1", dirty=False)
    assert ch == "stable"
    assert label == "0.8.1", "the leading v is stripped for the manifest"


def test_untagged_main_is_alpha_and_cannot_wear_a_release_version():
    """The core guarantee: a build of main between releases must not present a bare
    release version. The suffix is structural, not cosmetic."""
    ch, label = fb.channel_label("0.8.1", None, dirty=False)
    assert ch == "alpha"
    assert label != "0.8.1"
    assert label.startswith("0.8.1") and "-alpha" in label


def test_dirty_tree_is_never_stable_even_on_a_tag():
    """A tagged commit with uncommitted changes is NOT that release — the bytes
    differ from the tag by definition, so the label has to differ too."""
    ch, label = fb.channel_label("0.8.1", "v0.8.1", dirty=True)
    assert ch == "alpha"
    assert "dirty" in label
    assert label != "0.8.1"


def test_dirty_untagged_is_alpha_dirty():
    ch, label = fb.channel_label("0.8.1", None, dirty=True)
    assert ch == "alpha"
    assert label == "0.8.1-alpha-dirty"


def test_no_alpha_label_is_ever_a_bare_version():
    """Swept across plausible versions and git states: every non-stable label is
    distinguishable from a release at a glance AND by string equality."""
    for ver in ("0.8.1", "0.9.0", "1.0.0"):
        for tag, dirty in ((None, False), (None, True), (f"v{ver}", True)):
            ch, label = fb.channel_label(ver, tag, dirty)
            assert ch == "alpha"
            assert label != ver, f"{ver!r} leaked as a bare release version"


def test_a_tag_that_disagrees_with_config_still_labels_from_the_tag():
    """The tag is the release identity; config.h can lag a version bump. Labelling
    from config here would publish the tag's bytes under a different version — the
    exact relabelling drift #1346 closed on the release job."""
    ch, label = fb.channel_label("0.8.0", "v0.8.1", dirty=False)
    assert ch == "stable"
    assert label == "0.8.1"


def test_a_release_build_without_its_tag_is_alpha_which_is_why_the_signer_creates_it():
    """#1630 — the pure half of a whole-pipeline defect, pinned here so the reason
    survives the workflow line that fixes it.

    `channel_label` is correct and this test asserts it stays correct: no exact tag
    means alpha, always (#1399 — stable is not a claim a build makes about itself).

    The defect was in what the SIGNER handed it. Publish creates the tag, so at signing
    time the checkout is a commit with no tag pointing at it; `git describe
    --exact-match` found nothing and every release build labelled itself
    `<version>-alpha`. The §5.1 dry-run walk demonstrated it and could not flag it — a
    throwaway tag is *legitimately* alpha, so the walk is blind to this by construction.

    The fix is upstream (sign-release.yml creates the release tag locally on the proven
    target commit before building). This pins both halves of the contract so neither can
    drift: without a tag the label MUST stay alpha, and with one it MUST be the bare
    release version.
    """
    version = "0.8.1"
    # what the signer used to hand it: a commit, no tag
    channel, label = fb.channel_label(version, None, dirty=False)
    assert (channel, label) == ("alpha", "0.8.1-alpha")

    # what it hands it now, after the workflow tags the proven target commit
    channel, label = fb.channel_label(version, f"v{version}", dirty=False)
    assert (channel, label) == ("stable", "0.8.1")
