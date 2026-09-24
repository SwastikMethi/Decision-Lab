import argparse
import json
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(prog="decisionlab")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=int(os.getenv("DECISIONLAB_PORT", "8768")))
    serve.add_argument("--host", default=os.getenv("DECISIONLAB_HOST", "127.0.0.1"))
    serve.add_argument("--reload", action="store_true")
    sub.add_parser("openapi")
    models = sub.add_parser("models")
    models.add_argument("action", choices=["prepare"])
    models.add_argument("--revision")
    sub.add_parser("datasets")
    rescore = sub.add_parser("rescore")
    rescore.add_argument("run_id")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "decisionlab.api:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
    elif args.command == "models":
        from .laya_runtime import prepare_models

        result = prepare_models(
            os.getenv("DECISIONLAB_MODEL_LOCK", "./models/lock.json"), args.revision
        )
        print(json.dumps(result, indent=2))
    elif args.command == "openapi":
        from .api import create_app

        path = Path("docs/openapi.json")
        with tempfile.TemporaryDirectory(prefix="decisionlab-openapi-") as temporary:
            path.write_text(json.dumps(create_app(temporary).openapi(), indent=2))
        print(path)
    else:
        from .store import Store

        store = Store(os.getenv("DECISIONLAB_DATA_ROOT", "./data"), recover=False)
        if args.command == "datasets":
            print(json.dumps(store.datasets(), indent=2))
        elif args.command == "rescore":
            from .reports import write_reports
            from .runner import Runner

            with store.exclusive():
                store.recover()
                summary = Runner(store).rescore(args.run_id)
                write_reports(store, args.run_id, summary)
            print(json.dumps(summary["counts"]))


if __name__ == "__main__":
    main()
