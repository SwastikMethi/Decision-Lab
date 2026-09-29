import httpx
import pytest
import respx
from repo_mcp.api_client import ApiError
from repo_mcp.custom_tools import prepare_benchmark
from repo_mcp.tools import (
    advance_benchmark,
    cancel_benchmark,
    get_benchmark_report,
    get_benchmark_status,
    list_benchmarks,
)

BASE = "http://127.0.0.1:8000"


@respx.mock
async def test_prepare_reads_only_dataset_jsonl_below_configured_root(tmp_path, monkeypatch):
    root = tmp_path / "datasets"
    folder = root / "support-routing"
    folder.mkdir(parents=True)
    content = '{"schema_version":"1.0"}\n'
    (folder / "dataset.jsonl").write_text(content)
    monkeypatch.setenv("DECISIONLAB_DATASET_ROOT", str(root))
    route = respx.post(f"{BASE}/api/v1/benchmark-workflows").mock(
        return_value=httpx.Response(201, json={"workflow_id": "workflow-1", "stage": "prepared"})
    )

    result = await prepare_benchmark("support-routing", profile="full", publication=True)

    assert result == {"workflow_id": "workflow-1", "stage": "prepared"}
    assert route.calls.last.request.read() == (
        b'{"name":"support-routing","dataset_jsonl":"{\\"schema_version\\":\\"1.0\\"}\\n",'
        b'"profile":"full","publication":true}'
    )


@pytest.mark.parametrize("folder", ["/absolute", "../outside", "nested/../../outside"])
async def test_prepare_rejects_absolute_and_parent_paths(tmp_path, monkeypatch, folder):
    monkeypatch.setenv("DECISIONLAB_DATASET_ROOT", str(tmp_path))
    with pytest.raises(ApiError) as error:
        await prepare_benchmark(folder)
    assert error.value.category == "invalid_input"


async def test_prepare_requires_dataset_root_and_fixed_filename(tmp_path, monkeypatch):
    monkeypatch.delenv("DECISIONLAB_DATASET_ROOT", raising=False)
    with pytest.raises(ApiError, match="DECISIONLAB_DATASET_ROOT"):
        await prepare_benchmark("sample")

    monkeypatch.setenv("DECISIONLAB_DATASET_ROOT", str(tmp_path))
    (tmp_path / "sample").mkdir()
    (tmp_path / "sample" / "other.jsonl").write_text("{}\n")
    with pytest.raises(ApiError, match="dataset.jsonl"):
        await prepare_benchmark("sample")


async def test_prepare_rejects_symlink_escape(tmp_path, monkeypatch):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "dataset.jsonl").write_text("{}\n")
    (root / "escape").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("DECISIONLAB_DATASET_ROOT", str(root))

    with pytest.raises(ApiError, match="escapes"):
        await prepare_benchmark("escape")


async def test_prepare_enforces_25_mib_limit(tmp_path, monkeypatch):
    folder = tmp_path / "large"
    folder.mkdir()
    with (folder / "dataset.jsonl").open("wb") as file:
        file.seek(25 * 1024 * 1024)
        file.write(b"x")
    monkeypatch.setenv("DECISIONLAB_DATASET_ROOT", str(tmp_path))

    with pytest.raises(ApiError, match="25 MiB"):
        await prepare_benchmark("large")


@respx.mock
async def test_list_benchmarks_maps_to_workflow_collection():
    route = respx.get(f"{BASE}/api/v1/benchmark-workflows").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )
    assert await list_benchmarks() == {"items": [], "total": 0}
    assert route.called


@respx.mock
async def test_get_status_maps_workflow_id_into_path():
    route = respx.get(f"{BASE}/api/v1/benchmark-workflows/a%2Fb").mock(
        return_value=httpx.Response(200, json={"workflow_id": "a/b"})
    )
    assert await get_benchmark_status("a/b") == {"workflow_id": "a/b"}
    assert route.called


@respx.mock
async def test_advance_forwards_explicit_confirmations():
    route = respx.post(f"{BASE}/api/v1/benchmark-workflows/w1/advance").mock(
        return_value=httpx.Response(200, json={"stage": "development_running"})
    )
    result = await advance_benchmark(
        "w1", confirm_live_calls=True, confirm_remote_data=True
    )
    assert result["stage"] == "development_running"
    assert route.calls.last.request.read() == (
        b'{"confirm_live_calls":true,"confirm_remote_data":true}'
    )


@respx.mock
async def test_cancel_posts_to_workflow_cancel():
    route = respx.post(f"{BASE}/api/v1/benchmark-workflows/w1/cancel").mock(
        return_value=httpx.Response(200, json={"stage": "cancelled"})
    )
    assert await cancel_benchmark("w1") == {"stage": "cancelled"}
    assert route.called


@respx.mock
async def test_report_maps_workflow_id_into_report_path():
    route = respx.get(f"{BASE}/api/v1/benchmark-workflows/w1/report").mock(
        return_value=httpx.Response(200, json={"default": {"winner": "no_clear_winner"}})
    )
    assert (await get_benchmark_report("w1"))["default"]["winner"] == "no_clear_winner"
    assert route.called
