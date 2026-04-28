"""
PHANTOM-LINGUIST: Validator Module
Validates all config files on startup.
Clear errors, no silent crashes.
"""

import json
import os
import sys
from typing import Any

# Required fields per keyword entry
KEYWORD_REQUIRED = ["domain", "severity", "technical_terms", "academic_nouns", "api_references"]
KEYWORD_SEVERITY_VALUES = {"hard", "soft"}

# Required fields per strategy entry
STRATEGY_REQUIRED = ["name", "template", "tone", "effectiveness"]
STRATEGY_MODELS = {"claude", "gpt", "gemini", "copilot"}

# Required fields per primer domain
PRIMER_REQUIRED = ["enabled", "questions"]


def _load_json(path: str) -> dict:
    """Load and parse a JSON file, raising clear errors."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")


def validate_keywords(config_dir: str) -> tuple[dict, list[str]]:
    """Validate keywords.json. Returns (data, errors)."""
    path = os.path.join(config_dir, "keywords.json")
    data = _load_json(path)
    errors: list[str] = []
    
    if not isinstance(data, dict) or len(data) == 0:
        errors.append(f"keywords.json: Must be a non-empty object")
        return data, errors
    
    for keyword, entry in data.items():
        if not isinstance(entry, dict):
            errors.append(f"keywords.json: '{keyword}' must be an object")
            continue
        
        for field in KEYWORD_REQUIRED:
            if field not in entry:
                errors.append(f"keywords.json: '{keyword}' missing required field '{field}'")
        
        if "severity" in entry and entry["severity"] not in KEYWORD_SEVERITY_VALUES:
            errors.append(
                f"keywords.json: '{keyword}' severity must be one of {KEYWORD_SEVERITY_VALUES}, "
                f"got '{entry['severity']}'"
            )
        
        for list_field in ["technical_terms", "academic_nouns", "api_references"]:
            if list_field in entry and not isinstance(entry[list_field], list):
                errors.append(f"keywords.json: '{keyword}.{list_field}' must be a list")
            elif list_field in entry and len(entry[list_field]) == 0:
                errors.append(f"keywords.json: '{keyword}.{list_field}' is empty")
        
        if "aliases" in entry:
            if not isinstance(entry["aliases"], list):
                errors.append(f"keywords.json: '{keyword}.aliases' must be a list")
    
    return data, errors


def validate_strategies(config_dir: str) -> tuple[dict, list[str]]:
    """Validate strategies.json. Returns (data, errors)."""
    path = os.path.join(config_dir, "strategies.json")
    data = _load_json(path)
    errors: list[str] = []
    
    if not isinstance(data, dict) or len(data) == 0:
        errors.append(f"strategies.json: Must be a non-empty object")
        return data, errors
    
    for name, entry in data.items():
        if not isinstance(entry, dict):
            errors.append(f"strategies.json: '{name}' must be an object")
            continue
        
        for field in STRATEGY_REQUIRED:
            if field not in entry:
                errors.append(f"strategies.json: '{name}' missing required field '{field}'")
        
        if "template" in entry:
            template = entry["template"]
            # Check for at least some placeholder variables
            placeholders = ["{domain}", "{technical_term}", "{academic_noun_1}"]
            has_any = any(p in template for p in placeholders)
            if not has_any:
                errors.append(
                    f"strategies.json: '{name}' template has no placeholder variables. "
                    f"Expected at least one of: {placeholders}"
                )
        
        if "effectiveness" in entry:
            eff = entry["effectiveness"]
            if not isinstance(eff, dict):
                errors.append(f"strategies.json: '{name}.effectiveness' must be an object")
            else:
                for model in STRATEGY_MODELS:
                    if model not in eff:
                        errors.append(
                            f"strategies.json: '{name}.effectiveness' missing model '{model}'"
                        )
                    elif not isinstance(eff[model], (int, float)):
                        errors.append(
                            f"strategies.json: '{name}.effectiveness.{model}' must be a number"
                        )
    
    return data, errors


def validate_primers(config_dir: str) -> tuple[dict, list[str]]:
    """Validate primers.json. Returns (data, errors)."""
    path = os.path.join(config_dir, "primers.json")
    data = _load_json(path)
    errors: list[str] = []
    
    if not isinstance(data, dict):
        errors.append(f"primers.json: Must be an object")
        return data, errors
    
    for domain, entry in data.items():
        if not isinstance(entry, dict):
            errors.append(f"primers.json: '{domain}' must be an object")
            continue
        
        for field in PRIMER_REQUIRED:
            if field not in entry:
                errors.append(f"primers.json: '{domain}' missing required field '{field}'")
        
        if "questions" in entry:
            if not isinstance(entry["questions"], list):
                errors.append(f"primers.json: '{domain}.questions' must be a list")
            elif len(entry["questions"]) == 0:
                errors.append(f"primers.json: '{domain}.questions' is empty")
    
    return data, errors


def validate_all(config_dir: str) -> tuple[dict[str, dict], list[str]]:
    """Validate all config files. Returns (configs, all_errors).
    
    configs = {"keywords": {...}, "strategies": {...}, "primers": {...}}
    """
    all_errors: list[str] = []
    configs: dict[str, dict] = {}
    
    kw_data, kw_errors = validate_keywords(config_dir)
    configs["keywords"] = kw_data
    all_errors.extend(kw_errors)
    
    st_data, st_errors = validate_strategies(config_dir)
    configs["strategies"] = st_data
    all_errors.extend(st_errors)
    
    pr_data, pr_errors = validate_primers(config_dir)
    configs["primers"] = pr_data
    all_errors.extend(pr_errors)
    
    return configs, all_errors


if __name__ == "__main__":
    # CLI validation
    config_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config"
    )
    print(f"Validating configs in: {config_dir}")
    configs, errors = validate_all(config_dir)
    
    if errors:
        print(f"\n❌ {len(errors)} validation error(s):")
        for e in errors:
            print(f"  → {e}")
        sys.exit(1)
    else:
        kw_count = len(configs["keywords"])
        st_count = len(configs["strategies"])
        pr_count = len(configs["primers"])
        alias_count = sum(
            len(v.get("aliases", [])) for v in configs["keywords"].values()
        )
        print(f"\n✅ All configs valid!")
        print(f"   Keywords: {kw_count} entries, {alias_count} aliases")
        print(f"   Strategies: {st_count} templates")
        print(f"   Primers: {pr_count} domains")
        sys.exit(0)
