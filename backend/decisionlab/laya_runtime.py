from __future__ import annotations

import asyncio
import importlib.metadata
import json
import multiprocessing
import os
import time
import warnings
from pathlib import Path

from .adapters import ProviderFailure, sanitize


def prepare_models(lock_path, revision=None):
    from huggingface_hub import HfApi, snapshot_download

    repo = "convaiinnovations/laya"
    resolved = HfApi().model_info(repo, revision=revision).sha
    snapshot = snapshot_download(
        repo,
        revision=resolved,
        allow_patterns=[
            "config.json",
            "model.safetensors",
            "tokenizer/*",
            "encoder/*",
            "multilingual/*",
            "typed-decisions/*",
        ],
    )
    root = Path(snapshot)
    routes = {
        "english": str(root),
        "multilingual": str(root / "multilingual"),
        "typed-decisions": str(root / "typed-decisions"),
    }
    for route, directory in routes.items():
        if not (Path(directory) / "model.safetensors").exists():
            raise ValueError(f"Pinned snapshot is missing {route} weights")
    lock = {
        "repo": repo,
        "revision": resolved,
        "snapshot": snapshot,
        "package_version": importlib.metadata.version("laya"),
        "routes": routes,
        "size_bytes": sum(p.stat().st_size for p in root.rglob("*") if p.is_file()),
    }
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    return lock


def _worker(connection, config, model_lock):
    """The child owns all torch state. Only public requests cross this boundary."""
    try:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        import torch
        from laya import Agent, Router

        device = config["device"]
        if device == "auto":
            device = (
                "cuda"
                if torch.cuda.is_available()
                else "mps"
                if torch.backends.mps.is_available()
                else "cpu"
            )
        router = Router(models=model_lock["routes"], device=device, preload=False)
        agents, load_warnings = {}, {}

        def route_for(request):
            return (
                config["checkpoint"]
                if config["checkpoint"] != "router"
                else router.route(**request).model
            )

        def infer(request):
            route = route_for(request)
            if route not in agents:
                with warnings.catch_warnings(record=True) as captured:
                    warnings.simplefilter("always")
                    agents[route] = Agent(model_lock["routes"][route], device=device)
                load_warnings[route] = [str(w.message) for w in captured]
                router.attach(route, agents[route])
            agent = agents[route]
            start = time.perf_counter()
            raw = router.predict(**request, model=route)
            actual_device = str(agent.device)
            if actual_device.startswith("mps"):
                torch.mps.synchronize()
            elif actual_device.startswith("cuda"):
                torch.cuda.synchronize()
            raw["_runtime"] = {
                "inference_ms": (time.perf_counter() - start) * 1000,
                "device": actual_device,
                "dtype": str(agent.dtype),
                "route": route,
                "revision": model_lock["revision"],
                "effective_settings": {
                    "checkpoint_config": agent.cfg,
                    "temperature": agent.temperature,
                    "temperature_by_options": agent.temperature_by_options,
                    "amp_enabled": agent.amp_enabled,
                },
                "warnings": load_warnings[route],
                "accelerator_memory_bytes": torch.mps.current_allocated_memory()
                if actual_device.startswith("mps")
                else torch.cuda.max_memory_allocated()
                if actual_device.startswith("cuda")
                else None,
            }
            return raw

        connection.send(
            {"ready": True, "device": device, "package_version": importlib.metadata.version("laya")}
        )
        while True:
            message = connection.recv()
            if message["action"] == "close":
                break
            try:
                if message["action"] == "warmup":
                    representatives: dict[tuple, dict] = {}
                    for request in message["requests"]:
                        primitive = next(iter(request["questions"].values()))["type"]
                        representatives.setdefault((route_for(request), primitive), request)
                    raw = {"responses": [infer(request) for request in representatives.values()]}
                else:
                    raw = infer(message["request"])
                connection.send({"result": raw})
            except Exception as exc:
                connection.send({"error": str(sanitize(str(exc))), "category": "runtime"})
    except BaseException as exc:
        try:
            connection.send({"error": str(sanitize(str(exc))), "category": "runtime"})
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


