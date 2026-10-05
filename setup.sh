#!/usr/bin/env bash
#
# HackPraxis installer.
#
# MOVES this folder to /opt/hackpraxis (the standard place for installed tools),
# builds an isolated virtual environment inside it, and drops a launcher at
# /usr/bin/hackpraxis so you can start it with one word:   hackpraxis
#
# Run it from the cloned folder:
#     chmod +x setup.sh
#     ./setup.sh
#
# Using a venv means the system Python is never touched, so you never hit the
# "externally-managed-environment" pip error.
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/hackpraxis}"
BIN_DIR="${BIN_DIR:-/usr/bin}"   # override with BIN_DIR=/usr/local/bin on macOS
DATA_DIR="$APP_DIR/data"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; else
    echo "This needs root to write $APP_DIR and $BIN_DIR. Re-run as root or install sudo." >&2
    exit 1
  fi
fi

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then echo "python3 not found. Install Python 3.10+ first." >&2; exit 1; fi

echo "==> Moving HackPraxis to $APP_DIR"
if [ "$SRC_DIR" = "$APP_DIR" ]; then
  echo "    already at $APP_DIR, skipping move"
else
  # Preserve saved projects across a reinstall.
  STASH=""
  if [ -d "$APP_DIR/data" ]; then
    STASH="$(mktemp -d)"
    $SUDO mv "$APP_DIR/data" "$STASH/data"
  fi
  $SUDO rm -rf "$APP_DIR"
  $SUDO mkdir -p "$(dirname "$APP_DIR")"
  $SUDO mv "$SRC_DIR" "$APP_DIR"
  if [ -n "$STASH" ]; then $SUDO mv "$STASH/data" "$APP_DIR/data"; rmdir "$STASH" 2>/dev/null || true; fi
fi

echo "==> Building virtual environment"
$SUDO "$PY" -m venv "$APP_DIR/.venv"
$SUDO "$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
echo "==> Installing HackPraxis (editable, runs in place from $APP_DIR)"
$SUDO "$APP_DIR/.venv/bin/pip" install --quiet -e "$APP_DIR"

echo "==> Creating persistent data directory at $DATA_DIR"
$SUDO mkdir -p "$DATA_DIR/projects" "$DATA_DIR/runs"
if [ -n "${SUDO_USER:-}" ]; then
  $SUDO chown -R "$SUDO_USER" "$DATA_DIR"
else
  $SUDO chmod -R 0777 "$DATA_DIR"
fi

echo "==> Installing launcher at $BIN_DIR/hackpraxis"
$SUDO mkdir -p "$BIN_DIR"
$SUDO tee "$BIN_DIR/hackpraxis" >/dev/null <<EOF
#!/usr/bin/env bash
# HackPraxis launcher
export HACKPRAXIS_HOME="\${HACKPRAXIS_HOME:-$DATA_DIR}"
exec "$APP_DIR/.venv/bin/hackpraxis" "\$@"
EOF
$SUDO chmod +x "$BIN_DIR/hackpraxis"

echo
echo "  HackPraxis installed to $APP_DIR"
echo "  Start it with:   hackpraxis"
echo "  Your data lives in:   $DATA_DIR"
echo
if ! command -v hackpraxis >/dev/null 2>&1; then
  echo "  (note: $BIN_DIR is not on your PATH yet. Add it, or run $BIN_DIR/hackpraxis directly.)"
fi
