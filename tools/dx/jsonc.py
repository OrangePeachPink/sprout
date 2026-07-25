#!/usr/bin/env python3
"""Minimal JSONC reader — VS Code's config files are JSON *with comments* (#1561).

`.vscode/extensions.json` and `.devcontainer/devcontainer.json` both carry `//` comments
that explain *why* each entry is there, and those comments are worth keeping. Python's
`json` cannot read them, and the obvious `re.sub(r"//.*", "", text)` is a trap: this
repo's `extensions.json` uses `"// "` as a **key**, so the naive strip corrupts the
document it was meant to parse.

So: a scanner that knows what a string is. Comments are removed only outside strings,
and escapes inside strings are honoured. It handles the subset VS Code actually emits
— `//`
line comments — and deliberately not `/* */` or trailing commas, because we do not use
them, and silently accepting more than we can round-trip would be a worse lie than
failing.
"""

from __future__ import annotations

import json
from typing import Any

_SLASH = "/"
_QUOTE = '"'
_BACKSLASH = "\\"


def strip_line_comments(text: str) -> str:
    """Remove `//` comments that are not inside a string literal."""
    out: list[str] = []
    i = 0
    in_string = False
    escaped = False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == _BACKSLASH:
                escaped = True
            elif ch == _QUOTE:
                in_string = False
            i += 1
            continue
        if ch == _QUOTE:
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == _SLASH and text[i + 1 : i + 2] == _SLASH:
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def loads(text: str) -> Any:
    return json.loads(strip_line_comments(text))
