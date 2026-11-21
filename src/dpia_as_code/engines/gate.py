"""CI/CD Merge Gate Decision Engine (governance/01_governance_policy.md §3 & §4)."""

from __future__ import annotations

from datetime import date

from dpia_as_code.models import (
    DataFlowModel,
    GateDecision,
    RedLineViolation,
    RiskLevel,
    RiskSummary,
    ThreatFinding,
    ThresholdAssessment,
    WaiverEvaluation,
)
from dpia_as_code.rules_loader import RulePackBundle


def evaluate_gate(
    model: DataFlowModel,
    threshold: ThresholdAssessment,
    findings: list[ThreatFinding],
    risk_summary: RiskSummary,
    red_lines: list[RedLineViolation],
    bundle: RulePackBundle,
    as_of: date | None = None,
) -> GateDecision:
    """Compute final CI/CD gate decision (`pass` / `warn` / `block`)."""
    check_date = as_of or date.today()
    reasons: list[str] = []
    waiver_evals: list[WaiverEvaluation] = []

    # 1. Evaluate declared waivers for expiry and covered targets
    waived_targets: set[str] = set()
    for waiver in model.metadata.risk_waivers:
        if waiver.is_active(check_date):
            waiver_evals.append(
                WaiverEvaluation(
                    waiver_id=waiver.waiver_id,
                    target_findings=list(waiver.target_findings),
                    status="active",
                    expires_at=waiver.expires_at,
                    reason=f"豁免有效（到期日：{waiver.expires_at}，审批人：{waiver.approved_by}）。",
                )
            )
            waived_targets.update(waiver.target_findings)
        else:
            waiver_evals.append(
                WaiverEvaluation(
                    waiver_id=waiver.waiver_id,
                    target_findings=list(waiver.target_findings),
                    status="expired",
                    expires_at=waiver.expires_at,
                    reason=f"豁免已于 {waiver.expires_at} 到期失效，自动恢复阻断检查。",
                )
            )
            reasons.append(f"风险豁免单 '{waiver.waiver_id}' 已过期（到期日 {waiver.expires_at}）。")

    blocked = False
    warned = False

    # 2. Zero-tolerance statutory red lines -> unconditionally BLOCK
    if red_lines:
        blocked = True
        for rl in red_lines:
            reasons.append(f"[红线阻断 {rl.red_line_id.value}] {rl.title}：{rl.reason}")

    # 3. Cross-jurisdiction ERROR-level conflicts (e.g., legitimate_interests under PIPL)
    for conflict in threshold.jurisdiction_conflicts:
        if "CONFLICT-LB-LEGITIMATE-INTERESTS" in conflict:
            blocked = True
            reasons.append(f"[跨法域冲突阻断] {conflict}")

    # 4. Unwaived HIGH / CRITICAL residual risk findings -> BLOCK
    unwaived_high_crit = [
        f
        for f in findings
        if f.residual_risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        and f.finding_id not in waived_targets
        and f.element_id not in waived_targets
    ]
    if unwaived_high_crit:
        blocked = True
        ids = [f"{f.finding_id}({f.residual_risk.level.value}:{f.residual_risk.score})" for f in unwaived_high_crit]
        reasons.append(f"存在 {len(unwaived_high_crit)} 项未豁免的高/极高残余风险：{', '.join(ids)}。")

    # 5. High-Inherent Risk DPO Sign-Off Policy Patch (governance/01 §3.2)
    gate_cfg = bundle.linddun_matrix.risk_appetite_gate
    if (
        gate_cfg.high_inherent_requires_dpo_signoff
        and risk_summary.overall_inherent_level == RiskLevel.CRITICAL
        and not (model.metadata.dpo_signoff and model.metadata.dpo_signoff.approved)
    ):
        blocked = True
        reasons.append(
            "系统固有风险达到 CRITICAL，按治理政策首次上线必须完成 DPO 人工复核签批（dpo_signoff.approved=true）。"
        )

    # 6. Medium residual risk -> WARN
    if not blocked and risk_summary.overall_residual_level == RiskLevel.MEDIUM:
        warned = True
        reasons.append("残余最高风险为 MEDIUM，允许警示放行，请在 14 个工作日内闭环缓解计划。")

    # 7. Active waiver note when it prevented a block
    if not blocked and waived_targets:
        warned = True
        reasons.append("存在生效中的限时风险豁免单，请在到期前完成根治整改。")

    if blocked:
        return GateDecision(
            status="block",
            exit_code=1,
            reasons=reasons,
            red_line_violations=red_lines,
            waiver_evaluations=waiver_evals,
        )
    if warned:
        return GateDecision(
            status="warn",
            exit_code=0,
            reasons=reasons,
            red_line_violations=[],
            waiver_evaluations=waiver_evals,
        )

    return GateDecision(
        status="pass",
        exit_code=0,
        reasons=["未命中法定红线，残余风险处于可接受范围（LOW），门禁自动放行。"],
        red_line_violations=[],
        waiver_evaluations=waiver_evals,
    )