class LayaAdapter:
    adapter_id = "laya"

    def __init__(self, config, lock_path):
        self.config, self.lock_path = config, Path(lock_path)
        self.process = None
        self.connection = None
        self.mutex = asyncio.Lock()
        self.model_lock = None
        self.metadata = {}

    async def readiness(self):
        try:
            package = importlib.metadata.version("laya")
        except importlib.metadata.PackageNotFoundError:
            return {"ready": False, "reason": "Install the laya optional dependency"}
        if not self.lock_path.exists():
            return {
                "ready": False,
                "installed": True,
                "package_version": package,
                "reason": "Run decisionlab models prepare to pin and download checkpoints",
            }
        lock = json.loads(self.lock_path.read_text())
        complete = all(
            (Path(directory) / "model.safetensors").exists()
            for directory in lock["routes"].values()
        )
        return {
            "ready": complete,
            "installed": True,
            "package_version": package,
            "revision": lock["revision"],
            "size_bytes": lock["size_bytes"],
        }

    async def _receive(self, timeout):
        if self.connection is None or self.process is None:
            raise ProviderFailure("runtime", "Local inference worker is unavailable")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.connection.poll():
                try:
                    result = self.connection.recv()
                except EOFError as exc:
                    raise ProviderFailure("runtime", "Local inference worker stopped") from exc
                if "error" in result:
                    raise ProviderFailure(result["category"], result["error"])
                return result
            if not self.process.is_alive():
                raise ProviderFailure("runtime", "Local inference worker exited")
            await asyncio.sleep(0.01)
        raise ProviderFailure("timeout", "Local inference exceeded its deadline")

    async def warmup(self, cases):
        readiness = await self.readiness()
        if not readiness["ready"]:
            raise ProviderFailure("runtime", readiness["reason"])
        self.model_lock = json.loads(self.lock_path.read_text())
        if (
            self.config.checkpoint_revision
            and self.config.checkpoint_revision != self.model_lock["revision"]
        ):
            raise ProviderFailure(
                "runtime", "Requested checkpoint revision differs from the prepared lock"
            )
        context = multiprocessing.get_context("spawn")
        self.connection, child = context.Pipe()
        start = time.perf_counter()
        self.process = context.Process(
            target=_worker, args=(child, self.config.model_dump(), self.model_lock), daemon=True
        )
        self.process.start()
        child.close()
        self.metadata = await self._receive(180)
        self.connection.send({"action": "warmup", "requests": [c.request() for c in cases]})
        warmed = (await self._receive(180))["result"]
        return {
            "cold_start_ms": (time.perf_counter() - start) * 1000,
            **warmed,
            **self.metadata,
            "checkpoint": self.model_lock,
        }

    async def predict(self, case):
        return await self.predict_questions(case, 1)

    async def predict_questions(self, case, batch_size):
        queued = time.perf_counter()
        async with self.mutex:
            queue_ms = (time.perf_counter() - queued) * 1000
            if self.process is None or self.connection is None or not self.process.is_alive():
                raise ProviderFailure("runtime", "Local worker is not available")
            request = case.request()
            question = request["questions"][case.question.id]
            request["questions"].update(
                {f"{case.question.id}_{i}": question for i in range(1, batch_size)}
            )
            self.connection.send({"action": "predict", "request": request})
            try:
                response = await self._receive(self.config.timeout_seconds)
            except (ProviderFailure, asyncio.CancelledError):
                await self.close()
                raise
            response["result"].setdefault("_runtime", {})["queue_ms"] = queue_ms
            return response["result"]

    async def close(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            await asyncio.to_thread(self.process.join, 3)
            if self.process.is_alive():
                self.process.kill()
                await asyncio.to_thread(self.process.join, 2)
            self.process = None
        if self.connection:
            self.connection.close()
            self.connection = None
