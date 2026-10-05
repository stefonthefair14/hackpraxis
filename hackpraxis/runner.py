"""Command construction and execution.

Modules describe *what* to run as a list of :class:`Step` objects. The runner
is the only place that actually touches ``subprocess``; before any step runs
its target is re-checked against the active project scope, server-side.

Design goals:
  * Transparency — every step carries the exact argv and a plain-English
    explanation of each token, so the UI can teach while it runs.
  * Safety — scope is enforced here, and binaries are looked up on PATH so a
    missing tool fails loudly instead of doing something surprising.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .scope import Scope, ScopeError


@dataclass
class Step:
    """A single command to be executed."""

    tool: str                       # binary that must be on PATH, e.g. "ffuf"
    argv: list[str]                 # full argument vector
    target: str                     # URL/host this step contacts (scope-checked)
    explain: list[dict] = field(default_factory=list)  # [{token, meaning}]
    parse: str = "raw"              # "raw" | "curl-metrics"
    label: str = ""                 # short human label for this step
    meta: dict = field(default_factory=dict)  # grouping info: endpoint, technique, link

    @property
    def display(self) -> str:
        return " ".join(shlex.quote(a) for a in self.argv)


@dataclass
class Plan:
    """What a module wants to do, ready for the UI and the runner."""

    module: str
    engine: str
    title: str
    summary: str
    steps: list[Step] = field(default_factory=list)


def tool_available(tool: str) -> bool:
    return shutil.which(tool) is not None


def missing_tools(plan: Plan) -> list[str]:
    needed = {s.tool for s in plan.steps}
    return sorted(t for t in needed if not tool_available(t))


def run_step(step: Step, scope: Scope, timeout: int = 45) -> dict:
    """Execute one step after enforcing scope. Never raises for tool errors."""
    # --- scope gate (server-side, authoritative) -----------------------
    try:
        scope.guard(step.target)
    except ScopeError as exc:
        return {
            "label": step.label,
            "display": step.display,
            "meta": step.meta,
            "blocked": True,
            "reason": str(exc),
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "metrics": None,
            "duration": 0.0,
        }

    if not tool_available(step.tool):
        return {
            "label": step.label,
            "display": step.display,
            "meta": step.meta,
            "blocked": False,
            "missing_tool": step.tool,
            "returncode": None,
            "stdout": "",
            "stderr": f"Required tool '{step.tool}' was not found on your PATH.",
            "metrics": None,
            "duration": 0.0,
        }

    start = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            step.argv,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = None
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = (exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")) \
            + f"\n[hackpraxis] step exceeded {timeout}s and was stopped."
    duration = round(time.time() - start, 2)

    result = {
        "label": step.label,
        "display": step.display,
        "meta": step.meta,
        "blocked": False,
        "returncode": rc,
        "timed_out": timed_out,
        "stdout": out[-20000:],       # cap payload returned to the browser
        "stderr": err[-8000:],
        "metrics": None,
        "duration": duration,
    }
    if step.parse == "curl-metrics":
        result["metrics"] = _parse_curl_metrics(out)
    return result


def run_steps(steps: list[Step], scope: Scope, timeout: int = 30,
              max_workers: int = 10) -> list[dict]:
    """Run many steps, concurrently where it is safe, preserving input order.

    A single long-running step (one ffuf/gobuster scan) just runs once. A large
    matrix of short curl probes (the bypass module) fans out across a small
    thread pool so the whole run returns in seconds rather than minutes.
    """
    if len(steps) <= 1:
        return [run_step(s, scope, timeout) for s in steps]
    workers = min(max_workers, len(steps))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda s: run_step(s, scope, timeout), steps))


def _parse_curl_metrics(out: str) -> dict | None:
    """Parse the ``%{http_code} %{size_download} %{time_total}`` writeout."""
    line = out.strip().splitlines()[-1] if out.strip() else ""
    parts = line.split()
    if len(parts) >= 2 and parts[0].isdigit():
        try:
            return {
                "status": int(parts[0]),
                "size": int(float(parts[1])),
                "time": float(parts[2]) if len(parts) >= 3 else None,
            }
        except ValueError:
            return None
    return None
