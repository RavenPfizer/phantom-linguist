"""Tests for PHANTOM-LINGUIST Scanner Module."""

import os
import sys
import json
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.scanner import scan, _build_alias_map, _tokenize, get_severity_summary


@pytest.fixture
def keywords():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "keywords.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestBuildAliasMap:
    def test_canonical_maps_to_self(self, keywords):
        alias_map = _build_alias_map(keywords)
        assert alias_map["hack"] == "hack"
        assert alias_map["steal"] == "steal"
    
    def test_aliases_map_to_canonical(self, keywords):
        alias_map = _build_alias_map(keywords)
        assert alias_map["nyolong"] == "steal"
        assert alias_map["retas"] == "hack"
        assert alias_map["suntik"] == "inject"
        assert alias_map["mancing"] == "phishing"
    
    def test_case_insensitive(self, keywords):
        alias_map = _build_alias_map(keywords)
        # All keys should be lowercase
        for key in alias_map:
            assert key == key.lower()


class TestTokenize:
    def test_basic_split(self):
        tokens = _tokenize("gue mau hack server")
        assert tokens == ["gue", "mau", "hack", "server"]
    
    def test_strips_punctuation(self):
        tokens = _tokenize("nyolong, data! dari server.")
        assert "nyolong" in tokens
        assert "data" in tokens
    
    def test_preserves_underscores(self):
        tokens = _tokenize("fake_login dan privilege_escalation")
        assert "fake_login" in tokens
        assert "privilege_escalation" in tokens
    
    def test_lowercase(self):
        tokens = _tokenize("HACK Server INJECT DLL")
        assert all(t == t.lower() for t in tokens)


class TestScan:
    def test_detects_english_keywords(self, keywords):
        results = scan("I want to hack the server and inject a DLL", keywords)
        canonicals = {r["canonical"] for r in results}
        assert "hack" in canonicals
        assert "inject" in canonicals
    
    def test_detects_indonesian_aliases(self, keywords):
        results = scan("gue mau nyolong data pake suntik DLL", keywords)
        canonicals = {r["canonical"] for r in results}
        assert "steal" in canonicals
        assert "inject" in canonicals
    
    def test_deduplicates(self, keywords):
        results = scan("hack retas jebol bongkar", keywords)
        # All these are aliases of "hack", should only appear once
        canonicals = [r["canonical"] for r in results]
        assert canonicals.count("hack") == 1
    
    def test_returns_metadata(self, keywords):
        results = scan("exploit the vulnerability", keywords)
        assert len(results) >= 1
        r = results[0]
        assert "domain" in r
        assert "severity" in r
        assert "technical_terms" in r
        assert "academic_nouns" in r
        assert "api_references" in r
    
    def test_empty_prompt(self, keywords):
        results = scan("", keywords)
        assert results == []
    
    def test_no_keywords(self, keywords):
        results = scan("the weather is nice today", keywords)
        assert results == []
    
    def test_mixed_language(self, keywords):
        results = scan("gue mau bypass WAF trus dump databasenya", keywords)
        canonicals = {r["canonical"] for r in results}
        assert "bypass" in canonicals
        assert "dump" in canonicals


class TestSeveritySummary:
    def test_counts_severity(self, keywords):
        results = scan("hack exploit scrape sniff", keywords)
        summary = get_severity_summary(results)
        assert "hard" in summary
        assert "soft" in summary
        assert summary["hard"] + summary["soft"] == len(results)
