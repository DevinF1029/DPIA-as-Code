"""Output contract models produced by DPIA-as-Code analysis engines.

These models connect the 5 core engines:
1. DFD Parser -> Mermaid DFD + RoPAEntry list
2. Threshold Engine -> ThresholdAssessment (GDPR Art. 35 / WP29 + PIPL Art. 55)
3. LINDDUN Mapper -> ThreatFinding list
4. Risk Scorer (CNIL PIA / GB/T 39335) -> RiskScore & RiskSummary
5. CI/CD Gate -> GateDecision & AssessmentReport
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dpia_as_code.models.enums import (
    DFDElementType,
    Jurisdiction,
    LawfulBasis,
    LINDDUNCategory,
    PETType,
    RedLineId,
    RiskLevel,
)


class RoPAEntry(BaseModel):
    """GDPR Article 30 Record of Processing Activities (RoPA) draft row."""

    model_config = ConfigDict(extra="forbid")

    process_id: str
    process_name: str
    controller: str
    dpo_contact: str
    purposes: list[str]
    lawful_basis: LawfulBasis
    data_subjects: list[str]
    data_categories: list[str]
    recipients: list[str] = Field(default_factory=list)
    cross_border_transfers: list[str] = Field(default_factory=list)
    retention_policies: list[str] = Field(default_factory=list)
    security_measures: list[str] = Field(default_factory=list)


class TriggeredCriterion(BaseModel):
    """A single statutory DPIA/PIA threshold rule that fired."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(description="Stable rule code (e.g., GDPR-WP29-04, PIPL-ART55-01).")
    jurisdiction: Jurisdiction
    title: str
    legal_reference: str
    reason: str
    evidence_elements: list[str] = Field(
        default_factory=list, description="DFD element or asset IDs that triggered this rule."
    )


class JurisdictionThresholdResult(BaseModel):
    """Mandatory DPIA/PIA determination for a single jurisdiction."""

    model_config = ConfigDict(extra="forbid")

    jurisdiction: Jurisdiction
    dpia_required: bool
    summary: str
    triggered_criteria: list[TriggeredCriterion] = Field(default_factory=list)


class ThresholdAssessment(BaseModel):
    """Aggregated multi-jurisdiction statutory threshold result."""

    model_config = ConfigDict(extra="forbid")

    dpia_required: bool
    fria_required: bool = Field(
        default=False,
        description="Whether EU AI Act Art. 27 Fundamental Rights Impact Assessment is required.",
    )
    important_data_assessment_required: bool = Field(
        default=False,
        description="Whether China DSL Art. 30 / NDSR Art. 31 important data risk assessment is required.",
    )
    jurisdiction_conflicts: list[str] = Field(
        default_factory=list,
        description="Cross-jurisdiction legal conflict warnings (e.g., legitimate_interests under PIPL).",
    )
    results: list[JurisdictionThresholdResult] = Field(default_factory=list)


class RiskScore(BaseModel):
    """CNIL PIA & GB/T 39335 4x4 matrix score (Likelihood 1-4 x Severity 1-4)."""

    model_config = ConfigDict(extra="forbid")

    likelihood: int = Field(ge=1, le=4, description="1=Negligible, 2=Limited, 3=Significant, 4=Maximum")
    severity: int = Field(ge=1, le=4, description="1=Negligible, 2=Limited, 3=Significant, 4=Maximum")
    score: int = Field(ge=1, le=16)
    level: RiskLevel

    @classmethod
    def from_matrix(cls, likelihood: int, severity: int) -> RiskScore:
        likelihood = max(1, min(4, likelihood))
        severity = max(1, min(4, severity))
        score = likelihood * severity
        if score >= 13:
            level = RiskLevel.CRITICAL
        elif score >= 9:
            level = RiskLevel.HIGH
        elif score >= 5:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW
        return cls(likelihood=likelihood, severity=severity, score=score, level=level)


