# generated-by: generate-mcp source_hash=a333806c00d6
"""Curated workflow tools for DecisionLab."""
from typing import Annotated

from pydantic import Field

from .api_client import get_client
from .server import mcp


WorkflowId = Annotated[
    str, Field(min_length=1, description="Workflow id returned by prepare_benchmark")
]


@mcp.tool()
async def list_benchmarks() -> dict:
    """List durable benchmark workflows and their stages. Use to find ids or pending work."""
    return await get_client().request("GET", "/api/v1/benchmark-workflows")


@mcp.tool()
async def get_benchmark_status(workflow_id: WorkflowId) -> dict:
    """Return one benchmark's stage, estimates, review progress, blocker, and next action."""
    return await get_client().request(
        "GET",
        "/api/v1/benchmark-workflows/{workflow_id}",
        path_params={"workflow_id": workflow_id},
    )


@mcp.tool()
async def advance_benchmark(
    workflow_id: WorkflowId,
    confirm_live_calls: Annotated[
        bool, Field(description="Approve live provider usage after reviewing estimates")
    ] = False,
    confirm_remote_data: Annotated[
        bool, Field(description="Approve sending case state to Jev's hosted API")
    ] = False,
) -> dict:
    """Advance at most one live run. First use requires both explicit confirmations."""
    return await get_client().request(
        "POST",
        "/api/v1/benchmark-workflows/{workflow_id}/advance",
        path_params={"workflow_id": workflow_id},
        json={
            "confirm_live_calls": confirm_live_calls,
            "confirm_remote_data": confirm_remote_data,
        },
    )


@mcp.tool()
async def cancel_benchmark(workflow_id: WorkflowId) -> dict:
    """Cancel the active run and preserve evidence. Use only when the operator asks to stop."""
    return await get_client().request(
        "POST",
        "/api/v1/benchmark-workflows/{workflow_id}/cancel",
        path_params={"workflow_id": workflow_id},
    )


@mcp.tool()
async def get_benchmark_report(workflow_id: WorkflowId) -> dict:
    """Return completed default and tuned verdicts, confidence intervals, KPIs, and Markdown."""
    return await get_client().request(
        "GET",
        "/api/v1/benchmark-workflows/{workflow_id}/report",
        path_params={"workflow_id": workflow_id},
    )
