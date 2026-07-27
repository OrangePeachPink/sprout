"""#1549 (A6) — the Add-a-board flash handoff may only offer boards we can web-flash.

The flow's last step now opens the browser flasher. Which boards that is *safe* for is
not a UI opinion: `firmware/scripts/factory_bin.py` holds `WEB_FLASH_VERIFIED`, and
ADR-0026 D6 rules that an unverified board gets no web-flasher manifest and "is never
offered from a browser." The C5 sat in that set until a bench failure pulled it.

So the UI and the firmware set have to agree, and the failure is asymmetric:

- offering a board that is NOT verified walks someone into a known-failing flash;
- withholding one that IS verified only costs a convenience.

The first is the one worth a test. This asserts the two stay in step, so re-adding the
C5 to `WEB_FLASH_VERIFIED` fails here until the UI is updated to match — rather than the
UI quietly continuing to withhold a board that now works.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FACTORY = REPO / "firmware" / "scripts" / "factory_bin.py"
DASHBOARD = REPO / "tools" / "analytics" / "dashboard_template.html"

# firmware mcu token -> the registry/UI board class it corresponds to
MCU_TO_CLASS = {"esp32": "esp32-classic", "esp32c5": "esp32-c5", "esp32s3": "esp32-s3"}


def _verified_mcus() -> set[str]:
    src = FACTORY.read_text(encoding="utf-8")
    m = re.search(r"WEB_FLASH_VERIFIED\s*=\s*\{([^}]*)\}", src)
    assert m, "WEB_FLASH_VERIFIED not found — factory_bin.py changed shape"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def _classes_offered_the_browser_flasher() -> set[str]:
    """Board classes the flash step gates its browser-flasher door on."""
    html = DASHBOARD.read_text(encoding="utf-8")
    step = html.split("D.step === 'flash'")[1].split("return card;")[0]
    assert "orangepeachpink.github.io/sprout/flash" in step, (
        "the flash step no longer links the web flasher — A6's handoff is gone"
    )
    return set(re.findall(r"D\.board === '([^']+)'", step))


def test_the_ui_offers_exactly_the_verified_boards() -> None:
    verified = {MCU_TO_CLASS[m] for m in _verified_mcus() if m in MCU_TO_CLASS}
    offered = _classes_offered_the_browser_flasher()
    assert offered == verified, (
        f"the flash step offers {sorted(offered)} but firmware verifies "
        f"{sorted(verified)}. Offering an unverified board sends someone into a "
        "known-failing flash (ADR-0026 D6); withholding a verified one is only a "
        "missed convenience — reconcile them."
    )


def test_the_c5_is_not_offered_while_it_is_pulled() -> None:
    """Named explicitly because it is the live case: the C5 was in the set, a bench
    failure removed it, and the browser path stays closed until it is re-verified."""
    if "esp32c5" in _verified_mcus():
        return  # re-verified upstream; the test above governs
    assert "esp32-c5" not in _classes_offered_the_browser_flasher()


def test_an_unverified_board_still_gets_a_real_path() -> None:
    """Withholding the browser door must not leave a dead end — the whole point of A6
    is that "I have a board" reaches "it's reporting" without hunting for docs."""
    html = DASHBOARD.read_text(encoding="utf-8")
    step = html.split("D.step === 'flash'")[1].split("return card;")[0]
    branch = step.split("} else {")[-1]
    assert "just flash" in branch, "no USB path offered for an unverified board"
