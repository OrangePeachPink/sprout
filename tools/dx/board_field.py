#!/usr/bin/env python3
"""#1443 — read/write the five Project #2 board fields in one line.

The four planning attributes (plus Status) live on the board as fields, not labels
(ADR-0003 §5). Lanes must be able to read and set them in one line, or attributes rot —
`velocity:` reached 7-of-69 because writing it was annoying. This makes the field the
path of least resistance. The `just` recipes are thin passthroughs to this.

Guard-family shape (the #1409 pattern): a **declared ID table**, and every operation is
checked against the **live board** rather than trusted. Two ways that matters:

- **Never trust a fired mutation** (#519/#522): after a write we RE-QUERY the field and
  print the value the board now reports — the confirmation is the read-back, not the
  mutation's own "ok".
- **The declared table can drift** (a renamed/removed option): before writing, we
  confirm the declared option id still exists on the live field, and fail loud with
  "fix the table" if it doesn't. Silently writing a stale id is worse than no tool.

    python tools/dx/board_field.py read <issue>
    python tools/dx/board_field.py <field> <issue> <value>
"""

from __future__ import annotations

import json
import subprocess
import sys

PROJECT_ID = "PVT_kwHOCpHTeM4Bbmep"

# The declared table (spec on #1443). Each field: its Project field id + the option
# words a lane types → the option ids the board stores. Words are the lane's vocabulary;
# ids are the board's. Adding a row is deliberate — this is a table, never a lookup.
FIELDS: dict[str, dict] = {
    "owner": {
        "id": "PVTSSF_lAHOCpHTeM4BbmepzhYhYBg",
        "gql": "Owner",
        "options": {
            "firmware": "217a1dc9",
            "data": "7bafb049",
            "design": "a09f3b9a",
            "dx": "124f213e",
            "trellis": "70fd18c0",
            "workflow": "04d26220",
            "maintainer": "7ac7b0d6",
        },
    },
    "velocity": {
        "id": "PVTSSF_lAHOCpHTeM4BbmepzhYhYE0",
        "gql": "Velocity",
        "options": {"v1": "f3c7b174", "v2": "b16828b0"},
    },
    "size": {
        "id": "PVTSSF_lAHOCpHTeM4BbmepzhWV5dA",
        "gql": "Size",
        "options": {
            "xs": "5d8ec1e1",
            "s": "79c17528",
            "m": "48136fd0",
            "l": "a61b3080",
            "xl": "7d090c3a",
        },
    },
    "priority": {
        "id": "PVTSSF_lAHOCpHTeM4BbmepzhWV5cI",
        "gql": "Priority",
        "options": {
            "p0": "f5ba88db",
            "p1": "6b7cebb2",
            "p2": "9e0a9579",
            "p3": "9c8eef09",
        },
    },
    "status": {
        "id": "PVTSSF_lAHOCpHTeM4BbmepzhWV5GY",
        "gql": "Status",
        # the recipe words the spec uses → the board's option ids
        "options": {
            "backlog": "e24cf82d",
            "progress": "b8970df8",
            "verify": "0742aca7",
            "ready": "7c75f7df",
            "done": "ba88d845",
        },
    },
}

# Read order = the board's mental model: who owns it, how fast, how big, how urgent.
_READ_ORDER = ("owner", "velocity", "size", "priority", "status")


class BoardError(Exception):
    """A loud, actionable failure — never a silent wrong write."""


def _gql(query: str) -> dict:
    """Run a GraphQL query and return its `data`, failing loud on any error.

    `gh` exits non-zero when GraphQL reports errors even alongside partial `data`
    (a not-found issue returns both). Prefer the structured `errors[].message` over
    the raw stderr, and still return `data` when it is usable — so a null `issue`
    reaches the caller as a clean 'does not exist' rather than a generic API blob."""
    p = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        capture_output=True,
        text=True,
    )
    try:
        doc = json.loads(p.stdout)
    except (json.JSONDecodeError, ValueError):
        raise BoardError(
            f"GitHub API call failed:\n{(p.stderr or p.stdout).strip()}"
        ) from None
    if doc.get("errors"):
        msgs = "; ".join(e.get("message", str(e)) for e in doc["errors"])
        if doc.get("data") is None:
            raise BoardError(f"GitHub API: {msgs}")
        # partial data (e.g. issue: null) — let the caller give the clean message
    return doc["data"]


