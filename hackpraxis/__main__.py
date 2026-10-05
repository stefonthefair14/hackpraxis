"""Launch the HackPraxis server.

    hackpraxis                    # after setup.sh — http://127.0.0.1:7337
    python -m hackpraxis          # from a source checkout
    hackpraxis --port 9000        # custom port
    hackpraxis --host 0.0.0.0     # expose on LAN (think before you do this)
"""

from __future__ import annotations

import argparse
import webbrowser

import uvicorn

from . import __port__, __version__
from .paths import data_dir

BANNER = r"""
 _   _            _    ____                 _
| | | | __ _  ___| | _|  _ \ _ __ __ ___  _(_)___
| |_| |/ _` |/ __| |/ / |_) | '__/ _` \ \/ / / __|
|  _  | (_| | (__|   <|  __/| | | (_| |>  <| \__ \
|_| |_|\__,_|\___|_|\_\_|   |_|  \__,_/_/\_\_|___/
"""

TAGLINE = "The only way to learn is to try"


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def print_banner(url: str) -> None:
    print(_c(BANNER, "1;38;5;42"))                     # phosphor green
    print("   " + _c(TAGLINE, "38;5;114"))             # soft green
    print()
    print("   " + _c(f"HackPraxis v{__version__}", "1;38;5;48") + _c("  ·  authorized testing only", "38;5;65"))
    print("   " + _c(url, "4;38;5;42"))
    print("   " + _c(f"data: {data_dir()}", "38;5;65"))
    print()


def main() -> None:
    ap = argparse.ArgumentParser(prog="hackpraxis", description="HackPraxis web testing console")
    ap.add_argument("--host", default="127.0.0.1",
                    help="Bind address (default 127.0.0.1 — local only).")
    ap.add_argument("--port", type=int, default=__port__,
                    help=f"Port (default {__port__}).")
    ap.add_argument("--no-browser", action="store_true",
                    help="Don't open a browser tab on start.")
    ap.add_argument("--reload", action="store_true", help="Dev auto-reload.")
    args = ap.parse_args()

    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.port}"
    print_banner(url)
    if args.host == "0.0.0.0":
        print("   " + _c("WARNING: bound to 0.0.0.0 — reachable from your network.", "1;38;5;196"))
        print()

    if not args.no_browser and not args.reload:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run("hackpraxis.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
