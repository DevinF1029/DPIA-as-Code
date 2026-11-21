"""Command-line interface (`dpia`) for DPIA-as-Code."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import click

from dpia_as_code.engines import assess_dataflow
from dpia_as_code.loader import DataFlowValidationError, load_dataflow
from dpia_as_code.reporter import (
    render_json_report,
    render_markdown_report,
    render_pr_comment,
)
from dpia_as_code.rules_loader import load_rule_bundle


@click.group()
def main() -> None:
    """DPIA-as-Code: Architecture-driven DPIA/PIA/FRIA & LINDDUN privacy gate CLI."""


@main.command()
@click.argument("dataflow_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def validate(dataflow_path: Path) -> None:
    """Validate a `dataflow.yaml` file against the Pydantic v2 specification."""
    try:
        model = load_dataflow(dataflow_path)
    except DataFlowValidationError as exc:
        click.echo(f"[ERROR] {exc}", err=True)
        sys.exit(2)

    click.echo(
        f"[OK] '{dataflow_path}' validated successfully "
        f"(system={model.metadata.system_id}, assets={len(model.data_assets)}, "
        f"processes={len(model.processes)}, flows={len(model.flows)})."
    )
    for warning in model.topology_warnings():
        click.echo(f"[WARN] {warning}", err=True)


@main.command()
@click.argument("dataflow_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["md", "json", "pr-comment"], case_sensitive=False),
    default="md",
    show_default=True,
    help="Output report format.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write report to a file instead of stdout.",
)
@click.option(
    "--rules-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Optional custom directory containing Policy-as-Code rules/*.yaml.",
)
@click.option(
    "--as-of",
    "as_of_str",
    type=str,
    default=None,
    help="Reference date (YYYY-MM-DD) for evaluating RiskWaiver expiration.",
)
@click.option(
    "--no-fail",
    is_flag=True,
    default=False,
    help="Always exit 0 even when CI gate status is BLOCK (useful for report generation only).",
)
def assess(
    dataflow_path: Path,
    output_format: str,
    output_path: Path | None,
    rules_dir: Path | None,
    as_of_str: str | None,
    no_fail: bool,
) -> None:
    """Run full DPIA/PIA/FRIA & LINDDUN assessment and evaluate CI/CD gate."""
    try:
        model = load_dataflow(dataflow_path)
    except DataFlowValidationError as exc:
        click.echo(f"[ERROR] {exc}", err=True)
        sys.exit(2)

    as_of = date.fromisoformat(as_of_str) if as_of_str else None
    bundle = load_rule_bundle(rules_dir)
    report = assess_dataflow(model, rule_bundle=bundle, as_of=as_of)

    fmt = output_format.lower()
    if fmt == "json":
        rendered = render_json_report(report)
    elif fmt == "pr-comment":
        rendered = render_pr_comment(model, report)
    else:
        rendered = render_markdown_report(model, report)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        click.echo(
            f"[GATE: {report.gate.status.upper()}] Report written to {output_path} "
            f"(findings={report.risk_summary.total_findings}, "
            f"max_residual={report.risk_summary.max_residual_score})."
        )
    else:
        click.echo(rendered, nl=False)

    if not no_fail and report.gate.exit_code != 0:
        sys.exit(report.gate.exit_code)


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host address.")
@click.option("--port", default=8000, type=int, show_default=True, help="Bind port number.")
@click.option("--reload", "reload_server", is_flag=True, default=False, help="Enable auto-reload.")
def serve(host: str, port: int, reload_server: bool) -> None:
    """Launch the interactive DPIA-as-Code Governance Workbench web UI."""
    try:
        import uvicorn
    except ImportError as exc:
        click.echo(
            "[ERROR] Web UI requires `fastapi` and `uvicorn`. "
            "Install them with: pip install fastapi uvicorn",
            err=True,
        )
        raise SystemExit(2) from exc

    click.echo(f"Starting DPIA-as-Code Governance Workbench at http://{host}:{port}")
    uvicorn.run(
        "dpia_as_code.web.api:app",
        host=host,
        port=port,
        reload=reload_server,
    )


if __name__ == "__main__":
    main()
