"""Tests for the #1161 voice-guard (retired-register patterns + scoping).

Fixture lines below deliberately contain the retired register — this file is
in the guard's own skip-list, so the strings live here without tripping it.
"""

from __future__ import annotations

from tools.dx import voice_guard as vg


def _names(line: str) -> list[str]:
    return vg.scan_line(line)


# --- each retired pattern fires -------------------------------------------------


def test_noun_frames_fire():
    assert _names("Our honesty sets us apart.")
    assert _names("We promise honest data, always.")
    assert _names("Other apps are dishonest about moisture.")
    assert _names("Without moralizing about percentages.")


def test_is_truth_formulas_fire():
    assert _names("raw + band is truth, % is an index")
    assert _names("The manifest is truth for the fleet.")
    assert _names("rows kept on the plot (raw = truth) but excluded")  # the = form


def test_judgment_hooks_fire():
    assert _names("Sprout refuses to lie to you.")
    assert _names("No fake % pretending to be science.")
    assert _names("a made-up number dressed as precision")


def test_copula_fires():
    assert _names("Sprout is a plant.")
    assert _names("sprout is the plant, basically")
    assert _names("Sprout is a plant that talks back.")  # edge class -> human read


# --- the kept register passes ---------------------------------------------------


def test_adjectival_honest_kept():
    assert not _names("an honest reading of the sensor")
    assert not _names("honestly, the band model is simpler")


def test_canonical_exceptions_pass():
    assert not _names("the registry is the source of truth")
    assert not _names("compare against ground truth labels")


def test_code_identifiers_pass():
    assert not _names("def test_honesty_gates_reject_stitching():")


def test_descriptor_copulas_pass():
    assert not _names("Sprout is a plant-care assistant.")
    assert not _names("Sprout is the plant monitor on your sill.")
    assert not _names("Sprout is a plant-first voice.")


def test_allow_marker_suppresses():
    assert not _names("the retired phrase 'honest data' <!-- voice-guard: allow -->")


# --- diff parsing and scoping ---------------------------------------------------

DIFF = """\
diff --git a/docs/user/intro.md b/docs/user/intro.md
--- a/docs/user/intro.md
+++ b/docs/user/intro.md
@@ -4,0 +5,2 @@
+Sprout is a plant.
+Sprout is a plant-care assistant.
diff --git a/docs/adr/0099-example.md b/docs/adr/0099-example.md
--- a/docs/adr/0099-example.md
+++ b/docs/adr/0099-example.md
@@ -1,0 +2 @@
+we retired the honesty framing here
"""


def test_added_lines_flag_only_in_scope():
    hits = [(p, n, vg.scan_line(t)) for p, n, t in vg._added_lines(DIFF)]
    flagged = [(p, n) for p, n, names in hits if names]
    assert flagged == [("docs/user/intro.md", 5)]  # ADR line skipped by scope


def test_skip_list():
    assert vg._skipped("docs/adr/0031-x.md")
    assert vg._skipped("docs/evidence/2026-07-04-wave1-golive/README.md")
    assert vg._skipped("CHANGELOG.md")
    assert vg._skipped("tools/dx/test_voice_guard.py")
    assert not vg._skipped("docs/user/what-sprout-is-telling-you.md")
    assert not vg._skipped("tools/analytics/home_template.html")


# ---- #1506: the collective is a greenhouse, not a fleet -----------------------
# This pattern exists because the vocabulary was retired ONCE, as a sweep, and came
# back within days — in STATUS.md, via #1653, written by the lane that filed the
# sweep. That is the exact migration this guard's docstring predicts.

FLEET_PROSE = [
    "Two boards are live, so the fleet is 8 instrumented plants",  # the regression
    "the multi-board fleet, per-board serial paths, and pin maps",
    "wider fleet - see BOARDS.md for per-board serial paths",
    "// #686 interim: at fleet scale 13 series cycle a 4-colour palette",
    "fleet watering IS a fleet-wide exclusion zone",
    "Fleet overview",
]

# #923's vocabulary contract keeps `fleet` legal in code and endpoints, and there are
# ~619 such uses. A pattern that fired on these would be switched off within a day —
# which is how a guard dies. Each line below is copied from the live tree.
FLEET_CODE = [
    "from fleet_logger import FleetLogger",
    "  const F = DASH.fleet || {};",
    "  const [fc, fa] = count(st.fleet);",
    "  if(L.fleet_sources && L.fleet_sources.length){",
    '  // "serial"/"fleet" stay in code + endpoints only (#923 vocabulary contract)',
    "st['fleet']",
    "tools/logger/fleet_control.py",
]


def test_fleet_prose_is_flagged():
    for line in FLEET_PROSE:
        assert "fleet (#1506)" in vg.scan_line(line), line


def test_fleet_in_code_and_endpoints_is_not_flagged():
    """The #923 carve-out. Renaming identifiers is a separate, unasked-for job."""
    for line in FLEET_CODE:
        assert "fleet (#1506)" not in vg.scan_line(line), line


def test_the_allow_marker_still_works_for_fleet():
    """A deliberate mention — quoting the retired term to explain it — stays sayable."""
    line = "we used to call it the fleet  <!-- voice-guard: allow -->"
    assert vg.scan_line(line) == []


# ---- #1479 AC4: user-facing text says Workbench --------------------------------
# Design's ruling. "Classic Sprout" survives only in architecture prose naming the
# transitional migration architecture — and docs/adr/ is already out of scope, so
# ADR-0033 and its descendants keep it without an exemption.


def test_classic_sprout_in_user_prose_is_flagged():
    assert "Classic Sprout (#1479 AC4)" in vg.scan_line(
        "This is Classic Sprout, and ADR-0033 calls it scaffolding"
    )


def test_the_hardware_class_named_Classic_is_never_flagged():
    """The collision that DECIDED the ruling, asserted rather than assumed.

    `Classic (ESP32-WROOM)` is a live board class in the greenhouse right now. A
    pattern that flagged the hardware label would be switched off within a day, and
    then it would catch nothing at all.
    """
    for line in [
        "  const CLASSES = [['esp32-classic', 'Classic (ESP32-WROOM)'], ...];",
        "the classic board holds four channels",
        "Board env is `esp32dev` (classic ESP32)",
    ]:
        assert "Classic Sprout (#1479 AC4)" not in vg.scan_line(line), line


def test_workbench_is_the_approved_word():
    assert vg.scan_line("Today - the Workbench. One command serves it.") == []


def test_adrs_keep_the_architecture_noun():
    """Ruling part 2: architecture prose may say Classic Sprout. docs/adr/ is already
    skipped, so this needs no new exemption — asserted so a future scope change to
    SKIP_DIR_PARTS does not silently start flagging ADR-0033."""
    assert vg._skipped("docs/adr/0033-two-surface-architecture-home-and-workbench.md")
