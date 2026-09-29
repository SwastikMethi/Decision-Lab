# generated-by: generate-mcp source_hash=a333806c00d6
"""MCP server entry point. Tools register against `mcp` from tools.py and custom_tools.py."""
from __future__ import annotations

import importlib

from mcp.server import MCPServer

mcp = MCPServer("decisionlab-mcp")


def load_tools() -> None:
    """Import the tool modules so their @mcp.tool() decorators run.

    Imported lazily so tools.py can do `from .server import mcp` without a circular import.
    """
    for mod in ("repo_mcp.tools", "repo_mcp.custom_tools"):
        importlib.import_module(mod)


def main() -> None:
    load_tools()
    mcp.run()  # stdio


if __name__ == "__main__":
    main()
