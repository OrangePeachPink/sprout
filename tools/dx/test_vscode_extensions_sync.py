"""#1561 — the local editor and the Codespaces editor must agree.

`.vscode/extensions.json` is what a local contributor is offered on open;
`.devcontainer/devcontainer.json` is what a Codespaces contributor gets installed. They
had drifted to 12 vs 6 — same repo, same gate, half the editor — so a Codespaces user
met the cspell and YAML gates with no editor support for either.

A declared exception list, not a fuzzy tolerance: the only permitted difference is named
here with its reason, and anything else fails loud (the guard-family shape).
"""

from pathlib import Path

from tools.dx import jsonc

REPO = Path(__file__).resolve().parents[2]

# Allowed to differ, each for a stated reason. Adding a row is a deliberate act.
CONTAINER_EXEMPT = {
    # Opens a project *in* a container. Inside one it has nothing to do.
    "ms-vscode-remote.remote-containers",
}


def _local() -> dict:
    return jsonc.loads(
        (REPO / ".vscode" / "extensions.json").read_text(encoding="utf-8")
    )


def _devcontainer() -> dict:
    doc = jsonc.loads(
        (REPO / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    )
    return doc["customizations"]["vscode"]


def test_every_local_recommendation_reaches_the_devcontainer() -> None:
    local = set(_local()["recommendations"])
    container = set(_devcontainer()["extensions"])
    missing = local - container - CONTAINER_EXEMPT
    assert not missing, (
        f"Codespaces would be missing {sorted(missing)} — add them to "
        ".devcontainer/devcontainer.json, or exempt them here WITH a reason."
    )


def test_the_devcontainer_adds_nothing_unannounced() -> None:
    """Drift runs both ways: an extension only Codespaces gets is just as much a split
    experience, and it would never show up in a local contributor's recommendations."""
    local = set(_local()["recommendations"])
    extra = set(_devcontainer()["extensions"]) - local
    assert not extra, (
        f"only the devcontainer installs {sorted(extra)} — add to .vscode too"
    )


def test_unwanted_recommendations_are_never_installed_by_the_container() -> None:
    """`.vscode` deliberately marks cmake-tools unwanted (this repo builds with
    PlatformIO, and pointing someone at `cmake` would be actively misleading). The
    container must not undo that ruling."""
    unwanted = set(_local().get("unwantedRecommendations", []))
    assert unwanted, "the unwanted list vanished — that ruling was deliberate"
    assert not (unwanted & set(_devcontainer()["extensions"]))


def test_the_exemption_list_is_real() -> None:
    """An exemption for something nobody recommends is a stale rule watching nothing."""
    local = set(_local()["recommendations"])
    assert local >= CONTAINER_EXEMPT, (
        f"exempted but not actually recommended locally: "
        f"{sorted(CONTAINER_EXEMPT - local)}"
    )


def test_jsonc_survives_a_comment_shaped_key() -> None:
    """The naive `re.sub(r'//.*', '', text)` corrupts THIS repo's extensions.json,
    which uses `"// "` as a key. The parser must handle it — the bug that would make
    every assertion above silently vacuous."""
    doc = jsonc.loads('{"// ": "a note", "x": 1} // trailing\n')
    assert doc == {"// ": "a note", "x": 1}
