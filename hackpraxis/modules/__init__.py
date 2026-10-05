"""Module registry.

Each module exposes a ``META`` dict (how the UI renders it) and a ``build``
function (params -> Plan). Register new modules here to make them appear in the
sidebar; the rest of the app is module-agnostic.
"""

from __future__ import annotations

from . import bypass_401_403, enumeration, path_traversal, sqli, xss

_MODULES = {
    enumeration.META["id"]: enumeration,
    bypass_401_403.META["id"]: bypass_401_403,
    path_traversal.META["id"]: path_traversal,
    xss.META["id"]: xss,
    sqli.META["id"]: sqli,
}

# Order shown in the UI.
ORDER = ["enumeration", "bypass_401_403", "path_traversal", "xss", "sqli"]


def catalog() -> list[dict]:
    return [_MODULES[mid].META for mid in ORDER if mid in _MODULES]


def get(module_id: str):
    return _MODULES.get(module_id)
