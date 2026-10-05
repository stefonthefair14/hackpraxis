"""SQL injection.

Learn it from both ends: drive the automated tool (sqlmap) and see the exact
command and what every flag does, OR hand-send classic test payloads with curl
and watch for database error messages. And try it live in the embedded iframe,
so you see the app's real behaviour, not just a status code.

Target URLs come from the project's reachable pool. Authorized targets only.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from ..runner import Plan, Step

DATA = Path(__file__).resolve().parent.parent / "data"
DEFAULT_WORDLIST = str(DATA / "wordlists" / "sqli_payloads.txt")


def _with_scheme(t: str) -> str:
    t = (t or "").strip()
    return ("https://" + t) if (t and "://" not in t) else t


META = {
    "id": "sqli",
    "title": "SQL Injection",
    "blurb": "Probe a parameter with sqlmap, or send manual test payloads with curl; try it live in the iframe.",
    "engines": [
        {"id": "sqlmap", "label": "sqlmap", "tool": "sqlmap",
         "hint": "Automated SQLi detection & exploitation."},
        {"id": "curl", "label": "curl (manual)", "tool": "curl",
         "hint": "Send classic payloads at a FUZZ point; flags DB error messages."},
    ],
    "fields": [
        {"name": "target", "label": "Target URL", "type": "url_combo",
         "placeholder": "https://host.example.com/item?id=1   (curl: mark point with FUZZ)",
         "required": True, "hint": "pick a reachable URL, or type one"},
        {"name": "level", "label": "sqlmap --level (1-5)", "type": "number", "default": 1,
         "engines": ["sqlmap"]},
        {"name": "risk", "label": "sqlmap --risk (1-3)", "type": "number", "default": 1,
         "engines": ["sqlmap"]},
        {"name": "enum_dbs", "label": "Enumerate databases (--dbs)", "type": "checkbox",
         "default": False, "engines": ["sqlmap"]},
        {"name": "wordlist", "label": "Payload list path", "type": "text",
         "placeholder": DEFAULT_WORDLIST, "default": DEFAULT_WORDLIST, "engines": ["curl"]},
        {"name": "max_requests", "label": "Max payloads", "type": "number", "default": 30,
         "engines": ["curl"]},
    ],
    "has_iframe": True,
    "run_timeout": 180,
}


def _read(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [s for s in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if s.strip() and not s.startswith("#")]


def build(params: dict) -> Plan:
    engine = params.get("engine", "sqlmap")
    target = _with_scheme(params.get("target") or "")

    if engine == "curl":
        if "FUZZ" not in target:
            return Plan(module="sqli", engine="curl", title="SQLi (needs FUZZ)",
                        summary="Add FUZZ where the payload should go, e.g. ?id=FUZZ. "
                                "You can still try payloads by hand in the iframe.", steps=[])
        wordlist = (params.get("wordlist") or DEFAULT_WORDLIST).strip()
        try:
            budget = max(1, min(int(params.get("max_requests") or 30), 200))
        except (TypeError, ValueError):
            budget = 30
        steps: list[Step] = []
        for payload in _read(Path(wordlist))[:budget]:
            link = target.replace("FUZZ", quote(payload, safe=""))
            steps.append(Step(
                tool="curl", argv=["curl", "-sS", "-k", "--max-time", "12",
                                   "-w", "HPSTATUS:%{http_code}", link],
                target=link, parse="raw", label=payload,
                meta={"payload": payload, "link": link, "technique": payload, "detect": "sql-error"},
                explain=[{"token": "payload", "meaning": payload}]))
        return Plan(module="sqli", engine="curl", title="SQLi manual probe",
                    summary=f"{len(steps)} payloads sent to the FUZZ point. A database error in the "
                            "response is a lead - confirm by hand or switch to sqlmap.", steps=steps)

    # default: sqlmap
    if not target:
        return Plan(module="sqli", engine="sqlmap", title="SQLi (needs target)",
                    summary="Pick or type a target URL with a parameter (e.g. ?id=1).", steps=[])
    try:
        level = max(1, min(int(params.get("level") or 1), 5))
        risk = max(1, min(int(params.get("risk") or 1), 3))
    except (TypeError, ValueError):
        level, risk = 1, 1
    argv = ["sqlmap", "-u", target, "--batch", "--level", str(level), "--risk", str(risk)]
    explain = [
        {"token": "-u <url>", "meaning": "Target URL. sqlmap tests its parameters for SQLi."},
        {"token": "--batch", "meaning": "Never prompt; take the default answer to every question."},
        {"token": f"--level {level}", "meaning": "How hard to look (1-5): more places tested, more requests."},
        {"token": f"--risk {risk}", "meaning": "How aggressive the payloads are (1-3). Higher can modify data."},
    ]
    if params.get("enum_dbs"):
        argv.append("--dbs")
        explain.append({"token": "--dbs", "meaning": "If injectable, list the database names."})
    step = Step(tool="sqlmap", argv=argv, target=target, parse="raw", label="sqlmap",
                meta={"link": target, "technique": "sqlmap"}, explain=explain)
    return Plan(module="sqli", engine="sqlmap", title="sqlmap scan",
                summary="Run sqlmap against the target's parameters. Read the output; if it finds an "
                        "injection point, that's your confirmed finding.", steps=[step])
