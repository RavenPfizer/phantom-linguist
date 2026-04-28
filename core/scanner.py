"""
PHANTOM-LINGUIST: Scanner Module
Detects hot keywords (multilingual) in raw prompts.
Builds reverse alias map for Indo+English+expandable input.
"""

import re
from typing import Any


def _build_alias_map(keywords: dict[str, Any]) -> dict[str, str]:
    """Build reverse lookup: alias → canonical keyword."""
    alias_map: dict[str, str] = {}
    for canonical, data in keywords.items():
        # Canonical keyword maps to itself
        alias_map[canonical.lower()] = canonical
        # Each alias also maps to canonical
        for alias in data.get("aliases", []):
            alias_map[alias.lower()] = canonical
    return alias_map


def _tokenize(prompt: str) -> list[str]:
    """Split prompt into scannable tokens.
    
    Handles underscored compound terms (e.g., 'fake_login'),
    and strips basic punctuation while preserving technical terms.
    """
    # Lowercase the whole prompt
    lowered = prompt.lower()
    # Split on whitespace, keeping underscored compounds
    raw_tokens = lowered.split()
    tokens = []
    for tok in raw_tokens:
        # Strip trailing punctuation but keep underscores and hyphens
        cleaned = re.sub(r'[^\w\-]', '', tok)
        if cleaned:
            tokens.append(cleaned)
    return tokens


def scan(prompt: str, keywords: dict[str, Any]) -> list[dict[str, Any]]:
    """Scan prompt for hot keywords. Returns detected terms with metadata.
    
    Args:
        prompt: Raw user prompt (any language)
        keywords: Loaded keywords.json dict
    
    Returns:
        List of detected keyword matches with:
        - original: the word as found in the prompt
        - canonical: the canonical keyword it maps to
        - domain: security domain category
        - severity: hard/soft trigger level
        - technical_terms: list of academic replacements
        - academic_nouns: list of formal noun phrases
        - api_references: list of legitimate tool/API names
    """
    alias_map = _build_alias_map(keywords)
    tokens = _tokenize(prompt)
    
    found: list[dict[str, Any]] = []
    seen_canonicals: set[str] = set()
    
    for token in tokens:
        if token in alias_map:
            canonical = alias_map[token]
            # Deduplicate: only report each canonical once
            if canonical not in seen_canonicals:
                seen_canonicals.add(canonical)
                kw_data = keywords[canonical]
                found.append({
                    "original": token,
                    "canonical": canonical,
                    "domain": kw_data.get("domain", "unknown"),
                    "severity": kw_data.get("severity", "soft"),
                    "technical_terms": kw_data.get("technical_terms", []),
                    "academic_nouns": kw_data.get("academic_nouns", []),
                    "api_references": kw_data.get("api_references", []),
                })
    
    return found


def get_severity_summary(scan_results: list[dict]) -> dict[str, int]:
    """Count hard vs soft triggers in scan results."""
    counts = {"hard": 0, "soft": 0}
    for r in scan_results:
        sev = r.get("severity", "soft")
        counts[sev] = counts.get(sev, 0) + 1
    return counts
