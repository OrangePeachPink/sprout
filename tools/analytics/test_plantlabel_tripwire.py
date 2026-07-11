"""#925 - the identity-leak tripwire.

The plant-identity fallback chain (``plant_name || plant_id || probe || id``) used to be
copy-pasted across ~6 template sites; when every term was null it leaked the
``s2@device`` machine key onto a card (#803/#804/#805 were all this class). It now lives
in exactly ONE place - ``plantName()`` - and every render site routes through it (or its
``plantLabel()`` wrapper). This test is the gate that keeps it that way: it fails if the
raw chain is re-pasted, so the leak class can't come back on a new Predict surface.
"""

from __future__ import annotations

import re
from pathlib import Path

_TEMPLATE = (Path(__file__).resolve().parent / "dashboard_template.html").read_text(
    encoding="utf-8"
)
_CHAIN = re.compile(r"plant_name\s*\|\|")


def test_identity_chain_lives_in_exactly_one_place() -> None:
    n = len(_CHAIN.findall(_TEMPLATE))
    assert n == 1, (
        f"the raw plant-identity fallback chain appears {n}x (expected 1, in "
        "plantName()). Route the new site through plantName() / plantLabel() instead "
        "of re-pasting `plant_name || plant_id || ...` — the #803-805 leak class."
    )


def test_plantname_and_plantlabel_are_defined() -> None:
    assert "function plantName(" in _TEMPLATE
    assert "function plantLabel(" in _TEMPLATE
