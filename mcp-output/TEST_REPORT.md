# Test report: decisionlab-mcp

Generated 2026-09-29T12:32:51Z by generate-mcp.
Passed 15, failed 0, skipped 2.

## Static validation

- ✓ **mcp-design.json tools map only to included inventory operations**
- ✓ **import repo_mcp.server and load tools**
- ✓ **no secret patterns in generated files**

## Unit tests

- ✓ **pytest (29 passed in 0.14s)**

## MCP protocol tests

- ✓ **initialize**
- ✓ **tools/list returns 6 tool(s)**
- ✓ **tools/list matches mcp-design.json**

## Safe integration tests

- ✓ **tools/call prepare_benchmark (mock API, write)**
- ✓ **tools/call list_benchmarks (mock API)**
- ✓ **tools/call get_benchmark_status (mock API)**
- ✓ **tools/call get_benchmark_report (mock API)**
- ✓ **invalid input to prepare_benchmark yields a tool error (missing required input)**
- ✓ **upstream 401 is a redacted tool error**

## Client connection checks

- ✓ **claude mcp list shows decisionlab-mcp (pending approval)**
- ✓ **codex mcp list shows decisionlab-mcp (listed)**

## Skipped tests and reasons

- – **tools/call advance_benchmark**
  - Reason: risk destructive is never called automatically
- – **tools/call cancel_benchmark**
  - Reason: risk destructive is never called automatically
