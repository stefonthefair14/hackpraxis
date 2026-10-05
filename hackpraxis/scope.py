"""Scope engine and project persistence.

This is the heart of HackPraxis's safety model. Nothing in the application is
allowed to send a request to a host unless that host is in the active
project's scope. Scope is enforced here, server-side, so no amount of
front-end tinkering can route a tool at an out-of-scope target.

Matching rules (kept deliberately simple and predictable):

  * An entry is matched against the *host* of a target (scheme, port, path and
    query are ignored for the decision).
  * ``example.com``        matches the host ``example.com`` exactly.
  * ``*.example.com``      matches any single-or-multi-label subdomain
                           (``api.example.com``, ``a.b.example.com``) but NOT
                           the apex ``example.com``. List both if you want both.
  * Entries are case-insensitive. A leading/trailing dot or whitespace is
    tolerated.
  * out-of-scope ALWAYS wins. If a host matches both lists it is OUT of scope.
  * An IP address is matched literally (no CIDR in v1 — list the hosts you were
    given).

A target is in scope only if it matches at least one in-scope entry and no
out-of-scope entry.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .paths import projects_dir

# Projects live in HackPraxis's persistent data directory (see paths.py) — not the
# home directory — so they survive restarts and reinstalls.
PROJECTS_DIR = projects_dir()

_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_.-]+")
# A valid host is DNS-style labels or an IP (IPv6 uses ':'); anything else
# (spaces, junk) is treated as unparseable and therefore out of scope.
_VALID_HOST = re.compile(r"^[a-z0-9.\-:]+$")


class ScopeError(Exception):
    """Raised when a target is rejected by the scope gate."""


def _slug(name: str) -> str:
    slug = _SAFE_NAME.sub("-", name.strip().lower()).strip("-.")
    return slug or "project"


def host_of(target: str) -> str:
    """Extract a bare hostname from a URL or host[:port] string."""
    t = (target or "").strip()
    if not t:
        return ""
    if "://" not in t:
        # Let urlparse treat it as a host rather than a path.
        t = "//" + t
    try:
        parsed = urlparse(t)
        host = (parsed.hostname or "").strip(".").lower()
    except ValueError:
        return ""
    if not host or not _VALID_HOST.match(host):
        return ""
    return host


def _entry_matches(host: str, entry: str) -> bool:
    entry = (entry or "").strip().strip(".").lower()
    if not entry or not host:
        return False
    if entry.startswith("*."):
        suffix = entry[1:]  # ".example.com"
        return host.endswith(suffix) and host != suffix.lstrip(".")
    return host == entry


@dataclass
class Scope:
    in_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)

    def decision(self, target: str) -> tuple[bool, str]:
        """Return (allowed, human-readable reason)."""
        host = host_of(target)
        if not host:
            return False, "Could not parse a hostname from the target."
        for entry in self.out_of_scope:
            if _entry_matches(host, entry):
                return False, f"'{host}' matches out-of-scope rule '{entry}'."
        for entry in self.in_scope:
            if _entry_matches(host, entry):
                return True, f"'{host}' matches in-scope rule '{entry}'."
        return False, f"'{host}' is not in the in-scope list for this project."

    def allows(self, target: str) -> bool:
        return self.decision(target)[0]

    def guard(self, target: str) -> None:
        """Raise ScopeError unless the target is allowed."""
        allowed, reason = self.decision(target)
        if not allowed:
            raise ScopeError(reason)


@dataclass
class Project:
    name: str
    scope: Scope = field(default_factory=Scope)
    notes: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def slug(self) -> str:
        return _slug(self.name)

    @property
    def dir(self) -> Path:
        return PROJECTS_DIR / self.slug

    @property
    def path(self) -> Path:
        return self.dir / "project.json"

    # --- persistence -----------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["slug"] = self.slug
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        scope = Scope(
            in_scope=list(d.get("scope", {}).get("in_scope", [])),
            out_of_scope=list(d.get("scope", {}).get("out_of_scope", [])),
        )
        return cls(
            name=d["name"],
            scope=scope,
            notes=d.get("notes", ""),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
        )

    def save(self) -> Path:
        self.updated_at = time.time()
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "scans").mkdir(exist_ok=True)
        self.path.write_text(json.dumps(self.to_dict(), indent=2))
        return self.path


def project_dir(slug: str) -> Path:
    return PROJECTS_DIR / _slug(slug)


def list_projects() -> list[dict]:
    out = []
    for d in sorted(PROJECTS_DIR.iterdir() if PROJECTS_DIR.exists() else []):
        pj = d / "project.json"
        if not pj.is_file():
            continue
        try:
            data = json.loads(pj.read_text())
            out.append(
                {
                    "name": data.get("name", d.name),
                    "slug": data.get("slug", d.name),
                    "in_scope": data.get("scope", {}).get("in_scope", []),
                    "out_of_scope": data.get("scope", {}).get("out_of_scope", []),
                    "updated_at": data.get("updated_at", 0),
                }
            )
        except (json.JSONDecodeError, OSError):
            continue
    return out


def load_project(slug: str) -> Optional[Project]:
    path = project_dir(slug) / "project.json"
    if not path.exists():
        return None
    return Project.from_dict(json.loads(path.read_text()))


def delete_project(slug: str) -> bool:
    import shutil
    d = project_dir(slug)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False
