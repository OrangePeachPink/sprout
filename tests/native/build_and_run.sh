#!/usr/bin/env sh
# Build + run the host-native irrigation FSM tests (no ESP32, no flash).
# Needs any host C compiler. Override with CC=/path/to/gcc if not on PATH
# (e.g. a winget MinGW: CC="$LOCALAPPDATA/.../mingw64/bin/gcc.exe").
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CC="${CC:-gcc}"
OUT="$HERE/test_irrigation.exe"

"$CC" -std=gnu11 -Wall -Wextra -O1 \
  -I"$ROOT/firmware/lib/irrigation" \
  -I"$ROOT/firmware/lib/moisture_classifier" \
  "$HERE/test_irrigation.c" \
  "$ROOT/firmware/lib/irrigation/irrigation.c" \
  "$ROOT/firmware/lib/moisture_classifier/moisture_classifier.c" \
  -o "$OUT"

"$OUT"
