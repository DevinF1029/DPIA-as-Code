"""Policy-as-Code rule bundle loader & validator for `rules/*.yaml`.

Loads and cross-validates the 4 machine-readable rule packs that bridge
`governance/` documents and the Python execution engines:
1. `rules/red_lines.yaml`       -> Statutory zero-tolerance red lines (RL-01..RL-05)
2. `rules/thresholds.yaml`      -> Multi-jurisdiction trigger criteria & conflicts
3. `rules/linddun_matrix.yaml`  -> DFD x LINDDUN matrix, scoring rubric & gate appetite
4. `rules/control_catalog.yaml` -> Standardized PC-xxx-xx control catalog & discounts
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from dpia_as_code.models.dataflow import ControlId
from dpia_as_code.models.enums import (
    DFDElementType,
    Jurisdiction,
    LINDDUNCategory,
    PETType,
    ProcessingOperation,
    RedLineId,
)


class _StrictRuleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ----------------------------------------------------------------------
# 1. Red Lines Pack (`rules/red_lines.yaml`)
# ----------------------------------------------------------------------


class RedLineRule(_StrictRuleModel):
    id: RedLineId
    rule_id: str
    title: str
    jurisdictions: list[Jurisdiction] = Field(min_length=1)
    legal_references: list[str] = Field(min_length=1)
    condition_key: str
    observed_fields: list[str] = Field(min_length=1)
    action: Literal["hard_block"] = "hard_block"
    remediation_guidance: str


class RedLinesPack(_StrictRuleModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_ref: str
    waivable: Literal[False] = False
    red_lines: list[RedLineRule] = Field(min_length=1)


# ----------------------------------------------------------------------
# 2. Thresholds Pack (`rules/thresholds.yaml`)
# ----------------------------------------------------------------------


class ThresholdCriterionRule(_StrictRuleModel):
    rule_id: str
    title: str
    legal_reference: str
    condition_key: str
    related_controls: list[ControlId] = Field(default_factory=list)


class JurisdictionThresholdPack(_StrictRuleModel):
    dpia_trigger_min_criteria: int = Field(ge=1)
    large_scale_subject_threshold: int | None = None
    subject_volume_tiers: dict[str, int] = Field(default_factory=dict)
    criteria: list[ThresholdCriterionRule] = Field(min_length=1)


class CrossJurisdictionConflictRule(_StrictRuleModel):
    conflict_id: str
    jurisdictions: list[Jurisdiction] = Field(min_length=2)
    description: str
    condition_key: str
    severity: Literal["error", "warn", "info"]


class ThresholdsPack(_StrictRuleModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_ref: str
    jurisdiction_rules: dict[Jurisdiction, JurisdictionThresholdPack]
    cross_jurisdiction_conflicts: list[CrossJurisdictionConflictRule] = Field(default_factory=list)


# ----------------------------------------------------------------------
# 3. LINDDUN Matrix & Scoring Pack (`rules/linddun_matrix.yaml`)
# ----------------------------------------------------------------------


class PruningRules(_StrictRuleModel):
    exclude_anonymized_for_privacy_threats: bool = True
    exclude_non_personal_unless_important_data: bool = True
    elevate_linkability_on_operations: list[ProcessingOperation] = Field(default_factory=list)
    elevate_disclosure_when_unencrypted: bool = True
    trigger_unawareness_on_missing_notice_or_opt_out: bool = True


class ScoreRange(_StrictRuleModel):
    min: int = Field(ge=1, le=16)
    max: int = Field(ge=1, le=16)


class ScoringRubric(_StrictRuleModel):
    severity_anchors: dict[int, str]
    likelihood_anchors: dict[int, str]
    matrix_thresholds: dict[Literal["low", "medium", "high", "critical"], ScoreRange]


class MaturityDiscount(_StrictRuleModel):
    likelihood_factor: float = Field(ge=0.0, le=1.0)
    severity_factor: float = Field(ge=0.0, le=1.0)
    max_step_reduction: int | None = Field(default=None, ge=0, le=3)
    requires_evidence: bool = False
    counts_as_effective: bool


class MaturityDiscountingConfig(_StrictRuleModel):
    planned: MaturityDiscount
    implemented: MaturityDiscount
    verified: MaturityDiscount
    score_floor: int = Field(default=1, ge=1, le=4)


class GateLevelPolicy(_StrictRuleModel):
    action: Literal["pass", "warn", "block"]
    exit_code: int
    review_cycle_days: int | None = None
    remediation_sla_workdays: int | None = None
    waiver_allowed: bool = False
    max_waiver_days: int | None = None
    requires_dpo_and_executive_signoff: bool = False
    requires_regulatory_consultation_check: bool = False


class RiskAppetiteGateConfig(_StrictRuleModel):
    low: GateLevelPolicy
    medium: GateLevelPolicy
    high: GateLevelPolicy
    critical: GateLevelPolicy
    high_inherent_requires_dpo_signoff: bool = True


class LinddunMatrixPack(_StrictRuleModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_ref: str
    dfd_linddun_matrix: dict[DFDElementType, list[LINDDUNCategory]]
    pruning_rules: PruningRules
    scoring_rubric: ScoringRubric
    maturity_discounting: MaturityDiscountingConfig
    risk_appetite_gate: RiskAppetiteGateConfig


# ----------------------------------------------------------------------
# 4. Control Catalog Pack (`rules/control_catalog.yaml`)
# ----------------------------------------------------------------------


class ControlDefinition(_StrictRuleModel):
    id: ControlId
    domain: Literal["PC-GOV", "PC-DAT", "PC-ENC", "PC-ACC", "PC-AI", "PC-XBD"]
    name: str
    pet_types: list[PETType] = Field(min_length=1)
    mitigates_threats: list[LINDDUNCategory] = Field(min_length=1)
    reduces_dimensions: list[Literal["likelihood", "severity"]] = Field(min_length=1)
    max_likelihood_reduction: int = Field(ge=0, le=3)
    max_severity_reduction: int = Field(ge=0, le=3)
    regulations: list[str] = Field(min_length=1)
    audit_evidence: str


class ControlCatalogPack(_StrictRuleModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_ref: str
    controls: list[ControlDefinition] = Field(min_length=1)

    def by_id(self) -> dict[str, ControlDefinition]:
        return {c.id: c for c in self.controls}

    def by_pet_type(self, pet_type: PETType) -> list[ControlDefinition]:
        return [c for c in self.controls if pet_type in c.pet_types]


# ----------------------------------------------------------------------
# Aggregated Rule Bundle with Cross-File Integrity Checks
# ----------------------------------------------------------------------


class RulePackBundle(_StrictRuleModel):
    """Complete validated Policy-as-Code bundle loaded from `rules/`."""

    red_lines: RedLinesPack
    thresholds: ThresholdsPack
    linddun_matrix: LinddunMatrixPack
    control_catalog: ControlCatalogPack

    @model_validator(mode="after")
    def _validate_cross_references(self) -> RulePackBundle:
        # Ensure unique control IDs
        seen_controls: set[str] = set()
        for ctrl in self.control_catalog.controls:
            if ctrl.id in seen_controls:
                raise ValueError(f"Duplicate control ID in control_catalog.yaml: '{ctrl.id}'")
            seen_controls.add(ctrl.id)

        # Ensure unique red line IDs
        seen_rl: set[RedLineId] = set()
        for rl in self.red_lines.red_lines:
            if rl.id in seen_rl:
                raise ValueError(f"Duplicate red line ID in red_lines.yaml: '{rl.id.value}'")
            seen_rl.add(rl.id)

        # Ensure every related_control referenced in thresholds.yaml exists in control_catalog.yaml
        for jurisdiction, j_pack in self.thresholds.jurisdiction_rules.items():
            for criterion in j_pack.criteria:
                missing = [cid for cid in criterion.related_controls if cid not in seen_controls]
                if missing:
                    raise ValueError(
                        f"Threshold rule '{criterion.rule_id}' ({jurisdiction.value}) references "
                        f"undefined control IDs: {missing}"
                    )
        return self


def default_rules_dir() -> Path:
    """Resolve the repository's default `rules/` directory."""
    return Path(__file__).resolve().parents[2] / "rules"


def _load_yaml_file(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Rule pack file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"Expected YAML mapping at root of {path}")
    return data


def load_rule_bundle(rules_dir: str | Path | None = None) -> RulePackBundle:
    """Load and cross-validate all 4 Policy-as-Code YAML files from `rules_dir`."""
    base = Path(rules_dir) if rules_dir is not None else default_rules_dir()
    return RulePackBundle(
        red_lines=RedLinesPack.model_validate(_load_yaml_file(base / "red_lines.yaml")),
        thresholds=ThresholdsPack.model_validate(_load_yaml_file(base / "thresholds.yaml")),
        linddun_matrix=LinddunMatrixPack.model_validate(
            _load_yaml_file(base / "linddun_matrix.yaml")
        ),
        control_catalog=ControlCatalogPack.model_validate(
            _load_yaml_file(base / "control_catalog.yaml")
        ),
    )
