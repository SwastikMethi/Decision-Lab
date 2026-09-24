import io
import json
import zipfile

from markdown_it import MarkdownIt

from .datasets import digest_bytes

FENCE = chr(96) * 3


def display(value, percent=False):
    if value is None:
        return "Unavailable"
    return f"{value:.1%}" if percent else f"{value:.4g}"


def report_markdown(manifest, summary, environment):
    lines = [
        f"# {manifest['name']}",
        "",
        "**DecisionLab reproducible evaluation report**",
        "",
        f"- Run: {manifest['run_id']}",
        f"- Track: {manifest['track']}",
        f"- Status: {manifest['status']}",
        f"- Dataset digest: {manifest['dataset_digest']}",
        f"- Scoring version: {summary['scoring_version']}",
        "",
    ]
    if manifest["mode"] == "fake":
        lines += [
            "> SIMULATION: generated outcomes demonstrate the application. They are not evidence about Jev or Laya.",
            "",
        ]
    elif not manifest.get("publication"):
        lines += [
            "> Illustrative evaluation. Independent review and publication requirements have not all been satisfied.",
            "",
        ]
    lines += ["## Findings", ""]
    for finding in summary["findings"]:
        lines.append(
            f"- {finding['text']} Evidence: {finding['metric_ref']}; filters: {json.dumps(finding['filters'])}."
        )
    lines += [
        "",
        "## Primary comparison",
        "",
        "| System | Correct / total | Accuracy | Brier | ECE | Warm p50 ms | Failures |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for system, metrics in summary["systems"].items():
        accuracy = metrics["correctness"]["accuracy"]
        lines.append(
            f"| {system} | {accuracy['numerator']} / {accuracy['denominator']} | {display(accuracy['value'], True)} | {display(metrics['calibration']['brier']['value'])} | {display(metrics['calibration']['ece']['value'])} | {display(metrics['performance']['warm_p50_ms'])} | {metrics['failures']['count']} |"
        )
    lines += [
        "",
        "## Primitive and domain breakdown",
        "",
        "| System | Dimension | Group | Correct / total | Accuracy |",
        "|---|---|---|---:|---:|",
    ]
    for item in summary["slices"]:
        if item["dimension"] in ("primitive", "domain", "split"):
            value = item["metrics"]["correctness"]["accuracy"]
            lines.append(
                f"| {item['system_id']} | {item['dimension']} | {item['value']} | {value['numerator']} / {value['denominator']} | {display(value['value'], True)} |"
            )
    for system, metrics in summary["systems"].items():
        lines += [
            "",
            f"## {system}: reliability and automation",
            "",
            "| Threshold | Accepted / total | Coverage | Observed risk | Small sample |",
            "|---:|---:|---:|---:|---|",
        ]
        for point in metrics["selective_automation"]["thresholds"]:
            lines.append(
                f"| {point['threshold']} | {point['accepted']} / {point['denominator']} | {display(point['coverage'], True)} | {display(point['risk'], True)} | {point['unstable']} |"
            )
        if metrics["selective_automation"]["frozen_policy"]:
            lines += [
                "",
                "Frozen development policy (no evaluation refit):",
                FENCE + "json",
                json.dumps(metrics["selective_automation"]["frozen_policy"], indent=2),
                FENCE,
            ]
        lines += [
            "",
            "### Robustness",
            "",
            "| Transformation | Primitive | Comparable / total | Harmful flips | Mean JS drift |",
            "|---|---|---:|---:|---:|",
        ]
        for row in metrics["robustness"]:
            lines.append(
                f"| {row['variant']} | {row['primitive']} | {row['comparable_count']} / {row['count']} | {display(row['harmful_flip_rate'], True)} | {display(row['probability_drift']['value'])} |"
            )
        lines += [
            "",
            "### Repeatability, performance, cost and resources",
            "",
            "Complete measurements (null means unavailable):",
            FENCE + "json",
            json.dumps(
                {key: metrics[key] for key in ("repeatability", "performance", "cost")}, indent=2
            ),
            FENCE,
        ]
    lines += [
        "",
        "## Paired uncertainty",
        "",
        FENCE + "json",
        json.dumps(summary["comparisons"], indent=2),
        FENCE,
        "",
        "## Definitions",
        "",
    ]
    lines += [f"- **{key}:** {value}" for key, value in summary["definitions"].items()]
    lines += ["", "## Limitations and conditional interpretation", ""]
    lines += [f"- {note}" for note in summary["limitations"] + manifest["warnings"]]
    lines += [
        "- Choose a provider using the relevant workload slice, operating risk, deployment needs, and actual hardware. No universal winner is inferred.",
        "",
        "## Configuration and environment",
        "",
        FENCE + "json",
        json.dumps(
            {"configuration": manifest["effective_config"], "environment": environment}, indent=2
        ),
        FENCE,
        "",
        "The bundle includes complete per-case evidence, all attempts, dataset snapshot, events, and checksums.",
        "",
    ]
    return "\n".join(lines)


def write_reports(store, run_id, summary):
    manifest = store.manifest(run_id)
    environment = store.read_json(store.run_dir(run_id) / "environment.json")
    markdown = report_markdown(manifest, summary, environment)
    directory = store.run_dir(run_id)
    (directory / "report.md").write_text(markdown, encoding="utf-8")
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>DecisionLab evaluation report</title><style>"
        "body{font:15px/1.65 system-ui;color:#172033;background:#f8fafc;margin:0;padding:3vw}"
        "main{max-width:1100px;margin:auto;background:white;padding:3vw;border:1px solid #dbe2ea}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 monospace;background:#f1f5f9;padding:16px}"
        "table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;border-bottom:1px solid #dbe2ea;padding:8px}"
        "h2{margin-top:2em}blockquote{border-left:4px solid #6366f1;padding:8px 20px;margin:0}"
        "@media print{body,main{padding:0;border:0}}</style></head><body><main>"
        + MarkdownIt("commonmark", {"html": False}).enable("table").render(markdown)
        + "</main></body></html>"
    )
    (directory / "report.html").write_text(document, encoding="utf-8")


def bundle(store, run_id):
    directory = store.run_dir(run_id)
    output = io.BytesIO()
    checksums = {}
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix in (".json", ".jsonl", ".md", ".html"):
                data = path.read_bytes()
                checksums[path.name] = digest_bytes(data)
                archive.writestr(path.name, data)
        archive.writestr("checksums.json", json.dumps(checksums, indent=2))
    return output.getvalue()
