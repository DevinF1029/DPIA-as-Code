"""LINDDUN Privacy Threat Mapper & CNIL x GB/T 39335 Quantitative Risk Scorer.

Reads the DFD x LINDDUN matrix, scoring anchors, maturity discounting parameters,
and PC-xxx-xx control catalog directly from `rules/linddun_matrix.yaml` and
`rules/control_catalog.yaml`.
"""

from __future__ import annotations

import math

from dpia_as_code.models import (
    AIRiskTier,
    DataAsset,
    DataCategory,
    DataFlow,
    DataFlowModel,
    DataStore,
    DFDElementType,
    ExternalEntity,
    IdentifiabilityLevel,
    LawfulBasis,
    LINDDUNCategory,
    Mitigation,
    MitigationStatus,
    PETType,
    ProcessNode,
    ProcessingOperation,
    ProcessingScale,
    RiskLevel,
    RiskScore,
    RiskSummary,
    ThreatFinding,
    TransferMechanism,
)
from dpia_as_code.rules_loader import ControlDefinition, RulePackBundle

_CATEGORY_SHORT: dict[LINDDUNCategory, str] = {
    LINDDUNCategory.LINKABILITY: "L",
    LINDDUNCategory.IDENTIFIABILITY: "I",
    LINDDUNCategory.NON_REPUDIATION: "NR",
    LINDDUNCategory.DETECTABILITY: "DE",
    LINDDUNCategory.DISCLOSURE: "D",
    LINDDUNCategory.UNAWARENESS: "U",
    LINDDUNCategory.NON_COMPLIANCE: "NC",
}

_EXTREME_SEVERITY_CATEGORIES: frozenset[DataCategory] = frozenset(
    {
        DataCategory.BIOMETRIC,
        DataCategory.GENETIC,
        DataCategory.MINOR_UNDER_14,
    }
)


def _base_severity(model: DataFlowModel, assets: list[DataAsset]) -> int:
    """Compute baseline Severity (S = 1..4) aligned with GB/T 39335 & CNIL PIA anchors."""
    if not assets:
        return 1

    # Level 4 (Maximum): irreversible biometric/genetic, minors <14, important/core/CIIO, high-risk AI, >=10M
    if any(
        a.is_important_or_core or any(c in _EXTREME_SEVERITY_CATEGORIES for c in a.categories)
        for a in assets
    ):
        return 4
    if model.metadata.is_ciio or (model.metadata.estimated_subjects or 0) >= 10_000_000:
        return 4
    if model.metadata.ai_system and model.metadata.ai_system.risk_tier in (
        AIRiskTier.HIGH_RISK,
        AIRiskTier.PROHIBITED,
    ):
        return 4

    # Level 3 (Significant): sensitive personal data, large scale, vulnerable subjects
    if (
        any(a.is_sensitive_any for a in assets)
        or model.metadata.scale == ProcessingScale.LARGE
        or model.metadata.has_vulnerable_subjects
    ):
        return 3

    # Level 2 (Limited): directly identifiable general personal data or medium scale
    if (
        any(a.identifiability == IdentifiabilityLevel.DIRECTLY_IDENTIFIABLE for a in assets)
        or model.metadata.scale == ProcessingScale.MEDIUM
    ):
        return 2

    return 1


def _resolve_controls_for_mitigation(
    mit: Mitigation,
    bundle: RulePackBundle,
) -> list[ControlDefinition]:
    """Match a declared Mitigation to ControlDefinition(s) via control_id or pet_type."""
    by_id = bundle.control_catalog.by_id()
    if mit.control_id and mit.control_id in by_id:
        return [by_id[mit.control_id]]
    return bundle.control_catalog.by_pet_type(mit.pet_type)


