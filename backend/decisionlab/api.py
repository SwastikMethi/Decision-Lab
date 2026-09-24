from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .calibration import fit_calibration, inference_signature
from .datasets import MAX_UPLOAD
from .governance import freeze_protocol, import_reviews, review_packet, review_status
from .laya_runtime import LayaAdapter
from .metrics import SCORING_VERSION, gold
from .playback import PlaybackPage, playback_page
from .reports import bundle, write_reports
from .runner import Runner, make_schedule
from .schemas import LayaConfiguration, RunConfiguration
from .store import TERMINAL, Store, identifier, now


def case_filters(
    domain: str | None = None,
    primitive: str | None = None,
    variant: str | None = None,
    split: str | None = None,
    disagreement: bool | None = None,
    jev_correct: bool | None = None,
    laya_correct: bool | None = None,
    confidence_min: float = Query(0, ge=0, le=1),
    confidence_max: float = Query(1, ge=0, le=1),
    error_category: str | None = None,
    q: str = Query("", max_length=500),
):
    return dict(
        domain=domain,
        primitive=primitive,
        variant=variant,
        split=split,
        disagreement=disagreement,
        jev_correct=jev_correct,
        laya_correct=laya_correct,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        error_category=error_category,
        q=q,
    )


class CalibrationRequest(BaseModel):
    run_id: str


class ProtocolRequest(BaseModel):
    dataset_id: str
    configurations: dict[str, RunConfiguration]


class RescoreRequest(BaseModel):
    scoring_version: str = SCORING_VERSION


class ReviewRequest(BaseModel):
    reviews: list[dict] = Field(min_length=1, max_length=10000)


