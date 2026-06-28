"""
Serve a .dc.html design page over http so components render (file:// blocks the fetch).
Called by `just preview`; can also be run directly.
"""

import argparse
import os
import sys
import urllib.parse
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Serve a .dc.html file over http for review."
    )
    parser.add_argument("file", help="Path to the .dc.html file to preview")
    parser.add_argument(
        "--port", type=int, default=8791, help="Port to serve on (default: 8791)"
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Print the URL but don't open the browser",
    )
    args = parser.parse_args()

    path = Path(args.file).resolve()
    if not path.exists():
        print(f"error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    folder = path.parent
    encoded_name = urllib.parse.quote(path.name)
    url = f"http://localhost:{args.port}/{encoded_name}"

    print(f"  file : {path}")
    print(f"  url  : {url}")
    print("Ctrl-C to stop.\n")

    if not args.no_open:
        webbrowser.open(url)

    os.chdir(folder)

    # Suppress the per-request log lines so the terminal stays readable
    class _Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass

    try:
        HTTPServer(("", args.port), _Quiet).serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
