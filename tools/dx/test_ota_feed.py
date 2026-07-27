"""Tests for the #1524 OTA feed generator/validator - the device parser's desk twin.

Every rule the fleet enforces (ota_pull.h) is red-proofed here: a feed that
violates it must FAIL the check, and the two legal oddities (banner-only,
unknown keys) must PASS - the validator being stricter than the device in the
wrong place would block legitimate curation.
"""

from pathlib import Path

from tools.dx import ota_feed as f

_DL = "https://github.com/OrangePeachPink/sprout/releases/download/v0.8.1"
_CLASSIC_SIG = f"sig={_DL}/sprout-esp32-factory.bin.sig"
GOOD = (
    "# sprout-ota-feed v1\n"
    f"board=esp32-classic version=0.8.1 "
    f"image={_DL}/sprout-esp32-factory.bin {_CLASSIC_SIG}\n"
    f"board=esp32-c5 version=0.8.1 "
    f"image={_DL}/sprout-esp32c5-factory.bin "
    f"sig={_DL}/sprout-esp32c5-factory.bin.sig\n"
)


def test_a_good_two_board_feed_passes() -> None:
    assert f.validate(GOOD) == []


def test_banner_only_is_valid_and_offers_nothing() -> None:
    """The pre-first-release state: feed exists, offers nothing, boards stay put."""
    text = "# sprout-ota-feed v1\n# nothing pullable yet\n"
    assert f.validate(text) == []
    assert f.artifact_count(text) == 0


def test_missing_banner_fails() -> None:
    (msg,) = f.validate(GOOD.split("\n", 1)[1])
    assert "banner" in msg


def test_wrong_banner_version_fails() -> None:
    (msg,) = f.validate(GOOD.replace("v1", "v2", 1))
    assert "banner" in msg


def test_blank_lines_and_comments_are_skipped() -> None:
    text = GOOD.replace("\nboard=esp32-c5", "\n\n# a comment\nboard=esp32-c5")
    assert f.validate(text) == []


def test_missing_required_key_fails() -> None:
    """Missing keys are FATAL on-device - the feed must never lose a field."""
    problems = f.validate(GOOD.replace(" sig=https", " sg=https", 1))
    assert any("missing required key" in p and "sig" in p for p in problems)


def test_unknown_keys_are_ignored() -> None:
    """Additive-never-stitch: the feed may GAIN a field without stranding boards."""
    text = GOOD.replace("board=esp32-c5", "channel=stable board=esp32-c5")
    assert f.validate(text) == []


def test_duplicate_board_rejects_the_feed() -> None:
    text = GOOD + GOOD.split("\n")[1] + "\n"
    problems = f.validate(text)
    assert any("duplicate board" in p for p in problems)


def test_duplicate_key_in_one_line_fails() -> None:
    text = GOOD.replace("version=0.8.1", "version=0.8.1 version=0.8.0", 1)
    problems = f.validate(text)
    assert any("appears twice" in p for p in problems)


def test_overlong_url_fails_at_the_boundary() -> None:
    """255 chars fits char[256]; 256 is a REJECT - off-by-one is the classic."""
    pad_ok = "https://x/" + "a" * (f.URL_MAX - len("https://x/"))
    pad_bad = pad_ok + "a"
    assert len(pad_ok) == f.URL_MAX and len(pad_bad) == f.URL_MAX + 1
    ok = GOOD.replace(
        _CLASSIC_SIG,
        f"sig={pad_ok}",
    )
    bad = GOOD.replace(
        _CLASSIC_SIG,
        f"sig={pad_bad}",
    )
    assert f.validate(ok) == []
    assert any("exceeds" in p for p in f.validate(bad))


def test_overlong_board_and_version_fail() -> None:
    long_board = GOOD.replace("board=esp32-c5", "board=" + "b" * 24)
    assert any("board" in p and "exceeds" in p for p in f.validate(long_board))
    long_ver = GOOD.replace("version=0.8.1", "version=" + "9" * 24, 1)
    assert any("version exceeds" in p for p in f.validate(long_ver))


def test_http_url_fails() -> None:
    problems = f.validate(GOOD.replace("image=https://", "image=http://", 1))
    assert any("https" in p for p in problems)


def test_unknown_board_class_fails() -> None:
    """A typo'd class strands a fleet silently - the declared table screams."""
    problems = f.validate(GOOD.replace("board=esp32-classic", "board=esp32-clasic"))
    assert any("unknown board class" in p for p in problems)


def test_empty_value_fails() -> None:
    problems = f.validate(GOOD.replace("version=0.8.1", "version=", 1))
    assert any("empty value" in p for p in problems)


def test_build_feed_round_trips_and_is_fail_closed() -> None:
    assets = {
        "sprout-esp32-factory.bin",
        "sprout-esp32-factory.bin.sig",
        "sprout-esp32c5-factory.bin",
        "sprout-esp32c5-factory.bin.sig",
        "sprout-esp32-factory.bin.sha256",  # extras are fine
    }
    text = f.build_feed("v0.8.1", assets)
    assert f.validate(text) == []
    assert f.artifact_count(text) == len(f.BOARDS)
    assert "releases/download/v0.8.1/" in text and "version=0.8.1" in text


def test_build_feed_refuses_a_missing_sig() -> None:
    """An image without its signature is not offerable - never emit it."""
    assets = {
        "sprout-esp32-factory.bin",
        "sprout-esp32-factory.bin.sig",
        "sprout-esp32c5-factory.bin",  # .sig missing
    }
    try:
        f.build_feed("v0.8.1", assets)
    except ValueError as e:
        assert "esp32-c5" in str(e) and ".sig" in str(e)
    else:  # pragma: no cover
        raise AssertionError("a partial fleet was emitted silently")


def test_every_declared_board_has_a_real_board_cap() -> None:
    """The BOARDS table is declared, not inferred - so assert it against the
    firmware truth it declares: every class name exists in board_capability.h."""
    caps = (f._REPO / "firmware" / "include" / "board_capability.h").read_text(
        encoding="utf-8"
    )
    for board in f.BOARDS:
        assert f'"{board}"' in caps, f"{board} is not a BOARD_CAP name"


def test_bounds_mirror_the_device_header() -> None:
    """If ota_pull.h changes its buffer sizes, this file must follow - the desk
    twin drifting from the device is the exact failure class (#1227)."""
    hdr = (f._REPO / "firmware" / "lib" / "ota_pull" / "ota_pull.h").read_text(
        encoding="utf-8"
    )
    assert f"#define OTA_PULL_VERSION_MAX {f.VERSION_MAX + 1}" in hdr
    assert f"#define OTA_PULL_BOARD_MAX {f.BOARD_MAX + 1}" in hdr
    assert f"#define OTA_PULL_URL_MAX {f.URL_MAX + 1}" in hdr
    assert f'"{f.BANNER}"' in hdr


def test_the_committed_feed_parses_on_device() -> None:
    """The live claim: what docs/ota/feed.txt serves right now, the fleet accepts."""
    text = Path(f.FEED_PATH).read_text(encoding="utf-8")
    assert f.validate(text) == []
