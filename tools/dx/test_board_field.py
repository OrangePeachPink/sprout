"""Tests for the #1443 board-field wrappers.

Runs under `just test-dx`. The network calls (`_gql`) are stubbed — these pin the
value-resolution, the fail-loud vocabulary, and the two guard behaviours that can't be
proven against the live board without corrupting it: the declared-table drift check, and
that a write re-queries rather than trusting the mutation. The live read+write+revert is
in the PR evidence, per the AC."""

import pytest

from tools.dx import board_field as b


def test_the_declared_table_is_internally_consistent() -> None:
    """Every field has a gql name, a field id, and at least one option — the table is
    the whole contract, so a malformed row would silently break a recipe."""
    for name, f in b.FIELDS.items():
        assert f["id"].startswith("PVTSSF_"), name
        assert f["gql"] and f["options"]
        assert all(isinstance(v, str) and v for v in f["options"].values())


def test_read_order_covers_every_field() -> None:
    assert set(b._READ_ORDER) == set(b.FIELDS)


def test_unknown_value_fails_loud_with_the_valid_set(monkeypatch) -> None:
    # get past the item lookup so we reach the value check
    monkeypatch.setattr(b, "_item_and_values", lambda n: ("ITEM", {}))
    with pytest.raises(b.BoardError) as e:
        b.write("priority", 1443, "urgent")
    assert "p0 p1 p2 p3" in str(e.value)  # the vocabulary, not just 'invalid'


def test_write_rejects_a_stale_declared_option_id(monkeypatch) -> None:
    """The drift guard: if a declared option id no longer exists on the live field, the
    write must refuse and name the fix — not push a stale id (the #1409 lesson)."""
    monkeypatch.setattr(b, "_item_and_values", lambda n: ("ITEM", {"size": None}))
    # live field reports a DIFFERENT option id set than the table declares
    monkeypatch.setattr(
        b,
        "_gql",
        lambda q: {
            "node": {
                "field": {
                    "id": b.FIELDS["size"]["id"],
                    "options": [{"id": "totally-different"}],
                }
            }
        },
    )
    with pytest.raises(b.BoardError) as e:
        b.write("size", 1443, "s")
    assert "fix the table" in str(e.value).lower()


def test_write_rejects_a_field_id_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(b, "_item_and_values", lambda n: ("ITEM", {"size": None}))
    monkeypatch.setattr(
        b,
        "_gql",
        lambda q: {"node": {"field": {"id": "PVTSSF_renamed", "options": []}}},
    )
    with pytest.raises(b.BoardError) as e:
        b.write("size", 1443, "s")
    assert "fix the table" in str(e.value).lower()


def test_write_prints_the_requeried_value_not_the_mutation(monkeypatch, capsys) -> None:
    """AC1: the confirmation is the read-back. Simulate a board that ends on 'M' and
    assert the printed value is what the re-query returned, not what we asked to set."""
    calls = {"n": 0}

    def fake_item(n):  # first call = pre-write; after the mutation = post-write read
        calls["n"] += 1
        return "ITEM", {"size": "S" if calls["n"] == 1 else "M"}

    monkeypatch.setattr(b, "_item_and_values", fake_item)
    monkeypatch.setattr(b, "_assert_option_live", lambda field, oid: None)
    monkeypatch.setattr(b, "_gql", lambda q: {})  # the mutation itself is a no-op here
    b.write("size", 1443, "s")
    out = capsys.readouterr().out
    assert "size = M" in out  # the board's word, re-queried — not the requested 's'


def test_missing_issue_is_a_clean_message(monkeypatch) -> None:
    monkeypatch.setattr(b, "_gql", lambda q: {"repository": {"issue": None}})
    with pytest.raises(b.BoardError) as e:
        b._item_and_values(99999)
    assert "does not exist" in str(e.value)


def test_read_renders_empty_fields_and_exits_zero(monkeypatch, capsys) -> None:
    """#1447: an empty field is legal — read prints the marker and exits 0.
    (An unset Size took `just board 1069` down before the fix.)"""
    monkeypatch.setattr(
        b,
        "_item_and_values",
        lambda n: (
            "ITEM",
            {
                "owner": "dx",
                "velocity": "V1",
                "size": None,
                "priority": "P1",
                "status": "In Progress",
            },
        ),
    )
    rc = b.read(1069)
    assert rc == 0
    out = capsys.readouterr().out
    assert b.EMPTY in out  # the empty Size is rendered, not crashed on
    assert "dx" in out and "In Progress" in out  # the set fields still print


def test_the_empty_marker_encodes_on_a_legacy_console() -> None:
    """The crash was an un-encodable glyph (U+2205 on cp1252). The marker must survive
    the narrowest console we ship to, or the fix just moves the bug."""
    b.EMPTY.encode("cp1252")  # raises UnicodeEncodeError if it regresses to U+2205


def test_non_numeric_issue_is_named_accurately(monkeypatch) -> None:
    """The old broad `except ValueError` mislabelled a UnicodeEncodeError.
    Only a truly non-numeric arg should say so now."""
    with pytest.raises(b.BoardError) as e:
        b._issue_number("abc")
    assert "must be a number" in str(e.value)
    assert b._issue_number("1069") == 1069


def test_issue_not_on_the_board_is_named(monkeypatch) -> None:
    monkeypatch.setattr(
        b,
        "_gql",
        lambda q: {
            "repository": {
                "issue": {
                    "projectItems": {
                        "nodes": [{"id": "X", "project": {"id": "SOME_OTHER_PROJECT"}}]
                    }
                }
            }
        },
    )
    with pytest.raises(b.BoardError) as e:
        b._item_and_values(1443)
    assert "not on the board" in str(e.value)
