"""Where HackPraxis keeps its persistent, writable data.

Deliberately *not* the user's home directory. Resolution order:

  1. ``$HACKPRAXIS_HOME`` if set.
  2. ``/opt/hackpraxis/data`` — created by ``setup.sh`` on install.
  3. ``<repo>/.hackpraxis-data`` — running from a source checkout (the project
     directory, still not the home dir).
  4. ``<tmp>/hackpraxis`` — last resort so the app always starts.

The first candidate we can actually create/write wins, so HackPraxis runs whether
it was installed system-wide or cloned and launched in place.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_PKG = Path(__file__).resolve().parent


def _candidates() -> list[Path]:
    out = []
    env = os.environ.get("HACKPRAXIS_HOME")
    if env:
        out.append(Path(env).expanduser())
    out.append(Path("/opt/hackpraxis/data"))
    out.append(_PKG.parent / ".hackpraxis-data")
    out.append(Path(tempfile.gettempdir()) / "hackpraxis")
    return out


def data_dir() -> Path:
    for cand in _candidates():
        try:
            (cand / "projects").mkdir(parents=True, exist_ok=True)
            (cand / "runs").mkdir(parents=True, exist_ok=True)
            return cand
        except (OSError, PermissionError):
            continue
    raise RuntimeError("HackPraxis could not find a writable data directory.")


def projects_dir() -> Path:
    return data_dir() / "projects"


def runs_dir() -> Path:
    return data_dir() / "runs"
