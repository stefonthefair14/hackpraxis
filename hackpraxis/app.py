"""HackPraxis FastAPI application.

Serves the single-page GUI and a small JSON API. The API is intentionally thin:
the browser asks for the module catalog and learning content, manages projects,
previews a plan (to show the command + flag explanations), and runs a plan. The
scope gate is enforced server-side in :mod:`hackpraxis.runner` for every step.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import re
import time
from pathlib import Path as _P

from . import __port__, __version__, md, modules
from . import findings as findings_store
from .runner import missing_tools, run_steps, tool_available
from .scope import (Project, Scope, delete_project, list_projects, load_project,
                    project_dir)

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
CONTENT = HERE / "content"

app = FastAPI(title="HackPraxis", version=__version__)

KNOWN_TOOLS = ["ffuf", "curl", "sqlmap"]


# --------------------------------------------------------------------------
# request models
# --------------------------------------------------------------------------
class ProjectIn(BaseModel):
    name: str
    in_scope: list[str] = []
    out_of_scope: list[str] = []
    notes: str = ""


class PlanIn(BaseModel):
    module: str
    engine: str
    params: dict = {}
    project_slug: str | None = None


class ScopeCheckIn(BaseModel):
    project_slug: str
    target: str


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _plan_payload(plan) -> dict:
    return {
        "module": plan.module,
        "engine": plan.engine,
        "title": plan.title,
        "summary": plan.summary,
        "missing_tools": missing_tools(plan),
        "steps": [
            {
                "label": s.label,
                "tool": s.tool,
                "display": s.display,
                "target": s.target,
                "explain": s.explain,
                "meta": s.meta,
            }
            for s in plan.steps
        ],
    }


def _build_plan(body: PlanIn):
    module = modules.get(body.module)
    if module is None:
        raise HTTPException(404, f"Unknown module '{body.module}'")
    params = dict(body.params)
    params["engine"] = body.engine
    return module.build(params)


def _produces_findings(module_id: str) -> bool:
    mod = modules.get(module_id)
    return bool(mod and mod.META.get("produces_findings"))


def _consumes_forbidden(module_id: str) -> bool:
    mod = modules.get(module_id)
    return bool(mod and mod.META.get("consumes_forbidden"))


def _inject_forbidden(body: PlanIn) -> None:
    """Feed the project's saved 401/403 endpoints into a bypass-style module."""
    if _consumes_forbidden(body.module) and body.project_slug and "endpoints" not in body.params:
        forb = findings_store.read_findings(body.project_slug).get("forbidden", [])
        body.params = {**body.params, "endpoints": [f["url"] for f in forb]}


def _scan_outfile(slug: str) -> str:
    d = project_dir(slug) / "scans"
    d.mkdir(parents=True, exist_ok=True)
    return str(d / f"enum_{int(time.time())}.json")


# Common SQL error signatures (error-based SQLi detection for the curl engine).
_SQL_ERR = re.compile(
    r"SQL syntax|mysql_fetch|ORA-\d{4,}|SQLServer|SQLite3?::|PG::|psql:|"
    r"Unclosed quotation|quoted string not properly terminated|"
    r"syntax error at or near|Warning.*\bpg_|supplied argument is not a valid",
    re.I)


def _split_status(out: str):
    """Pull the trailing 'HPSTATUS:nnn' writeout off a captured body."""
    marker = "HPSTATUS:"
    if marker in out:
        body, _, st = out.rpartition(marker)
        try:
            return body, int(st.strip()[:3])
        except ValueError:
            return body, None
    return out, None


def _post_process(module_id: str, results: list[dict]) -> None:
    """Flag reflected XSS / SQL errors from captured curl bodies, then drop the
    body so the response stays small."""
    for r in results:
        meta = r.get("meta") or {}
        det = meta.get("detect")
        if not det or r.get("blocked") or r.get("missing_tool"):
            continue
        body, status = _split_status(r.get("stdout", "") or "")
        if det == "reflect":
            pl = meta.get("payload", "")
            r["detect_result"] = {"status": status, "hit": bool(pl and pl in body)}
        elif det == "sql-error":
            r["detect_result"] = {"status": status, "hit": bool(_SQL_ERR.search(body or ""))}
        r["stdout"] = ""


# --------------------------------------------------------------------------
# static / index
# --------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


# --------------------------------------------------------------------------
# meta
# --------------------------------------------------------------------------
@app.get("/api/meta")
def meta():
    return {"name": "HackPraxis", "version": __version__, "port": __port__}


