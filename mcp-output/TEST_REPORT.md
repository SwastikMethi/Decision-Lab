# Test report: decisionlab-mcp

Generated 2026-09-29T11:30:46Z by generate-mcp.
Passed 13, failed 0, skipped 3.

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
  - Tested: MCP Inspector `tools/call` with the local fixture root and generated mock API
  - Expected: exit 0, `isError: false`
  - Observed: exit 0, `isError: false`, mock API returned HTTP 201
  - Error: The generic verifier omits custom environment variables; the explicit rerun supplied `DECISIONLAB_DATASET_ROOT`.
  - Next action: None
- ✓ **tools/call list_benchmarks (mock API)**
- ✓ **tools/call get_benchmark_status (mock API)**
- ✓ **tools/call get_benchmark_report (mock API)**
- ✓ **invalid input to prepare_benchmark yields a tool error (missing required input)**
- ✓ **upstream 401 is a redacted tool error**

## Client connection checks

- – **claude/codex mcp list**
  - Reason: deferred to stage 7: run run_inspector_tests.py --clients-only after the configs are applied

## Skipped tests and reasons

- – **tools/call advance_benchmark**
  - Reason: risk destructive is never called automatically
- – **tools/call cancel_benchmark**
  - Reason: risk destructive is never called automatically
