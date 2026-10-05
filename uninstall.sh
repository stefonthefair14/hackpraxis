#!/usr/bin/env bash
# Remove HackPraxis. Keeps your data dir unless you pass --purge.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/hackpraxis}"
BIN_DIR="${BIN_DIR:-/usr/bin}"
DATA_DIR="${DATA_DIR:-$APP_DIR/data}"

SUDO=""
if [ ! -w "$APP_DIR" ] || [ ! -w "$BIN_DIR" ]; then
  command -v sudo >/dev/null 2>&1 && SUDO="sudo"
fi

echo "==> Removing launcher $BIN_DIR/hackpraxis"
$SUDO rm -f "$BIN_DIR/hackpraxis"

if [ "${1:-}" = "--purge" ]; then
  echo "==> Removing everything, including data at $DATA_DIR"
  $SUDO rm -rf "$APP_DIR"
else
  echo "==> Removing app, keeping data at $DATA_DIR"
  $SUDO find "$APP_DIR" -mindepth 1 -maxdepth 1 ! -name data -exec rm -rf {} +
  echo "    (pass --purge to delete your saved projects too)"
fi
echo "Done."
