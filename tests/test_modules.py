"""Tests that each module builds correct, scope-tagged commands."""

from hackpraxis.modules import bypass_401_403, enumeration, path_traversal


def test_enumeration_is_ffuf_only():
    assert [e["id"] for e in enumeration.META["engines"]] == ["ffuf"]
    assert enumeration.META.get("produces_findings") is True


def test_ffuf_appends_fuzz_keyword():
    plan = enumeration.build({"engine": "ffuf", "target": "https://example.com"})
    assert plan.steps[0].tool == "ffuf"
    assert "FUZZ" in plan.steps[0].display


def test_ffuf_adds_json_output_when_requested():
    plan = enumeration.build({"engine": "ffuf", "target": "https://example.com",
                              "output_file": "/tmp/out.json"})
    d = plan.steps[0].display
    assert "-o /tmp/out.json" in d and "-of json" in d


def test_bypass_runs_over_forbidden_endpoints():
    plan = bypass_401_403.build({
        "engine": "curl", "endpoints": ["https://example.com/admin", "https://example.com/secret"],
        "use_headers": True, "use_paths": True, "use_methods": True,
    })
    assert plan.steps, "should build steps for the injected endpoints"
    techs = [s.meta["technique"] for s in plan.steps]
    assert any(t.startswith("baseline") for t in techs)
    assert any(t.startswith("header") for t in techs)
    assert any(t.startswith("path") for t in techs)
    assert any(t.startswith("method") for t in techs)
    # resolved links, never a {P}/{S} placeholder
    for s in plan.steps:
        assert "{P}" not in s.meta["link"] and "{S}" not in s.meta["link"]
        assert "example.com" in s.target
    # both endpoints represented
    assert {s.meta["endpoint"] for s in plan.steps} == {
        "https://example.com/admin", "https://example.com/secret"}


def test_bypass_empty_without_endpoints():
    plan = bypass_401_403.build({"engine": "curl", "endpoints": []})
    assert plan.steps == []


def test_bypass_extra_target_scheme_added():
    plan = bypass_401_403.build({"engine": "curl", "endpoints": [], "extra_target": "example.com/x",
                                 "use_headers": False, "use_paths": False, "use_methods": False})
    assert plan.steps and plan.steps[0].meta["endpoint"] == "https://example.com/x"


def test_bypass_respects_budget_per_endpoint():
    plan = bypass_401_403.build({
        "engine": "curl", "endpoints": ["https://example.com/admin"], "max_requests": 5,
    })
    assert len(plan.steps) <= 5


def test_enum_prepends_https():
    plan = enumeration.build({"engine": "ffuf", "target": "example.com"})
    assert plan.steps[0].display.startswith("ffuf -u https://example.com")


def test_traversal_requires_fuzz():
    plan = path_traversal.build({"engine": "ffuf", "target": "https://example.com/x"})
    assert plan.steps == []  # no FUZZ -> nothing to run


def test_traversal_builds_with_fuzz():
    plan = path_traversal.build({"engine": "ffuf", "target": "https://example.com/d?f=FUZZ"})
    assert plan.steps and plan.steps[0].tool == "ffuf"
    assert "-mr" in plan.steps[0].argv


def test_traversal_curl_substitutes_payload():
    plan = path_traversal.build({
        "engine": "curl", "target": "https://example.com/d?f=FUZZ", "max_requests": 3,
    })
    assert plan.steps and "FUZZ" not in plan.steps[0].target


# --- v2.0 injection modules -------------------------------------------------
from hackpraxis.modules import xss, sqli


def test_xss_builds_reflection_probes():
    plan = xss.build({"engine": "curl", "target": "https://ex.com/s?q=FUZZ", "max_requests": 5})
    assert plan.steps and len(plan.steps) <= 5
    for s in plan.steps:
        assert s.meta["detect"] == "reflect"
        assert "FUZZ" not in s.meta["link"]
        assert s.tool == "curl"


def test_xss_requires_fuzz():
    assert xss.build({"engine": "curl", "target": "https://ex.com/s"}).steps == []


def test_sqli_sqlmap_command():
    plan = sqli.build({"engine": "sqlmap", "target": "ex.com/item?id=1",
                       "level": 2, "risk": 2, "enum_dbs": True})
    argv = plan.steps[0].argv
    assert plan.steps[0].tool == "sqlmap"
    assert argv[:3] == ["sqlmap", "-u", "https://ex.com/item?id=1"]
    for flag in ("--batch", "--level", "2", "--risk", "--dbs"):
        assert flag in argv


def test_sqli_curl_detects_errors():
    plan = sqli.build({"engine": "curl", "target": "https://ex.com/i?id=FUZZ", "max_requests": 4})
    assert plan.steps and all(s.meta["detect"] == "sql-error" for s in plan.steps)


def test_sqli_curl_requires_fuzz():
    assert sqli.build({"engine": "curl", "target": "https://ex.com/i?id=1"}).steps == []
