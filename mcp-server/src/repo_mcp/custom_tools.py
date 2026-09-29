"""Local dataset preparation tool with a fixed, sandboxed file contract."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from .api_client import ApiError, get_client
from .server import mcp

MAX_DATASET_BYTES = 25 * 1024 * 1024


def _dataset_file(dataset_folder: str) -> Path:
    configured = os.getenv("DECISIONLAB_DATASET_ROOT")
    if not configured:
        raise ApiError("invalid_input", "DECISIONLAB_DATASET_ROOT is required")
    root = Path(configured).expanduser()
    if not root.is_absolute():
        raise ApiError("invalid_input", "DECISIONLAB_DATASET_ROOT must be absolute")
    root = root.resolve()
    relative = Path(dataset_folder)
    if relative.is_absolute() or ".." in relative.parts:
        raise ApiError("invalid_input", "dataset_folder must stay below DECISIONLAB_DATASET_ROOT")
    folder = (root / relative).resolve()
    if not folder.is_relative_to(root):
        raise ApiError("invalid_input", "dataset_folder escapes DECISIONLAB_DATASET_ROOT")
    dataset = (folder / "dataset.jsonl").resolve()
    if not dataset.is_relative_to(root):
        raise ApiError("invalid_input", "dataset.jsonl escapes DECISIONLAB_DATASET_ROOT")
    if not dataset.is_file():
        raise ApiError("invalid_input", f"dataset.jsonl was not found in {dataset_folder}")
    if dataset.stat().st_size > MAX_DATASET_BYTES:
        raise ApiError("invalid_input", "dataset.jsonl exceeds 25 MiB")
    return dataset


@mcp.tool()
async def prepare_benchmark(
    dataset_folder: Annotated[
        str,
        Field(
            min_length=1,
            description="Folder below DECISIONLAB_DATASET_ROOT containing dataset.jsonl",
        ),
    ],
    profile: Annotated[
        Literal["standard", "full"],
        Field(description="Evaluation depth; standard is the lower-cost default"),
    ] = "standard",
    publication: Annotated[
        bool, Field(description="Mark the frozen evaluation as intended for publication")
    ] = False,
) -> dict:
    """Prepare a durable benchmark from a folder's dataset.jsonl. Use this first."""
    dataset = _dataset_file(dataset_folder)
    raw = dataset.read_bytes()
    if len(raw) > MAX_DATASET_BYTES:
        raise ApiError("invalid_input", "dataset.jsonl exceeds 25 MiB")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError("invalid_input", "dataset.jsonl must use UTF-8") from None
    return await get_client().request(
        "POST",
        "/api/v1/benchmark-workflows",
        json={
            "name": dataset.parent.name,
            "dataset_jsonl": content,
            "profile": profile,
            "publication": publication,
        },
    )