@app.get("/api/tools")
def tools():
    return {t: tool_available(t) for t in KNOWN_TOOLS}


@app.get("/api/modules")
def module_catalog():
    return modules.catalog()


@app.get("/api/content/{name}")
def content(name: str):
    if not name.isidentifier():
        raise HTTPException(400, "bad name")
    path = CONTENT / f"{name}.md"
    if not path.exists():
        raise HTTPException(404, "no such content")
    return {"html": md.render(path.read_text(encoding="utf-8"))}


# --------------------------------------------------------------------------
# projects
# --------------------------------------------------------------------------
@app.get("/api/projects")
def projects():
    return list_projects()


@app.post("/api/projects")
def save_project(body: ProjectIn):
    if not body.name.strip():
        raise HTTPException(400, "Project needs a name.")
    proj = Project(
        name=body.name.strip(),
        scope=Scope(
            in_scope=[x.strip() for x in body.in_scope if x.strip()],
            out_of_scope=[x.strip() for x in body.out_of_scope if x.strip()],
        ),
        notes=body.notes,
    )
    proj.save()
    return proj.to_dict()


@app.get("/api/projects/{slug}")
def get_project(slug: str):
    proj = load_project(slug)
    if proj is None:
        raise HTTPException(404, "no such project")
    return proj.to_dict()


@app.delete("/api/projects/{slug}")
def remove_project(slug: str):
    return {"deleted": delete_project(slug)}


@app.post("/api/scope/check")
def scope_check(body: ScopeCheckIn):
    proj = load_project(body.project_slug)
    if proj is None:
        raise HTTPException(404, "no such project")
    allowed, reason = proj.scope.decision(body.target)
    return {"allowed": allowed, "reason": reason}


# --------------------------------------------------------------------------
# plan / run
# --------------------------------------------------------------------------
@app.get("/api/projects/{slug}/findings")
def get_findings(slug: str):
    if load_project(slug) is None:
        raise HTTPException(404, "no such project")
    return findings_store.read_findings(slug)


@app.post("/api/plan")
def plan(body: PlanIn):
    """Build a plan and return it WITHOUT running — for the command preview."""
    if _produces_findings(body.module) and body.project_slug and "output_file" not in body.params:
        body.params = {**body.params, "output_file": _scan_outfile(body.project_slug)}
    _inject_forbidden(body)
    return _plan_payload(_build_plan(body))


@app.post("/api/run")
def run(body: PlanIn):
    """Build and execute a plan. Requires a project so scope can be enforced."""
    if not body.project_slug:
        raise HTTPException(400, "Select a project first — scope is required to run.")
    proj = load_project(body.project_slug)
    if proj is None:
        raise HTTPException(404, "no such project")

    # Modules that produce findings (enumeration) get a per-run JSON output path
    # inside the project folder; we parse it afterward.
    outfile = None
    if _produces_findings(body.module):
        outfile = _scan_outfile(body.project_slug)
        body.params = {**body.params, "output_file": outfile}
    _inject_forbidden(body)

    plan = _build_plan(body)
    if not plan.steps:
        return {"plan": _plan_payload(plan), "results": [], "note": plan.summary}

    allowed, reason = proj.scope.decision(plan.steps[0].target)
    mod = modules.get(body.module)
    run_timeout = int(mod.META.get("run_timeout", 30)) if mod else 30
    results = run_steps(plan.steps, proj.scope, timeout=run_timeout)
    _post_process(body.module, results)
    ran = sum(1 for r in results if not r.get("blocked") and not r.get("missing_tool"))
    blocked = sum(1 for r in results if r.get("blocked"))

    payload = {
        "plan": _plan_payload(plan),
        "results": results,
        "summary": {"total": len(results), "ran": ran, "blocked": blocked,
                    "first_target_ok": allowed, "first_target_reason": reason},
    }

    # The bypass step whittles the target set down: every endpoint it got
    # through is saved to the project's reachable pool for the injection steps.
    if _consumes_forbidden(body.module):
        won = findings_store.reachable_from_bypass(results)
        if won:
            findings_store.add_reachable(body.project_slug, won)
        payload["reachable_added"] = len(won)

    # Parse enumeration output into the project's persisted endpoint lists.
    if outfile:
        parsed = findings_store.parse_ffuf_json(_P(outfile))
        if parsed:
            findings_store.merge_results(body.project_slug, parsed)
        payload["findings"] = findings_store.read_findings(body.project_slug)
        payload["new_this_scan"] = len(parsed)

    return payload
