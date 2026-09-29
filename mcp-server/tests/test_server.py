"""The server imports, loads tools, and lists them through the SDK's in-memory client."""
from mcp import Client

from repo_mcp import server


async def test_tools_are_registered_and_listable():
    server.load_tools()
    async with Client(server.mcp) as client:
        tools = (await client.list_tools()).tools
    names = {t.name for t in tools}
    assert names, "at least one tool must be registered"
    for t in tools:
        assert t.description, f"{t.name} needs a description"
        assert t.input_schema.get("type") == "object"


async def test_api_error_reaches_the_model_unmasked(monkeypatch):
    """mcp 2.x masks non-ToolError exceptions as 'Error executing tool X'. ApiError must not be masked."""
    from repo_mcp import api_client
    from repo_mcp.api_client import ApiError

    server.load_tools()
    first_tool = next(iter(server.mcp._tool_manager._tools)) if hasattr(server.mcp, "_tool_manager") else None
    if first_tool is None:
        return

    class Boom:
        async def request(self, *a, **k):
            raise ApiError("not_found", "GET /x -> {\"detail\": \"nope\"}", 404)

    import repo_mcp.tools as tools_mod
    monkeypatch.setattr(tools_mod, "get_client", lambda: Boom(), raising=False)
    async with Client(server.mcp) as client:
        listed = (await client.list_tools()).tools
        tool = next(t for t in listed if t.name == "list_benchmarks")
        args = {k: "x" for k in (tool.input_schema.get("required") or [])}
        result = await client.call_tool(tool.name, args)
    assert result.is_error is True
    text = result.content[0].text
    # The SDK prefixes "Error executing tool <name>: "; the redacted detail must follow, not be swallowed.
    assert "not_found (HTTP 404)" in text and "nope" in text, text
