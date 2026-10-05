"""Tests for scan-findings parsing and persistence."""

import json
import os
import tempfile

import pytest


@pytest.fixture()
def project(tmp_path, monkeypatch):
    # Point the data dir at a temp location before importing the stores.
    monkeypatch.setenv("HACKPRAXIS_HOME", str(tmp_path))
    import importlib
    from hackpraxis import paths, scope, findings
    importlib.reload(paths); importlib.reload(scope); importlib.reload(findings)
    p = scope.Project(name="Demo", scope=scope.Scope(in_scope=["example.com"]))
    p.save()
    return scope, findings, p


def _ffuf_file(path, rows):
    path.write_text(json.dumps({"results": [
        {"url": u, "status": s, "length": l} for (u, s, l) in rows
    ]}))


def test_parse_and_merge(project, tmp_path):
    scope, findings, p = project
    f = tmp_path / "scan.json"
    _ffuf_file(f, [
        ("https://example.com/admin", 403, 9),
        ("https://example.com/login", 200, 500),
        ("https://example.com/secret", 401, 12),
    ])
    parsed = findings.parse_ffuf_json(f)
    assert len(parsed) == 3
    result = findings.merge_results(p.slug, parsed)
    assert len(result["discovered"]) == 3
    # only 401/403 are forbidden
    forb_urls = {r["url"] for r in result["forbidden"]}
    assert forb_urls == {"https://example.com/admin", "https://example.com/secret"}

    # real .txt files exist in the project folder
    pdir = scope.project_dir(p.slug)
    assert (pdir / "discovered.txt").exists()
    assert (pdir / "forbidden.txt").exists()
    assert "admin" in (pdir / "forbidden.txt").read_text()


def test_merge_is_idempotent_and_persists(project, tmp_path):
    scope, findings, p = project
    f = tmp_path / "scan.json"
    _ffuf_file(f, [("https://example.com/a", 200, 1)])
    findings.merge_results(p.slug, findings.parse_ffuf_json(f))
    findings.merge_results(p.slug, findings.parse_ffuf_json(f))  # same again
    assert len(findings.read_findings(p.slug)["discovered"]) == 1


def test_project_stored_as_folder(project):
    scope, findings, p = project
    pdir = scope.project_dir(p.slug)
    assert (pdir / "project.json").is_file()
    assert p.slug in [x["slug"] for x in scope.list_projects()]


def test_reachable_pool(project, tmp_path):
    scope, findings, p = project
    # enum results: 200 + 301 become reachable; 403 does not
    f = tmp_path / "s.json"
    f.write_text(__import__("json").dumps({"results": [
        {"url": "https://example.com/a", "status": 200, "length": 1},
        {"url": "https://example.com/b", "status": 301, "length": 0},
        {"url": "https://example.com/admin", "status": 403, "length": 9},
    ]}))
    findings.merge_results(p.slug, findings.parse_ffuf_json(f))
    pool = {r["url"] for r in findings.read_reachable(p.slug)}
    assert "https://example.com/a" in pool and "https://example.com/b" in pool
    assert "https://example.com/admin" not in pool

    # a successful bypass gets added too
    results = [
        {"meta": {"endpoint": "https://example.com/admin", "technique": "baseline (GET)"}, "metrics": {"status": 403}},
        {"meta": {"endpoint": "https://example.com/admin", "technique": "path trailing slash",
                  "link": "https://example.com/admin/"}, "metrics": {"status": 200}},
    ]
    won = findings.reachable_from_bypass(results)
    assert won and won[0]["url"] == "https://example.com/admin/"
    findings.add_reachable(p.slug, won)
    assert "https://example.com/admin/" in {r["url"] for r in findings.read_reachable(p.slug)}
