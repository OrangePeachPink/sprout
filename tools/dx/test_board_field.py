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


def _content_doc(typename="Issue", project_id=b.PROJECT_ID, values=None):
    """One `issueOrPullRequest` response with a single project item (#1522)."""
    values = values or {}
    item = {"id": "ITEM", "project": {"id": project_id}}
    # every declared field is present in a real response — absent ones come back null
    item.update({k: ({"name": values[k]} if values.get(k) else None) for k in b.FIELDS})
    return {
        "repository": {
            "issueOrPullRequest": {
                "__typename": typename,
                "id": "CONTENT",
                "title": "t",
                "projectItems": {"nodes": [item]},
            }
        }
    }


def test_missing_number_names_both_types(monkeypatch) -> None:
    """#1522 AC3: a number that is neither must say so — "does not exist" alone reads
    as "this tool only does issues", which is the confusion that hid the bug."""
    monkeypatch.setattr(
        b, "_gql", lambda q: {"repository": {"issueOrPullRequest": None}}
    )
    with pytest.raises(b.BoardError) as e:
        b._item_and_values(99999)
    msg = str(e.value)
    assert "issue" in msg and "pull request" in msg


def test_a_pull_request_resolves_like_an_issue(monkeypatch) -> None:
    """#1522 AC1/AC4: the whole point — PR cards carry planning fields too."""
    monkeypatch.setattr(
        b, "_gql", lambda q: _content_doc("PullRequest", values={"size": "M"})
    )
    item_id, values = b._item_and_values(1512)
    assert item_id == "ITEM"
    assert values["size"] == "M"


def test_the_query_asks_for_both_types(monkeypatch) -> None:
    """Pin the mechanism, not just the result: querying `issue(` alone is the defect."""
    seen = {}
    monkeypatch.setattr(
        b, "_gql", lambda q: (seen.update(q=q), _content_doc("PullRequest"))[1]
    )
    b._item_and_values(1512)
    assert "issueOrPullRequest" in seen["q"]
    assert "... on Issue" in seen["q"] and "... on PullRequest" in seen["q"]


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


def test_non_numeric_arg_is_named_accurately(monkeypatch) -> None:
    """The old broad `except ValueError` mislabelled a UnicodeEncodeError.
    Only a truly non-numeric arg should say so now."""
    with pytest.raises(b.BoardError) as e:
        b._card_number("abc")
    assert "must be a number" in str(e.value)
    assert b._card_number("1069") == 1069


def test_an_uncarded_item_is_added_not_refused(monkeypatch, capsys) -> None:
    """#1522 AC2: refusing an un-carded number is what left the gate adding cards by
    hand. Add it, then RE-QUERY — the add's own "ok" is not evidence (#519/#522)."""
    calls = []

    def fake_gql(q):
        calls.append(q)
        if "addProjectV2ItemById" in q:
            return {"addProjectV2ItemById": {"item": {"id": "NEW"}}}
        # first read: carded elsewhere only; after the add: on Project #2
        added = any("addProjectV2ItemById" in c for c in calls)
        return _content_doc(project_id=b.PROJECT_ID if added else "OTHER_PROJECT")

    monkeypatch.setattr(b, "_gql", fake_gql)
    item_id, _ = b._item_and_values(1443)
    assert item_id == "ITEM"  # from the RE-QUERY, not the mutation's own id
    assert any("addProjectV2ItemById" in c for c in calls)
    assert "added to the board" in capsys.readouterr().out


def test_a_card_still_absent_after_adding_fails_loud(monkeypatch) -> None:
    """The add reported success and the card is still not there — that is a loud
    failure, never an assumed one."""

    def fake_gql(q):
        if "addProjectV2ItemById" in q:
            return {"addProjectV2ItemById": {"item": {"id": "NEW"}}}
        return _content_doc(project_id="OTHER_PROJECT")  # never lands

    monkeypatch.setattr(b, "_gql", fake_gql)
    with pytest.raises(b.BoardError) as e:
        b._item_and_values(1443)
    assert "did not come back" in str(e.value)
