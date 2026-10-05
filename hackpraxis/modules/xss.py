"""Reflected XSS.

Two ways to learn it, side by side: try payloads live in the embedded iframe
(the real page, real browser context), and fire them as curl requests so you see
exactly what's being sent. HackPraxis injects each payload at the FUZZ point and
flags any that come back UNESCAPED - a strong reflected-XSS signal - which you
then confirm by hand in the iframe.

Target URLs come from the project's reachable pool (what enumeration found and
what the bypass step got through). Authorized targets only.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from ..runner import Plan, Step

DATA = Path(__file__).resolve().parent.parent / "data"
DEFAULT_WORDLIST = str(DATA / "wordlists" / "xss_payloads.txt")

META = {
    "id": "xss",
    "title": "XSS",
    "blurb": "Inject payloads into a FUZZ-marked parameter and spot unescaped reflection; try them live in the iframe.",
    "engines": [
        {"id": "curl", "label": "curl (reflection)", "tool": "curl",
         "hint": "Send each payload and check if it reflects unescaped."},
    ],
    "fields": [
        {"name": "target", "label": "Target URL (mark the point with FUZZ)", "type": "url_combo",
         "placeholder": "https://host.example.com/search?q=FUZZ", "required": True,
         "hint": "pick a reachable URL, or type one"},
        {"name": "wordlist", "label": "Payload list path", "type": "text",
         "placeholder": DEFAULT_WORDLIST, "default": DEFAULT_WORDLIST},
        {"name": "max_requests", "label": "Max payloads", "type": "number", "default": 40},
    ],
    "has_iframe": True,
    "run_timeout": 45,
}


def _read(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [s for s in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if s.strip() and not s.startswith("#")]


def build(params: dict) -> Plan:
    target = (params.get("target") or "").strip()
    if target and "://" not in target:
        target = "https://" + target
    wordlist = (params.get("wordlist") or DEFAULT_WORDLIST).strip()
    try:
        budget = max(1, min(int(params.get("max_requests") or 40), 200))
    except (TypeError, ValueError):
        budget = 40

    if "FUZZ" not in target:
        return Plan(module="xss", engine="curl", title="XSS (needs FUZZ)",
                    summary="Add the FUZZ keyword where the payload should go, e.g. ?q=FUZZ. "
                            "You can still try payloads by hand in the iframe.", steps=[])

    steps: list[Step] = []
    for payload in _read(Path(wordlist))[:budget]:
        link = target.replace("FUZZ", quote(payload, safe=""))
        steps.append(Step(
            tool="curl",
            argv=["curl", "-sS", "-k", "--max-time", "12", "-w", "HPSTATUS:%{http_code}", link],
            target=link, parse="raw", label=payload,
            meta={"payload": payload, "link": link, "technique": payload, "detect": "reflect"},
            explain=[{"token": "payload", "meaning": payload}],
        ))
    return Plan(module="xss", engine="curl", title="XSS reflection probe",
                summary=f"{len(steps)} payloads sent to the FUZZ point. A payload that reflects "
                        "unescaped is a lead - confirm it live in the iframe.", steps=steps)
