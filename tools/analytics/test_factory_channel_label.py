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
    mod.__dict__["env"] = types.SimpleNamespace(
        subst=lambda s: "", AddPostAction=lambda *a, **k: None
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
