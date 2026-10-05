"""Scan findings: parse ffuf output and persist endpoint lists per project.

After an enumeration scan, HackPraxis reads ffuf's JSON output file, extracts
each discovered endpoint with its status code, and writes two plain-text lists
into the project's folder (under the persistent data dir):

    projects/<slug>/discovered.txt   every endpoint found   "<status>\t<length>\t<url>"
    projects/<slug>/forbidden.txt    only 401 / 403 ones    "<status>\t<url>"

These are real, human-readable files you can open, diff or feed to other tools.
The GUI reads them back so your results survive restarts: the Enumeration tab
shows everything discovered, and the 401/403 Bypass tab shows the forbidden
endpoints as ready-to-test targets.
"""

from __future__ import annotations

import json
from pathlib import Path

from .scope import project_dir

FORBIDDEN_CODES = {401, 403}


def _discovered_file(slug: str) -> Path:
    return project_dir(slug) / "discovered.txt"


def _forbidden_file(slug: str) -> Path:
    return project_dir(slug) / "forbidden.txt"


def parse_ffuf_json(path: Path) -> list[dict]:
    """Parse a ffuf ``-of json`` output file into [{url, status, length}]."""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return []
    out = []
    for r in data.get("results", []) or []:
        url = r.get("url") or ""
        if not url:
            continue
        out.append({
            "url": url,
            "status": int(r.get("status", 0) or 0),
            "length": int(r.get("length", 0) or 0),
        })
    return out


def _read_discovered(slug: str) -> dict[str, dict]:
    """Return {url: {url, status, length}} from the saved discovered.txt."""
    out: dict[str, dict] = {}
    f = _discovered_file(slug)
    if not f.exists():
        return out
    for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 3 and parts[0].isdigit():
            status, length, url = parts
            out[url] = {"url": url, "status": int(status), "length": int(length or 0)}
    return out


def _write(slug: str, items: dict[str, dict]) -> None:
    pdir = project_dir(slug)
    pdir.mkdir(parents=True, exist_ok=True)
    rows = sorted(items.values(), key=lambda x: (x["status"], x["url"]))
    _discovered_file(slug).write_text(
        "".join(f"{r['status']}\t{r['length']}\t{r['url']}\n" for r in rows),
        encoding="utf-8",
    )
    forb = [r for r in rows if r["status"] in FORBIDDEN_CODES]
    _forbidden_file(slug).write_text(
        "".join(f"{r['status']}\t{r['url']}\n" for r in forb),
        encoding="utf-8",
    )


def merge_results(slug: str, results: list[dict]) -> dict:
    """Merge new scan results into the project's saved lists. Returns findings."""
    items = _read_discovered(slug)
    for r in results:
        items[r["url"]] = r          # latest scan wins for a given URL
    _write(slug, items)
    # reachable pool: anything that actually responded (2xx/3xx) is a candidate
    # target for the injection steps.
    add_reachable(slug, [
        {"url": r["url"], "label": f"enum {r['status']}"}
        for r in results if 200 <= r["status"] < 400
    ])
    return read_findings(slug)


def read_findings(slug: str) -> dict:
    items = _read_discovered(slug)
    rows = sorted(items.values(), key=lambda x: (x["status"], x["url"]))
    forbidden = [{"url": r["url"], "status": r["status"]}
                 for r in rows if r["status"] in FORBIDDEN_CODES]
    return {"discovered": rows, "forbidden": forbidden, "reachable": read_reachable(slug)}


# --------------------------------------------------------------------------
# reachable pool  (projects/<slug>/reachable.txt  ->  "<url>\t<label>")
# This is how each step whittles the target set down for the next: enumeration
# adds the 2xx/3xx URLs, the bypass step adds every endpoint it got through,
# and the injection steps read this pool into their target dropdown.
# --------------------------------------------------------------------------
def _reachable_file(slug: str) -> Path:
    return project_dir(slug) / "reachable.txt"


def read_reachable(slug: str) -> list[dict]:
    f = _reachable_file(slug)
    if not f.exists():
        return []
    out, seen = [], set()
    for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        url, _, label = line.partition("\t")
        url = url.strip()
        if url and url not in seen:
            seen.add(url)
            out.append({"url": url, "label": label.strip()})
    return out


def add_reachable(slug: str, items: list[dict]) -> list[dict]:
    """Merge {url,label} entries into the pool (first label for a URL wins)."""
    pool = {r["url"]: r for r in read_reachable(slug)}
    for it in items:
        url = (it.get("url") or "").strip()
        if url and url not in pool:
            pool[url] = {"url": url, "label": (it.get("label") or "").strip()}
    rows = sorted(pool.values(), key=lambda x: x["url"])
    project_dir(slug).mkdir(parents=True, exist_ok=True)
    _reachable_file(slug).write_text(
        "".join(f"{r['url']}\t{r['label']}\n" for r in rows), encoding="utf-8")
    return rows


def reachable_from_bypass(results: list[dict]) -> list[dict]:
    """Pick the successful bypasses (2xx/3xx differing from the endpoint baseline)."""
    by_ep: dict[str, list[dict]] = {}
    for r in results:
        ep = (r.get("meta") or {}).get("endpoint")
        if ep:
            by_ep.setdefault(ep, []).append(r)
    out = []
    for ep, rows in by_ep.items():
        base = next((r for r in rows
                     if (r.get("meta") or {}).get("technique", "").startswith("baseline")), None)
        bstatus = base["metrics"]["status"] if base and base.get("metrics") else None
        for r in rows:
            m = r.get("metrics"); meta = r.get("meta") or {}
            if m and bstatus is not None and m["status"] != bstatus and m["status"] < 400:
                out.append({"url": meta.get("link", ep),
                            "label": "bypass: " + meta.get("technique", "")})
    return out


def clear_findings(slug: str) -> None:
    for f in (_discovered_file(slug), _forbidden_file(slug), _reachable_file(slug)):
        if f.exists():
            f.unlink()
