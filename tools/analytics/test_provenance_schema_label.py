#!/usr/bin/env python3
"""#1430 - the provenance panel names the CSV file-format version for what it is.

The bench read (#1430): the "Bench provenance" panel's device/firmware group showed
`schema  1`, which is the HOST CSV file-format version (parse_v1's schema_version), not
the DEVICE's wire schema (4 on 0.7.3, 5 on main). Under that heading it read as the
device's and disagreed by 3-4 - two different things named "schema", one column apart,
on a panel explicitly meant to be screenshot-ready. The fix is a label, not logic.
"""

from __future__ import annotations

from pathlib import Path

_HTML = (Path(__file__).resolve().parent / "dashboard_template.html").read_text(
    encoding="utf-8"
)


def test_the_host_csv_schema_is_labelled_as_such_not_bare_schema() -> None:
    assert "['csv schema', d.schema_version]" in _HTML, (
        "the host CSV file-format version must be labelled 'csv schema', not 'schema' "
        "under a device/firmware heading (#1430)"
    )


def test_a_bare_schema_label_does_not_return_beside_schema_version() -> None:
    """The exact misread: a bare 'schema' key rendering d.schema_version in the device
    group. Its return is the regression."""
    assert "['schema', d.schema_version]" not in _HTML