class ThreatFinding(BaseModel):
    """A concrete LINDDUN privacy threat mapped to a specific DFD element."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(description="Deterministic finding ID (e.g., LIND-I-face_verify_api).")
    element_id: str
    element_name: str
    element_type: DFDElementType
    category: LINDDUNCategory
    title: str
    description: str
    affected_assets: list[str] = Field(default_factory=list)
    inherent_risk: RiskScore
    residual_risk: RiskScore
    applied_mitigations: list[str] = Field(
        default_factory=list, description="IDs of effective mitigations reducing this threat."
    )
    planned_mitigations: list[str] = Field(
        default_factory=list, description="IDs of planned-only mitigations (not yet reducing risk)."
    )
    recommended_pets: list[PETType] = Field(default_factory=list)


class RiskSummary(BaseModel):
    """Roll-up risk statistics across all LINDDUN findings."""

    model_config = ConfigDict(extra="forbid")

    overall_inherent_level: RiskLevel
    overall_residual_level: RiskLevel
    max_inherent_score: int = Field(ge=0, le=16)
    max_residual_score: int = Field(ge=0, le=16)
    total_findings: int = Field(ge=0)
    residual_counts: dict[RiskLevel, int] = Field(
        default_factory=lambda: {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 0,
            RiskLevel.MEDIUM: 0,
            RiskLevel.LOW: 0,
        }
    )


class RedLineViolation(BaseModel):
    """A zero-tolerance statutory red line hit (RL-01..RL-05) that forces Hard Block."""

    model_config = ConfigDict(extra="forbid")

    red_line_id: RedLineId
    rule_id: str
    title: str
    legal_reference: str
    reason: str
    evidence_elements: list[str] = Field(default_factory=list)


class WaiverEvaluation(BaseModel):
    """Runtime evaluation result of a declared RiskWaiver."""

    model_config = ConfigDict(extra="forbid")

    waiver_id: str
    target_findings: list[str] = Field(default_factory=list)
    status: Literal["active", "expired", "invalid"]
    expires_at: date
    reason: str | None = None


class GateDecision(BaseModel):
    """CI/CD merge gate decision derived from red lines, threshold, risk, waivers, and DPO sign-off."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["pass", "warn", "block"]
    exit_code: int = Field(description="0 for pass/warn, 1 for block.")
    reasons: list[str] = Field(default_factory=list)
    red_line_violations: list[RedLineViolation] = Field(default_factory=list)
    waiver_evaluations: list[WaiverEvaluation] = Field(default_factory=list)


class RemediationItem(BaseModel):
    """Actionable remediation row linked to a LINDDUN ThreatFinding (Section 6.2)."""

    model_config = ConfigDict(extra="forbid")

    rem_id: str = Field(description="Sequential remediation ID (e.g., REM-01).")
    finding_id: str = Field(default="", description="Linked ThreatFinding ID.")
    control_id: str = Field(default="", description="Target control ID (e.g., PC-ENC-02).")
    action: str = Field(default="", description="Concrete engineering or governance action.")
    owner: str = Field(default="", description="Accountable owner or team.")
    due_date: str = Field(default="", description="Target completion date (YYYY-MM-DD).")
    evidence: str = Field(default="", description="Verification PR, ticket, or audit evidence link.")
    status: Literal["Open", "In Progress", "Closed"] = "Open"


class SignOffEntry(BaseModel):
    """Formal approval row for the DPIA Sign-Off table (Section 7)."""

    model_config = ConfigDict(extra="forbid")

    role: str
    name: str = ""
    decision: str = ""
    comments: str = ""
    signed_date: str = ""


class HumanReviewSheet(BaseModel):
    """Interactive human-judgment supplement captured in the DPIA Sheet (DPO / BO / 2LoD)."""

    model_config = ConfigDict(extra="forbid")

    assessment_id: str = ""
    business_owner: str = ""
    lawful_basis_rationale: str = ""
    necessity_proportionality: str = ""
    data_subject_rights_sla: str = ""
    fria_affected_groups: str = ""
    fria_fairness_bias: str = ""
    fria_human_oversight: str = ""
    important_data_impact: str = ""
    important_data_filing_ref: str = ""
    remediations: list[RemediationItem] = Field(default_factory=list)
    signoffs: list[SignOffEntry] = Field(default_factory=list)


class AssessmentReport(BaseModel):
    """Complete DPIA-as-Code execution output."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    system_id: str
    system_name: str
    mermaid_dfd: str
    topology_warnings: list[str] = Field(default_factory=list)
    ropa: list[RoPAEntry] = Field(default_factory=list)
    threshold: ThresholdAssessment
    findings: list[ThreatFinding] = Field(default_factory=list)
    risk_summary: RiskSummary
    gate: GateDecision
