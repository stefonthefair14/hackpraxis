"""Content / endpoint enumeration — with ffuf.

HackPraxis teaches one enumeration tool well rather than several shallowly, and
ffuf is the one worth knowing: fast, scriptable, and precise about filtering
noise. Results are written to a JSON file, parsed, and turned into endpoint
lists you can see in the GUI; anything that comes back 401/403 flows straight to
the Bypass tab. Other enumerators (gobuster, httpx, feroxbuster, dirsearch) are
covered in the Learn tab.
"""

from __future__ import annotations

from pathlib import Path

from ..runner import Plan, Step

DATA = Path(__file__).resolve().parent.parent / "data"
DEFAULT_WORDLIST = str(DATA / "wordlists" / "content_common.txt")

META = {
    "id": "enumeration",
    "title": "Enumeration",
    "blurb": "Discover hidden paths, files and endpoints with ffuf.",
    "engines": [
        {"id": "ffuf", "label": "ffuf", "tool": "ffuf",
         "hint": "Fast path/content brute-forcer. Fuzzes the FUZZ keyword."},
    ],
    "fields": [
        {"name": "target", "label": "Target", "type": "scope_select",
         "placeholder": "https://target.example.com",
         "hint": "pick an in-scope host, or Custom",
         "required": True},
        {"name": "wordlist", "label": "Wordlist path", "type": "text",
         "placeholder": DEFAULT_WORDLIST, "default": DEFAULT_WORDLIST},
        {"name": "extensions", "label": "Extensions (comma-sep, optional)",
         "type": "text", "placeholder": "php,txt,bak"},
        {"name": "threads", "label": "Threads", "type": "number", "default": 40},
        {"name": "match_codes", "label": "Match status codes", "type": "text",
         "default": "200,204,301,302,307,401,403,405"},
    ],
    # Tells the app to parse the ffuf JSON output into findings after a run.
    "produces_findings": True,
}


def _exts(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [e.strip().lstrip(".") for e in raw.split(",") if e.strip()]


def with_scheme(target: str) -> str:
    """Prepend https:// when the target has no scheme of its own."""
    t = (target or "").strip()
    if t and "://" not in t:
        t = "https://" + t
    return t


def build(params: dict) -> Plan:
    target = with_scheme((params.get("target") or "").strip())
    wordlist = (params.get("wordlist") or DEFAULT_WORDLIST).strip()
    threads = str(params.get("threads") or 40)
    exts = _exts(params.get("extensions"))
    mc = (params.get("match_codes") or "200,204,301,302,307,401,403,405").strip()
    # The app injects an output path per run so results can be parsed back.
    outfile = (params.get("output_file") or "").strip()

    url = target if "FUZZ" in target else target.rstrip("/") + "/FUZZ"
    argv = ["ffuf", "-u", url, "-w", wordlist, "-t", threads, "-mc", mc]
    explain = [
        {"token": "-u <url>", "meaning": "URL to fuzz. FUZZ is replaced by each wordlist entry."},
        {"token": "-w <wordlist>", "meaning": "Wordlist supplying values for the FUZZ keyword."},
        {"token": f"-t {threads}", "meaning": "Concurrent requests. Higher is faster and noisier."},
        {"token": f"-mc {mc}", "meaning": "Only keep responses with these status codes (match codes)."},
    ]
    if exts:
        ext_arg = ",".join("." + e for e in exts)
        argv += ["-e", ext_arg]
        explain.append({"token": f"-e {ext_arg}",
                        "meaning": "Append each extension to every FUZZ value."})
    if outfile:
        argv += ["-o", outfile, "-of", "json"]
        explain.append({"token": "-o <file> -of json",
                        "meaning": "Write results to a JSON file. HackPraxis parses it into "
                                   "your endpoint lists (shown below and in the Bypass tab)."})

    step = Step(tool="ffuf", argv=argv, target=url, parse="raw",
                label="ffuf scan", explain=explain)
    return Plan(module="enumeration", engine="ffuf", title="ffuf content scan",
                summary="Fuzz paths/files from the wordlist. Findings are saved to the "
                        "project folder and appear below.",
                steps=[step])
