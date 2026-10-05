"""Tests for the scope gate — the security-critical core."""

from hackpraxis.scope import Scope, host_of


def test_host_extraction():
    assert host_of("https://api.example.com/admin?x=1") == "api.example.com"
    assert host_of("example.com:8443/path") == "example.com"
    assert host_of("HTTP://Example.COM") == "example.com"
    assert host_of("not a url") == ""


def test_exact_and_wildcard():
    sc = Scope(in_scope=["*.example.com", "example.com"], out_of_scope=[])
    assert sc.allows("https://example.com")
    assert sc.allows("https://api.example.com")
    assert sc.allows("https://a.b.example.com")
    assert not sc.allows("https://example.com.evil.com")
    assert not sc.allows("https://notexample.com")


def test_wildcard_does_not_match_apex():
    sc = Scope(in_scope=["*.example.com"], out_of_scope=[])
    assert not sc.allows("https://example.com")
    assert sc.allows("https://www.example.com")


def test_out_of_scope_wins():
    sc = Scope(in_scope=["*.example.com"], out_of_scope=["secret.example.com"])
    assert sc.allows("https://api.example.com")
    assert not sc.allows("https://secret.example.com")


def test_empty_scope_blocks_everything():
    sc = Scope(in_scope=[], out_of_scope=[])
    assert not sc.allows("https://anything.com")


def test_unparseable_target_blocked():
    sc = Scope(in_scope=["example.com"], out_of_scope=[])
    assert not sc.allows("")
    assert not sc.allows("???")
