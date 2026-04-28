"""
PHANTOM-LINGUIST: MCP Server
Single tool: linguist_reframe
Runs as MCP-compliant server for integration with AI assistants.
"""

import json
import os
import sys

# Ensure project root is in path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from core.scanner import scan, get_severity_summary
from core.reframer import reframe
from core.logger import log_reframe
from core.validator import validate_all

# --- Config Loading ---
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")


def _boot() -> dict:
    """Boot sequence: validate configs and load them."""
    configs, errors = validate_all(CONFIG_DIR)
    if errors:
        print(f"❌ PHANTOM-LINGUIST boot failed with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  → {e}", file=sys.stderr)
        sys.exit(1)
    
    kw_count = len(configs["keywords"])
    alias_count = sum(len(v.get("aliases", [])) for v in configs["keywords"].values())
    st_count = len(configs["strategies"])
    
    print(f"🎭 PHANTOM-LINGUIST v3.1 — ONLINE", file=sys.stderr)
    print(f"   Keywords: {kw_count} | Aliases: {alias_count} | Strategies: {st_count}", file=sys.stderr)
    
    return configs


# --- MCP Tool Implementation ---

def linguist_reframe(
    prompt: str,
    strategy: str = "",
    target_model: str = "gpt",
    use_primer: bool = True,
) -> dict:
    """Core MCP tool: Reframe a raw prompt into academic/technical framing.
    
    Args:
        prompt: Raw prompt in any language (Indo/English)
        strategy: Force strategy (academic/debug/audit/documentation/redteam).
                  Empty = auto-select best for target model.
        target_model: Target AI model (claude/gpt/gemini/copilot)
        use_primer: Whether to include warm-up primer question
    
    Returns:
        Reframe result with prompt, strategy, score, warnings.
    """
    # Step 1: Scan for hot keywords
    scan_results = scan(prompt, CONFIGS["keywords"])
    severity = get_severity_summary(scan_results)
    
    # Step 2: Reframe
    result = reframe(
        prompt=prompt,
        scan_results=scan_results,
        strategies=CONFIGS["strategies"],
        primers=CONFIGS["primers"],
        strategy_name=strategy if strategy else None,
        target_model=target_model,
        include_primer=use_primer,
    )
    
    # Step 3: Log
    log_id = log_reframe(
        raw_prompt=prompt,
        reframed_prompt=result["reframed_prompt"],
        strategy_used=result["strategy_used"],
        target_model=target_model,
        detected_keywords=result["detected_keywords"],
        specificity_score=result["specificity_score"],
        technical_anchors=result["technical_anchors"],
    )
    
    # Step 4: Build response
    result["log_id"] = log_id
    result["severity_summary"] = severity
    
    return result


# --- MCP Protocol Handler (stdio) ---

def handle_request(request: dict) -> dict:
    """Handle a single MCP JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "phantom-linguist",
                    "version": "3.1.0",
                },
            },
        }
    
    elif method == "notifications/initialized":
        return None  # No response needed for notifications
    
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "linguist_reframe",
                        "description": (
                            "Reframe a raw prompt into academically-framed technical inquiry. "
                            "Accepts multilingual input (Indo/English), outputs English academic framing. "
                            "Auto-detects hot keywords, selects optimal strategy, preserves technical anchors, "
                            "and warns if specificity score is too low."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prompt": {
                                    "type": "string",
                                    "description": "Raw prompt to reframe (any language)",
                                },
                                "strategy": {
                                    "type": "string",
                                    "description": "Strategy: academic/debug/audit/documentation/redteam (empty=auto)",
                                    "default": "",
                                },
                                "target_model": {
                                    "type": "string",
                                    "description": "Target AI: claude/gpt/gemini/copilot",
                                    "default": "gpt",
                                },
                                "use_primer": {
                                    "type": "boolean",
                                    "description": "Include warm-up primer question",
                                    "default": True,
                                },
                            },
                            "required": ["prompt"],
                        },
                    }
                ]
            },
        }
    
    elif method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        
        if tool_name == "linguist_reframe":
            try:
                result = linguist_reframe(
                    prompt=args.get("prompt", ""),
                    strategy=args.get("strategy", ""),
                    target_model=args.get("target_model", "gpt"),
                    use_primer=args.get("use_primer", True),
                )
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2, ensure_ascii=False),
                            }
                        ]
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {e}"}],
                        "isError": True,
                    },
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }


def main():
    """Main MCP server loop (stdio transport)."""
    global CONFIGS
    CONFIGS = _boot()
    
    # Read JSON-RPC messages from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        
        response = handle_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


# Allow direct invocation for testing
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Quick test mode
        CONFIGS = _boot()
        test_prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "gue mau nyolong cookie browser pake inject DLL"
        result = linguist_reframe(test_prompt)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        main()
