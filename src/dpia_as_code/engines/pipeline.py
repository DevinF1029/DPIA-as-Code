"""Unified DPIA-as-Code execution pipeline orchestrating all analysis engines."""

from __future__ import annotations

from datetime import date

from dpia_as_code.engines.dfd_parser import generate_mermaid_dfd, generate_ropa
from dpia_as_code.engines.gate import evaluate_gate
from dpia_as_code.engines.linddun_scorer import map_threats_and_score
from dpia_as_code.engines.threshold_engine import evaluate_red_lines, evaluate_thresholds
from dpia_as_code.models import AssessmentReport, DataFlowModel
from dpia_as_code.rules_loader import RulePackBundle, load_rule_bundle


def assess_dataflow(
    model: DataFlowModel,
    rule_bundle: RulePackBundle | None = None,
    as_of: date | None = None,
) -> AssessmentReport:
    """Execute the full DPIA-as-Code assessment pipeline on a validated `DataFlowModel`."""
    bundle = rule_bundle or load_rule_bundle()

    mermaid_dfd = generate_mermaid_dfd(model)
    topology_warnings = model.topology_warnings()
    ropa = generate_ropa(model)

    red_lines = evaluate_red_lines(model, bundle)
    threshold = evaluate_thresholds(model, bundle)
    findings, risk_summary = map_threats_and_score(model, bundle)
    gate = evaluate_gate(
        model=model,
        threshold=threshold,
        findings=findings,
        risk_summary=risk_summary,
        red_lines=red_lines,
        bundle=bundle,
        as_of=as_of,
    )

    return AssessmentReport(
        system_id=model.metadata.system_id,
        system_name=model.metadata.name,
        mermaid_dfd=mermaid_dfd,
        topology_warnings=topology_warnings,
        ropa=ropa,
        threshold=threshold,
        findings=findings,
        risk_summary=risk_summary,
        gate=gate,
    )