def _apply_mitigations(
    inherent: RiskScore,
    category: LINDDUNCategory,
    mitigations: list[Mitigation],
    bundle: RulePackBundle,
) -> tuple[RiskScore, list[str], list[str]]:
    """Apply maturity-discounted controls to compute Residual Risk."""
    discount_cfg = bundle.linddun_matrix.maturity_discounting
    applied_ids: list[str] = []
    planned_ids: list[str] = []

    best_l_reduction = 0
    best_s_reduction = 0

    for mit in mitigations:
        matched_ctrls = _resolve_controls_for_mitigation(mit, bundle)
        # Check whether this mitigation addresses the threat category
        explicit_match = (
            mit.addresses_threats is not None and category in mit.addresses_threats
        )
        catalog_ctrls = [c for c in matched_ctrls if category in c.mitigates_threats]
        if not explicit_match and not catalog_ctrls:
            continue

        if mit.status == MitigationStatus.PLANNED:
            planned_ids.append(mit.id)
            continue

        # Effective control (implemented or verified)
        applied_ids.append(mit.id)
        max_l = max((c.max_likelihood_reduction for c in catalog_ctrls), default=1)
        max_s = max((c.max_severity_reduction for c in catalog_ctrls), default=0)

        if mit.status == MitigationStatus.IMPLEMENTED:
            cap = discount_cfg.implemented.max_step_reduction
            l_red = math.ceil(max_l * discount_cfg.implemented.likelihood_factor)
            s_red = math.floor(max_s * discount_cfg.implemented.severity_factor)
            if cap is not None:
                l_red = min(l_red, cap)
                s_red = min(s_red, cap)
        else:  # VERIFIED
            l_red = round(max_l * discount_cfg.verified.likelihood_factor)
            s_red = round(max_s * discount_cfg.verified.severity_factor)

        best_l_reduction = max(best_l_reduction, l_red)
        best_s_reduction = max(best_s_reduction, s_red)

    floor = discount_cfg.score_floor
    res_l = max(floor, inherent.likelihood - best_l_reduction)
    res_s = max(floor, inherent.severity - best_s_reduction)
    return RiskScore.from_matrix(res_l, res_s), applied_ids, planned_ids


def _recommend_pets(category: LINDDUNCategory, bundle: RulePackBundle) -> list[PETType]:
    """Recommend top PETs from the control catalog that mitigate the given LINDDUN threat."""
    pets: list[PETType] = []
    for ctrl in bundle.control_catalog.controls:
        if category in ctrl.mitigates_threats:
            for pet in ctrl.pet_types:
                if pet not in pets:
                    pets.append(pet)
    return pets[:4]


def _assets_for_element(
    element: ExternalEntity | ProcessNode | DataStore | DataFlow,
    model: DataFlowModel,
) -> list[DataAsset]:
    assets_map = model.data_asset_map()
    if isinstance(element, (DataStore, DataFlow)):
        return [assets_map[aid] for aid in element.data]
    asset_ids = {
        aid
        for f in model.flows
        if f.source == element.id or f.target == element.id
        for aid in f.data
    }
    return [assets_map[aid] for aid in sorted(asset_ids)]


def _should_skip_element(assets: list[DataAsset], bundle: RulePackBundle) -> bool:
    """Apply secondary pruning rules (skip purely anonymized / non-personal general data)."""
    pruning = bundle.linddun_matrix.pruning_rules
    if not assets:
        return True
    if pruning.exclude_anonymized_for_privacy_threats and all(
        a.identifiability == IdentifiabilityLevel.ANONYMIZED and not a.is_important_or_core
        for a in assets
    ):
        return True
    if pruning.exclude_non_personal_unless_important_data and all(
        not a.is_personal_data and not a.is_important_or_core for a in assets
    ):
        return True
    return False


def _make_finding(
    model: DataFlowModel,
    bundle: RulePackBundle,
    element: ExternalEntity | ProcessNode | DataStore | DataFlow,
    category: LINDDUNCategory,
    title: str,
    description: str,
    assets: list[DataAsset],
    likelihood: int,
    severity: int,
) -> ThreatFinding:
    inherent = RiskScore.from_matrix(likelihood, severity)
    mits = model.get_mitigations_for(element.id)
    residual, applied, planned = _apply_mitigations(inherent, category, mits, bundle)
    return ThreatFinding(
        finding_id=f"LIND-{_CATEGORY_SHORT[category]}-{element.id}",
        element_id=element.id,
        element_name=element.name or element.id,
        element_type=element.element_type,
        category=category,
        title=title,
        description=description,
        affected_assets=[a.id for a in assets],
        inherent_risk=inherent,
        residual_risk=residual,
        applied_mitigations=applied,
        planned_mitigations=planned,
        recommended_pets=_recommend_pets(category, bundle),
    )


