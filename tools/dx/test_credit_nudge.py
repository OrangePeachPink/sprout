"""Tests for the credit-protection nudge detector (#1126).

Runs under `just test-dx` (pytest tools/dx/). Import style mirrors
test_link_check.py (tools/dx on sys.path). A fork PR can't be exercised in CI,
so these tests are where the fire/silent contract earns its confidence."""

from tools.dx.credit_nudge import (
    evaluate,
    has_lane_trailer,
    is_maintainer_identity,
)

MAINTAINER = "177329016+OrangePeachPink@users.noreply.github.com"
MAINTAINER_PLAIN = "OrangePeachPink@users.noreply.github.com"
CONTRIBUTOR = "42+Thanazar@users.noreply.github.com"
CONTRIBUTOR_REAL = "ada@example.com"


def _commit(author=CONTRIBUTOR_REAL, committer=None, message="fix: a thing"):
    return {
        "sha": "abcdef1234567890",
        "commit": {
            "author": {"email": author},
            "committer": {"email": committer if committer else author},
            "message": message,
        },
    }


# --- is_maintainer_identity: matches the maintainer, not other contributors --
def test_maintainer_noreply_with_id_is_matched():
    assert is_maintainer_identity(MAINTAINER)


def test_maintainer_noreply_plain_is_matched():
    assert is_maintainer_identity(MAINTAINER_PLAIN)


def test_match_is_case_insensitive():
    assert is_maintainer_identity("177329016+orangepeachpink@users.noreply.github.com")


def test_contributors_own_noreply_is_not_matched():
    # the crucial false-positive guard: a different login must never match
    assert not is_maintainer_identity(CONTRIBUTOR)


def test_real_email_is_not_matched():
    assert not is_maintainer_identity(CONTRIBUTOR_REAL)


def test_none_and_empty_are_safe():
    assert not is_maintainer_identity(None)
    assert not is_maintainer_identity("")


# --- has_lane_trailer: only a real line-start trailer -----------------------
def test_lane_trailer_detected():
    assert has_lane_trailer("feat: x\n\nLane: DX\n")


def test_lane_word_in_prose_is_not_a_trailer():
    assert not has_lane_trailer("fix: widen the swim lane: it was too narrow")


def test_no_message_is_safe():
    assert not has_lane_trailer(None)
    assert not has_lane_trailer("")


# --- evaluate: the fire / silent contract -----------------------------------
def test_fires_on_maintainer_authored_commit():
    r = evaluate([_commit(author=MAINTAINER)])
    assert r["nudge"] is True
    assert "author-is-maintainer-identity" in r["hits"][0]["reasons"]


def test_fires_on_committer_maintainer_identity():
    r = evaluate([_commit(author=CONTRIBUTOR_REAL, committer=MAINTAINER)])
    assert r["nudge"] is True
    assert "committer-is-maintainer-identity" in r["hits"][0]["reasons"]


def test_fires_on_lane_trailer():
    r = evaluate([_commit(message="docs: y\n\nLane: DX\n")])
    assert r["nudge"] is True
    assert "lane-trailer" in r["hits"][0]["reasons"]


def test_silent_on_clean_contributor_pr():
    r = evaluate([_commit(), _commit(author=CONTRIBUTOR)])
    assert r["nudge"] is False
    assert r["hits"] == []


def test_silent_on_empty_commit_list():
    assert evaluate([])["nudge"] is False


def test_one_hit_among_many_still_fires():
    r = evaluate([_commit(), _commit(author=MAINTAINER), _commit()])
    assert r["nudge"] is True
    assert len(r["hits"]) == 1


def test_malformed_commit_does_not_crash():
    r = evaluate([{}, {"commit": {}}, None])
    assert r["nudge"] is False