def _item_and_values(issue: int) -> tuple[str, dict[str, str | None]]:
    """The issue's project-#2 item id, plus each field's current value name (or None).

    Per-issue query — never the bulk item-list, which truncates silently (ADR-0003 §5).
    """
    sel = "\n".join(
        f'{k}: fieldValueByName(name: "{f["gql"]}") '
        "{ ... on ProjectV2ItemFieldSingleSelectValue { name } }"
        for k, f in FIELDS.items()
    )
    data = _gql(
        f'{{ repository(owner: "OrangePeachPink", name: "sprout") '
        f"{{ issue(number: {issue}) {{ title projectItems(first: 10) "
        f"{{ nodes {{ id project {{ id }} {sel} }} }} }} }} }}"
    )
    issue_node = (data.get("repository") or {}).get("issue")
    if issue_node is None:
        raise BoardError(f"issue #{issue} does not exist.")
    for node in issue_node["projectItems"]["nodes"]:
        if node["project"]["id"] == PROJECT_ID:
            values = {k: (node[k] or {}).get("name") for k in FIELDS}
            return node["id"], values
    raise BoardError(
        f"issue #{issue} is not on the board (Project #2). Add it, then set fields."
    )


def _assert_option_live(field: str, option_id: str) -> None:
    """Confirm the declared option id still exists on the LIVE field before writing.

    This is the drift guard: a renamed/removed option would make the mutation write a
    stale id (or fail opaquely). Better to stop and say 'fix the table' by name."""
    f = FIELDS[field]
    data = _gql(
        f'{{ node(id: "{PROJECT_ID}") {{ ... on ProjectV2 '
        f'{{ field(name: "{f["gql"]}") {{ ... on ProjectV2SingleSelectField '
        "{ id options { id } } } } } }"
    )
    live = ((data.get("node") or {}).get("field")) or {}
    if live.get("id") != f["id"]:
        raise BoardError(
            f"field '{field}' id in the table ({f['id']}) != the live board "
            f"({live.get('id')}). The board changed — fix the table in {__file__}."
        )
    live_ids = {o["id"] for o in live.get("options", [])}
    if option_id not in live_ids:
        word = next(w for w, i in f["options"].items() if i == option_id)
        raise BoardError(
            f"option '{field}={word}' ({option_id}) is not on the live field anymore — "
            f"it was renamed or removed. Fix the table in {__file__}; do not guess."
        )


def read(issue: int) -> int:
    _, values = _item_and_values(issue)
    for k in _READ_ORDER:
        print(f"  {k:9} {values[k] or '∅'}")
    return 0


def write(field: str, issue: int, word: str) -> int:
    f = FIELDS[field]
    word = word.lower()
    if word not in f["options"]:
        valid = " ".join(f["options"])
        raise BoardError(f"unknown {field} '{word}'. Valid: {valid}")
    option_id = f["options"][word]

    item_id, _ = _item_and_values(issue)  # also proves the issue is on the board
    _assert_option_live(field, option_id)  # drift guard, before the mutation

    _gql(
        "mutation { updateProjectV2ItemFieldValue(input: { "
        f'projectId: "{PROJECT_ID}", itemId: "{item_id}", fieldId: "{f["id"]}", '
        f'value: {{ singleSelectOptionId: "{option_id}" }} }}) '
        "{ projectV2Item { id } } }"
    )

    # Never trust the mutation — re-query and print what the board reports (#519/#522).
    _, values = _item_and_values(issue)
    now = values[field]
    print(f"  #{issue} {field} = {now or '∅'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    fields = " ".join(FIELDS)
    if not argv:
        print(
            f"usage: board_field.py read <issue>\n"
            f"       board_field.py <{fields}> <issue> <value>",
            file=sys.stderr,
        )
        return 2

    verb = argv[0]
    try:
        if verb == "read":
            if len(argv) != 2:
                raise BoardError("usage: board_field.py read <issue>")
            return read(int(argv[1]))
        if verb in FIELDS:
            if len(argv) != 3:
                raise BoardError(f"usage: board_field.py {verb} <issue> <value>")
            return write(verb, int(argv[1]), argv[2])
        raise BoardError(f"unknown command '{verb}'. Use: read | {fields}")
    except ValueError:
        print("error: issue must be a number.", file=sys.stderr)
        return 2
    except BoardError as e:
        print(f"board_field: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
