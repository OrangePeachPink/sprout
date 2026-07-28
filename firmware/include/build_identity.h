#ifndef SPROUT_BUILD_IDENTITY_H
#define SPROUT_BUILD_IDENTITY_H

/*
 * build_identity.h — #1614: what this image IS, stamped by the build that made it.
 *
 * `scripts/git_rev.py` defines all three at compile time. This header only supplies
 * the FALLBACKS, for a translation unit compiled outside the normal build (the native
 * test suite, an ad-hoc compile, a future tool).
 *
 * The fallbacks are deliberately "unknown" and NOT "stable"/a plausible timestamp.
 * Version and commit alone could not separate "the stable v0.8.0 release" from "an
 * alpha build sitting on a commit tagged 0.8.0" — on the #1334 B3 bench the honest
 * answer was alpha and nothing on the wire said so. A channel that cannot be read
 * back is a claim, not a fact; and a channel that DEFAULTS to the trusted value is
 * worse than absent, because that is precisely how an alpha build comes to call
 * itself a release. An image that cannot name its channel must say so.
 *
 * The channel rule itself lives once, in scripts/build_channel.py, and is consumed
 * by both the firmware build (here) and the web-flasher manifest (factory_bin.py) —
 * so the board and the manifest can never disagree about which channel made it.
 */

#ifndef GIT_REV
#define GIT_REV "nogit" /* overridden by scripts/git_rev.py at build */
#endif

#ifndef PLANTS_BUILD_CHANNEL
#define PLANTS_BUILD_CHANNEL "unknown" /* never "stable" - see above */
#endif

#ifndef PLANTS_BUILT_UTC
#define PLANTS_BUILT_UTC "unknown" /* ISO-8601 Z when the build ran */
#endif

#endif /* SPROUT_BUILD_IDENTITY_H */
