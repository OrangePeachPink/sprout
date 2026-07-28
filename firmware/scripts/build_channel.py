# The ONE definition of "which channel did this build come from".
#
# #1614: two build scripts have to agree on the channel — factory_bin.py stamps it
# into the web-flasher manifest, git_rev.py compiles it into the firmware itself.
# If they ever disagree, the manifest says one thing and the board says another,
# which is precisely the unverifiable-claim #1614 exists to close. So the rule
# lives here once and both consume it; neither re-mints it.
#
# Pure by design (the git calls stay in the callers), so it is testable without a
# repo — see tools/analytics/test_factory_channel_label.py.


def channel_label(fw_version, exact_tag, dirty):
    """(channel, version_label) from the config version + git state.

    STABLE is earned, never assumed: only an exact tag on a clean tree. A commit
    that merely descends from a tag, or a dirty tree at a tag, is alpha — because
    the bytes are not the bytes that were released, and a build that calls itself
    stable when it isn't is the lie the channel exists to prevent.
    """
    if exact_tag and not dirty:
        return "stable", exact_tag.lstrip("v")
    suffix = "-alpha"
    if dirty:
        suffix = "-alpha-dirty"
    return "alpha", f"{fw_version}{suffix}"