def create_app(root=None):
    load_dotenv()
    store = Store(root or os.getenv("DECISIONLAB_DATA_ROOT", "./data"), recover=False)
    runner = Runner(store)

    @asynccontextmanager
    async def lifespan(app):
        with store.exclusive():
            store.recover()
            try:
                yield
            finally:
                await runner.close()

    app = FastAPI(title="DecisionLab", version="1.0.0", lifespan=lifespan)
    app.state.store, app.state.runner = store, runner
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"]
    )

    @app.middleware("http")
    async def protect_local_mutations(request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("origin")
            allowed = {
                f"http://{request.headers.get('host')}",
                "http://127.0.0.1:5173",
                "http://localhost:5173",
            }
            if origin and origin not in allowed:
                return Response(
                    '{"detail":"Cross-origin changes are not allowed"}',
                    status_code=403,
                    media_type="application/json",
                )
            length = request.headers.get("content-length")
            if length and not length.isdecimal():
                return Response(
                    '{"detail":"Invalid Content-Length"}',
                    status_code=400,
                    media_type="application/json",
                )
            if length and int(length) > MAX_UPLOAD + 1024 * 1024:
                return Response(
                    '{"detail":"Upload exceeds 25 MiB"}',
                    status_code=413,
                    media_type="application/json",
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(ValueError)
    async def bad_input(request, exc):
        from .adapters import sanitize

        return Response(
            json.dumps({"detail": sanitize(str(exc))}),
            status_code=400,
            media_type="application/json",
        )

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return Response(
            '{"detail":"Resource not found"}', status_code=404, media_type="application/json"
        )

    def visible_cases(run_id):
        manifest = store.manifest(run_id)
        cases = store.records(run_id, "cases.snapshot")
        return [c for c in cases if c["split"] != "sealed" or manifest.get("sealed_released")]

    def comparisons(run_id, filters):
        cases = visible_cases(run_id)
        all_predictions = store.records(run_id, "predictions")
        grouped: dict[str, dict[str, Any]] = {}
        for prediction in all_predictions:
            if prediction["suite"] in ("quality", "context_length", "option_cardinality"):
                grouped.setdefault(prediction["case_id"], {})[prediction["adapter_id"]] = prediction
        rows = []
        for case in cases:
            predictions = grouped.get(case["id"], {})
            correctness = {
                key: bool(
                    predictions.get(key, {}).get("status") == "success"
                    and predictions[key]["answer"]["selected"] == gold(case)
                )
                for key in ("jev", "laya")
            }
            selected = {
                key: predictions[key]["answer"]["selected"]
                if predictions.get(key, {}).get("answer")
                else None
                for key in ("jev", "laya")
            }
            disagreement = selected["jev"] != selected["laya"]
            if any(
                filters.get(key) and case[key] != filters[key]
                for key in ("domain", "primitive", "variant", "split")
            ):
                continue
            if filters.get("disagreement") is not None and disagreement != filters["disagreement"]:
                continue
            if any(
                filters.get(f"{key}_correct") is not None
                and correctness[key] != filters[f"{key}_correct"]
                for key in ("jev", "laya")
            ):
                continue
            if (
                filters.get("q")
                and filters["q"].lower() not in json.dumps(case, ensure_ascii=False).lower()
            ):
                continue
            if filters.get("error_category") and not any(
                (p.get("error") or {}).get("category") == filters["error_category"]
                for p in predictions.values()
            ):
                continue
            low, high = filters.get("confidence_min", 0), filters.get("confidence_max", 1)
            if (low > 0 or high < 1) and not any(
                p.get("answer") and low <= p["answer"]["decision_probability"] <= high
                for p in predictions.values()
            ):
                continue
            rows.append(
                {
                    "case": case,
                    "predictions": predictions,
                    "correctness": correctness,
                    "disagreement": disagreement,
                }
            )
        return rows

    summary_cache: dict[tuple, dict[str, Any]] = {}

    def summary_view(run_id, filters):
        manifest = store.manifest(run_id)
        rows = comparisons(run_id, filters)
        cases = [r["case"] for r in rows]
        ids = {c["id"] for c in cases}
        predictions = [p for p in store.records(run_id, "predictions") if p["case_id"] in ids]
        key = (
            run_id,
            manifest["status"],
            manifest["progress"]["completed"],
            manifest.get("sealed_released"),
            json.dumps(filters, sort_keys=True),
        )
        if key not in summary_cache:
            summary = runner.summary(run_id, cases, predictions)
            summary.update(
                sealed_results_withheld=any(
                    c["split"] == "sealed" for c in store.records(run_id, "cases.snapshot")
                )
                and not manifest["sealed_released"]
            )
            if len(summary_cache) > 32:
                summary_cache.clear()
            summary_cache[key] = summary
        return summary_cache[key]

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/v1/readiness")
    async def readiness():
        laya = await LayaAdapter(LayaConfiguration(), runner.model_lock).readiness()
        return {
            "jev": {
                "configured": bool(os.getenv("TYPESAFE_API_KEY")),
                "reachable": None,
                "model": "jev-1.13.0",
                "note": "Connectivity is verified during warm-up",
            },
            "laya": laya,
            "storage": {"writable": os.access(store.root, os.W_OK)},
            "simulation_available": os.getenv("DECISIONLAB_ALLOW_FAKE", "true").lower() == "true",
        }

    @app.get("/api/v1/datasets")
    def datasets():
        return {"items": store.datasets()}

    @app.post("/api/v1/datasets/validate")
    async def upload(file: UploadFile = File(...)):
        raw = await file.read(MAX_UPLOAD + 1)
        return store.add_dataset(raw, Path(file.filename or "Imported dataset").name)

    @app.get("/api/v1/datasets/{dataset_id}")
    def dataset(dataset_id: str):
        metadata, cases = store.dataset(dataset_id)
        return {
            **metadata,
            "preview": [c.model_dump() for c in cases if c.split != "sealed"][:50],
            "review": review_status(store, dataset_id),
        }

    @app.get("/api/v1/datasets/{dataset_id}/review-packet")
    def packet(dataset_id: str):
        return review_packet(store, dataset_id)

    @app.post("/api/v1/datasets/{dataset_id}/reviews")
    def reviews(dataset_id: str, body: ReviewRequest):
        return import_reviews(store, dataset_id, body.reviews)

    @app.post("/api/v1/runs/estimate")
    def estimate(config: RunConfiguration):
        _, cases = store.dataset(config.dataset_ref)
        from .benchmark import diagnostic_cases
        from .schemas import EvaluationCase

        cases += [
            EvaluationCase.model_validate(c)
            for c in diagnostic_cases(
                cases, config.suites.context_length, config.suites.option_cardinality
            )
        ]
        schedule = make_schedule(config, cases)
        return {
            "requests": len(schedule),
            "questions": sum(j["batch_size"] for j in schedule),
            "warmup_requests": 2 * len({c.primitive for c in cases}),
            "maximum_jev_retries": sum(j["adapter_id"] == "jev" for j in schedule)
            * config.systems.jev.max_retries,
            "runtime_estimate_seconds": None,
            "cost_estimate_usd": None,
            "note": "Runtime and exact cost depend on device, tokenization, batching, and retries.",
        }

    @app.post("/api/v1/runs", status_code=202)
    async def start_run(config: RunConfiguration):
        manifest = await runner.create(config)
        return {
            "run_id": manifest["run_id"],
            "status": manifest["status"],
            "events_url": f"/api/v1/runs/{manifest['run_id']}/events",
        }

    @app.get("/api/v1/runs")
    def runs(
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
        status: str | None = None,
        track: str | None = None,
        dataset: str | None = None,
    ):
        values = [
            r
            for r in store.runs()
            if (not status or r["status"] == status)
            and (not track or r["track"] == track)
            and (not dataset or r["effective_config"].get("dataset_ref") == dataset)
        ]
        return {"items": values[(page - 1) * page_size : page * page_size], "total": len(values)}

    @app.get("/api/v1/runs/{run_id}")
    def run(run_id: str):
        return store.manifest(run_id)

    @app.post("/api/v1/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        return await runner.cancel(run_id)

    @app.post("/api/v1/runs/{run_id}/rescore")
    async def rescore(run_id: str, body: RescoreRequest):
        if body.scoring_version != SCORING_VERSION:
            raise ValueError("Requested scoring version is not installed")
        if store.manifest(run_id)["status"] not in TERMINAL:
            raise ValueError("Wait for execution to stop before rescoring")
        summary = await asyncio.to_thread(runner.rescore, run_id)
        await asyncio.to_thread(write_reports, store, run_id, summary)
        summary_cache.clear()
        return {"scoring_version": summary["scoring_version"], "run_id": run_id}

    @app.get("/api/v1/runs/{run_id}/summary")
    def summary(run_id: str, filters=Depends(case_filters)):
        return summary_view(run_id, filters)

    @app.get("/api/v1/runs/{run_id}/cases")
    def cases(
        run_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=500),
        filters=Depends(case_filters),
    ):
        rows = comparisons(run_id, filters)
        result = []
        for row in rows[(page - 1) * page_size : page * page_size]:
            case = dict(row["case"])
            case["state_preview"] = json.dumps(case.pop("state"), ensure_ascii=False)[:240]
            result.append(
                {
                    **row,
                    "case": case,
                    "predictions": {
                        key: {k: v for k, v in p.items() if k not in ("raw_response", "request")}
                        for key, p in row["predictions"].items()
                    },
                }
            )
        return {"items": result, "total": len(rows), "page": page, "page_size": page_size}

    @app.get("/api/v1/runs/{run_id}/playback", response_model=PlaybackPage)
    def playback(
        run_id: str,
        after: int = Query(-1, ge=-1),
        limit: int = Query(20, ge=1, le=100),
    ):
        return playback_page(store, run_id, after, limit)

    @app.get("/api/v1/runs/{run_id}/cases/{case_id}")
    def case_detail(run_id: str, case_id: str):
        rows = comparisons(run_id, {})
        item = next((r for r in rows if r["case"]["id"] == case_id), None)
        if item is None:
            raise HTTPException(404, "Case is unavailable")
        return {
            **item,
            "family": [r for r in rows if r["case"]["family_id"] == item["case"]["family_id"]],
            "all_predictions": [
                p for p in store.records(run_id, "predictions") if p["case_id"] == case_id
            ],
        }

    @app.get("/api/v1/runs/{run_id}/charts/{chart_id}")
    def chart(run_id: str, chart_id: str, filters=Depends(case_filters)):
        summary = summary_view(run_id, filters)
        mapping = {
            "calibration": ("calibration", "bins"),
            "risk-coverage": ("selective_automation", "curve"),
            "confidence-distribution": ("calibration", "confidence_histogram"),
            "latency-distribution": ("performance", "latencies"),
        }
        if chart_id in mapping:
            a, b = mapping[chart_id]
            return {
                "chart_id": chart_id,
                "data": {system: value[a][b] for system, value in summary["systems"].items()},
            }
        if chart_id in ("accuracy-by-primitive", "domain-heatmap"):
            dimension = "primitive" if chart_id == "accuracy-by-primitive" else "domain"
            return {
                "chart_id": chart_id,
                "data": [s for s in summary["slices"] if s["dimension"] == dimension],
            }
        if chart_id == "robustness-heatmap":
            return {
                "chart_id": chart_id,
                "data": {
                    system: value["robustness"] for system, value in summary["systems"].items()
                },
            }
        if chart_id in ("context-length", "option-cardinality"):
            return {
                "chart_id": chart_id,
                "data": {
                    system: [
                        d
                        for d in value["diagnostics"]
                        if d["variant"] == chart_id.replace("-", "_")
                    ]
                    for system, value in summary["systems"].items()
                },
            }
        if chart_id == "quality-latency-scatter":
            return {
                "chart_id": chart_id,
                "data": [
                    {
                        "system": system,
                        "accuracy": value["correctness"]["accuracy"]["value"],
                        "latency_ms": value["performance"]["warm_p50_ms"],
                    }
                    for system, value in summary["systems"].items()
                ],
            }
        raise HTTPException(404, "Unknown chart")

    @app.get("/api/v1/runs/{run_id}/comparison/{other_id}")
    def compare_runs(run_id: str, other_id: str):
        left, right = store.manifest(run_id), store.manifest(other_id)
        if any(
            left[key] != right[key]
            for key in ("track", "dataset_digest", "scoring_version", "mode")
        ):
            raise ValueError(
                "Compare runs with the same track, dataset, scoring version, and live/simulation mode"
            )
        return {"left": summary_view(run_id, {}), "right": summary_view(other_id, {})}

    @app.get("/api/v1/runs/{run_id}/exports/{format}")
    def export(run_id: str, format: str):
        manifest = store.manifest(run_id)
        if (
            any(c["split"] == "sealed" for c in store.records(run_id, "cases.snapshot"))
            and not manifest["sealed_released"]
        ):
            raise HTTPException(403, "Exports unlock after both frozen tracks complete")
        if manifest["status"] not in TERMINAL:
            raise ValueError("Exports are available after execution stops")
        directory = store.run_dir(run_id)
        if not (directory / "summary.v1.0.0.json").exists():
            summary = runner.rescore(run_id)
            write_reports(store, run_id, summary)
        formats = {
            "markdown": ("report.md", "text/markdown"),
            "html": ("report.html", "text/html"),
            "summary-json": ("summary.v1.0.0.json", "application/json"),
            "predictions-jsonl": ("predictions.jsonl", "application/x-ndjson"),
        }
        if format == "bundle":
            return Response(
                bundle(store, run_id),
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="decisionlab-{run_id}.zip"'},
            )
        if format not in formats:
            raise HTTPException(404, "Unknown export format")
        filename, media_type = formats[format]
        return FileResponse(
            directory / filename, media_type=media_type, filename=f"{run_id}-{filename}"
        )

    @app.get("/api/v1/runs/{run_id}/events")
    async def events(run_id: str, request: Request, after: int = Query(0, ge=0)):
        store.manifest(run_id)
        try:
            last = max(after, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise HTTPException(400, "Invalid Last-Event-ID")

        async def stream():
            heartbeat = time.monotonic()
            path = store.run_dir(run_id) / "events.jsonl"
            with path.open(encoding="utf-8") as file:
                while not await request.is_disconnected():
                    position = file.tell()
                    line = file.readline()
                    if line:
                        if not line.endswith("\n"):
                            if store.manifest(run_id)["status"] in TERMINAL:
                                break
                            file.seek(position)
                            await asyncio.sleep(0.1)
                            continue
                        event = json.loads(line)
                        if event["id"] > last:
                            yield f"id: {event['id']}\nevent: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
                        continue
                    if store.manifest(run_id)["status"] in TERMINAL:
                        break
                    if time.monotonic() - heartbeat > 10:
                        yield ": heartbeat\n\n"
                        heartbeat = time.monotonic()
                    await asyncio.sleep(0.15)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/v1/calibrations")
    def calibrations():
        return {"items": [store.read_json(p) for p in (store.root / "calibrations").glob("*.json")]}

    @app.post("/api/v1/calibrations", status_code=201)
    def calibrate(body: CalibrationRequest):
        manifest = store.manifest(body.run_id)
        if manifest["status"] != "completed" or manifest["effective_config"].get("calibration_id"):
            raise ValueError("Fit from a completed development run without existing calibration")
        cases = store.records(body.run_id, "cases.snapshot")
        result = fit_calibration(
            cases, store.records(body.run_id, "predictions"), manifest["dataset_digest"]
        )
        calibration_id = identifier()
        result.update(
            calibration_id=calibration_id,
            run_id=body.run_id,
            created_at=now(),
            inference_signature=inference_signature(
                RunConfiguration.model_validate(manifest["effective_config"])
            ),
            source_mode=manifest["mode"],
            family_ids=sorted({c["family_id"] for c in cases}),
        )
        store.write_json(store.path("calibrations", calibration_id + ".json"), result)
        return result

    @app.get("/api/v1/calibrations/{calibration_id}")
    def calibration(calibration_id: str):
        return store.read_json(store.path("calibrations", calibration_id + ".json"))

    @app.post("/api/v1/protocols", status_code=201)
    def freeze(body: ProtocolRequest):
        return freeze_protocol(store, body.dataset_id, body.configurations)

    @app.get("/api/v1/protocols")
    def protocols():
        return {"items": [store.read_json(p) for p in (store.root / "protocols").glob("*.json")]}

    @app.get("/api/v1/protocols/{protocol_id}")
    def protocol(protocol_id: str):
        return store.read_json(store.path("protocols", protocol_id + ".json"))

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(dist / "index.html")

    return app
