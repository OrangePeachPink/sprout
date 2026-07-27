"""Tests for the link_check gate (#913).

Runs under `just test-dx` (pytest tools/dx/). Mirrors the import style of
test_lint_epic_subissues.py (tools/dx on sys.path)."""

from tools.dx.link_check import (
    check_link,
    extract_links,
    find_findings,
    finding_key,
)

TRACKED = {"docs/real.md", "docs/sub/page.md", "AGENTS.md", "docs/My File.md"}
DIRS = {"docs", "docs/sub"}


# --- the deliberate red: a broken relative link is caught -------------------
def test_broken_relative_is_flagged():
    f = check_link("docs/a.md", "nope.md", TRACKED, DIRS)
    assert f is not None
    assert f["kind"] == "broken-relative"


def test_good_relative_resolves_clean():
    assert check_link("docs/a.md", "real.md", TRACKED, DIRS) is None
    assert check_link("docs/sub/a.md", "../real.md", TRACKED, DIRS) is None


# --- the #908 class: self-links with a broken ref ---------------------------
def test_head_self_link_is_flagged():
    url = "https://github.com/OrangePeachPink/sprout/blob/HEAD/.github/CONTRIBUTING.md"
    f = check_link("x.md", url, TRACKED, DIRS)
    assert f is not None and f["kind"].startswith("bad-ref")


def test_main_self_link_ok_when_path_exists():
    url = "https://github.com/OrangePeachPink/sprout/blob/main/AGENTS.md"
    assert check_link("x.md", url, TRACKED, DIRS) is None


def test_main_self_link_flagged_when_path_missing():
    url = "https://github.com/OrangePeachPink/sprout/blob/main/docs/ghost.md"
    f = check_link("x.md", url, TRACKED, DIRS)
    assert f is not None and f["kind"].startswith("missing-path")


# --- deliberate skips (scope fence) -----------------------------------------
def test_app_runtime_routes_skipped():
    assert check_link("x.html", "/lab", TRACKED, DIRS) is None
    assert check_link("x.html", "/lab/<!--__EID__-->/notes", TRACKED, DIRS) is None


def test_external_links_skipped():
    assert check_link("x.md", "https://example.com/page", TRACKED, DIRS) is None


def test_placeholders_and_schemes_skipped():
    assert check_link("x.md", "{{ url }}", TRACKED, DIRS) is None
    assert check_link("x.md", "#anchor", TRACKED, DIRS) is None
    assert check_link("x.md", "mailto:a@b.com", TRACKED, DIRS) is None


def test_url_encoded_target_decodes_before_resolving():
    # "My%20File.md" -> "My File.md" -> docs/My File.md (tracked)
    assert check_link("docs/i.md", "My%20File.md", TRACKED, DIRS) is None


def test_non_blob_self_links_skipped():
    assert (
        check_link(
            "x.md",
            "https://github.com/OrangePeachPink/sprout/discussions",
            TRACKED,
            DIRS,
        )
        is None
    )


# --- extraction + aggregate --------------------------------------------------
def test_extract_markdown_and_html():
    md = extract_links("see [a](x.md) and [b](y.md)", is_html=False)
    assert md == ["x.md", "y.md"]
    html = extract_links('<a href="p.html">x</a><img src="i.png">', is_html=True)
    assert html == ["p.html", "i.png"]


def test_find_findings_aggregate_bites():
    texts = {"docs/a.md": "[ok](real.md) then [bad](ghost.md)"}
    findings = find_findings(texts, TRACKED, DIRS)
    assert len(findings) == 1
    assert findings[0]["target"] == "ghost.md"
    assert finding_key(findings[0]) == "docs/a.md -> ghost.md"