def map_threats_and_score(
    model: DataFlowModel,
    bundle: RulePackBundle,
) -> tuple[list[ThreatFinding], RiskSummary]:
    """Run LINDDUN threat mapping and CNIL x GB/T 39335 scoring across all DFD elements."""
    findings: list[ThreatFinding] = []
    matrix = bundle.linddun_matrix.dfd_linddun_matrix

    # 1. External Entities
    for entity in model.entities:
        allowed = set(matrix.get(DFDElementType.EXTERNAL_ENTITY, []))
        assets = _assets_for_element(entity, model)
        if _should_skip_element(assets, bundle):
            continue
        sev = _base_severity(model, assets)

        if (
            LINDDUNCategory.UNAWARENESS in allowed
            and entity.role.value == "data_subject"
            and (not entity.notice_provided or not entity.opt_out_available)
        ):
            missing = []
            if not entity.notice_provided:
                missing.append("缺少隐私告知（notice_provided=false）")
            if not entity.opt_out_available:
                missing.append("缺少撤回同意/拒绝画像机制（opt_out_available=false）")
            findings.append(
                _make_finding(
                    model,
                    bundle,
                    entity,
                    LINDDUNCategory.UNAWARENESS,
                    "数据主体知情权或干预权不足",
                    "；".join(missing) + "。",
                    assets,
                    likelihood=3 if not entity.notice_provided else 2,
                    severity=sev,
                )
            )

        if (
            LINDDUNCategory.NON_COMPLIANCE in allowed
            and entity.is_third_party
            and not entity.dpa_signed
        ):
            findings.append(
                _make_finding(
                    model,
                    bundle,
                    entity,
                    LINDDUNCategory.NON_COMPLIANCE,
                    "第三方接收方未签署数据处理协议（DPA/委托协议）",
                    f"外部实体 '{entity.name}' 角色为 {entity.role.value}，但 `dpa_signed=false`。",
                    assets,
                    likelihood=4,
                    severity=sev,
                )
            )

    # 2. Processes
    for proc in model.processes:
        allowed = set(matrix.get(DFDElementType.PROCESS, []))
        assets = _assets_for_element(proc, model)
        if _should_skip_element(assets, bundle):
            continue
        sev = _base_severity(model, assets)
        if proc.prevents_rights_or_service:
            sev = max(sev, 3)

        if LINDDUNCategory.LINKABILITY in allowed and any(
            op in proc.operations
            for op in (
                ProcessingOperation.PROFILING,
                ProcessingOperation.SCORING,
                ProcessingOperation.DATASET_MATCHING,
            )
        ):
            findings.append(
                _make_finding(
                    model,
                    bundle,
                    proc,
                    LINDDUNCategory.LINKABILITY,
                    "跨数据集关联画像导致高可链接性风险",
                    f"处理节点 '{proc.name}' 执行 {[op.value for op in proc.operations]}，可将多源记录关联至同一自然人。",
                    assets,
                    likelihood=3,
                    severity=sev,
                )
            )

        if LINDDUNCategory.IDENTIFIABILITY in allowed and (
            ProcessingOperation.BIOMETRIC_IDENTIFICATION in proc.operations
            or ProcessingOperation.AI_TRAINING in proc.operations
        ):
            findings.append(
                _make_finding(
                    model,
                    bundle,
                    proc,
                    LINDDUNCategory.IDENTIFIABILITY,
                    "生物识别或 AI 训练带来的直接身份重识别风险",
                    f"处理节点 '{proc.name}' 处理高识别度特征，存在不可逆身份暴露或模型记忆反演风险。",
                    assets,
                    likelihood=3,
                    severity=max(sev, 3),
                )
            )

        if (
            LINDDUNCategory.UNAWARENESS in allowed
            and ProcessingOperation.AUTOMATED_DECISION_MAKING in proc.operations
            and not proc.human_review_available
        ):
            findings.append(
                _make_finding(
                    model,
                    bundle,
                    proc,
                    LINDDUNCategory.UNAWARENESS,
                    "自动化决策缺失人工介入与可干预通道",
                    f"处理节点 '{proc.name}' 执行自动化决策但 `human_review_available=false`。",
                    assets,
                    likelihood=4 if proc.prevents_rights_or_service else 3,
                    severity=sev,
                )
            )

        if LINDDUNCategory.NON_COMPLIANCE in allowed and proc.lawful_basis == LawfulBasis.UNSPECIFIED:
            findings.append(
                _make_finding(
                    model,
                    bundle,
                    proc,
                    LINDDUNCategory.NON_COMPLIANCE,
                    "处理活动缺失法定合法性基础",
                    f"处理节点 '{proc.name}' 的 `lawful_basis` 为 `unspecified`。",
                    assets,
                    likelihood=4,
                    severity=sev,
                )
            )

    # 3. Data Stores
    for store in model.stores:
        allowed = set(matrix.get(DFDElementType.DATA_STORE, []))
        assets = _assets_for_element(store, model)
        if _should_skip_element(assets, bundle):
            continue
        sev = _base_severity(model, assets)

        if LINDDUNCategory.DISCLOSURE in allowed and (
            not store.encrypted_at_rest or not store.access_control or not store.audit_logging
        ):
            gaps = []
            if not store.encrypted_at_rest:
                gaps.append("未开启静态加密")
            if not store.access_control:
                gaps.append("未配置访问控制")
            if not store.audit_logging:
                gaps.append("未开启访问审计日志")
            lik = 4 if (not store.encrypted_at_rest and not store.access_control) else (
                3 if not store.encrypted_at_rest else 2
            )
            findings.append(
                _make_finding(
                    model,
                    bundle,
                    store,
                    LINDDUNCategory.DISCLOSURE,
                    "数据存储安全防护缺陷导致信息泄露风险",
                    f"存储节点 '{store.name}' 存在以下短板：{'、'.join(gaps)}。",
                    assets,
                    likelihood=lik,
                    severity=sev,
                )
            )

        if LINDDUNCategory.NON_COMPLIANCE in allowed and store.retention_days is None:
            findings.append(
                _make_finding(
                    model,
                    bundle,
                    store,
                    LINDDUNCategory.NON_COMPLIANCE,
                    "数据存储未设定留存期限上限（无限期留存）",
                    f"存储节点 '{store.name}' 的 `retention_days` 为空，违背最小存储期限原则。",
                    assets,
                    likelihood=3,
                    severity=sev,
                )
            )

    # 4. Data Flows
    for flow in model.flows:
        allowed = set(matrix.get(DFDElementType.DATA_FLOW, []))
        assets = _assets_for_element(flow, model)
        if _should_skip_element(assets, bundle):
            continue
        sev = _base_severity(model, assets)
        is_cb = model.is_cross_border_flow(flow)

        if LINDDUNCategory.DISCLOSURE in allowed and not flow.encrypted_in_transit:
            findings.append(
                _make_finding(
                    model,
                    bundle,
                    flow,
                    LINDDUNCategory.DISCLOSURE,
                    "数据流明文传输导致窃听与泄露风险",
                    f"数据流 '{flow.id}' ({flow.source} -> {flow.target}) 未启用传输层加密。",
                    assets,
                    likelihood=4,
                    severity=sev,
                )
            )

        if (
            LINDDUNCategory.NON_COMPLIANCE in allowed
            and is_cb
            and flow.transfer_mechanism == TransferMechanism.NONE
        ):
            findings.append(
                _make_finding(
                    model,
                    bundle,
                    flow,
                    LINDDUNCategory.NON_COMPLIANCE,
                    "跨境数据流缺失法定传输合规机制",
                    f"跨境流 '{flow.id}' ({model.resolve_region(flow.source)} -> {model.resolve_region(flow.target)}) 的 `transfer_mechanism=none`。",
                    assets,
                    likelihood=4,
                    severity=sev,
                )
            )

    # Roll-up RiskSummary
    residual_counts: dict[RiskLevel, int] = {
        RiskLevel.CRITICAL: 0,
        RiskLevel.HIGH: 0,
        RiskLevel.MEDIUM: 0,
        RiskLevel.LOW: 0,
    }
    max_inherent = 0
    max_residual = 0
    for f in findings:
        max_inherent = max(max_inherent, f.inherent_risk.score)
        max_residual = max(max_residual, f.residual_risk.score)
        residual_counts[f.residual_risk.level] += 1

    overall_inherent = _level_from_score(max_inherent)
    overall_residual = _level_from_score(max_residual)

    summary = RiskSummary(
        overall_inherent_level=overall_inherent,
        overall_residual_level=overall_residual,
        max_inherent_score=max_inherent,
        max_residual_score=max_residual,
        total_findings=len(findings),
        residual_counts=residual_counts,
    )
    return findings, summary


def _level_from_score(score: int) -> RiskLevel:
    if score >= 13:
        return RiskLevel.CRITICAL
    if score >= 9:
        return RiskLevel.HIGH
    if score >= 5:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
