"""Statutory Red-Line evaluator and Multi-Jurisdiction Threshold Engine.

Reads all rule definitions from `rules/red_lines.yaml` and `rules/thresholds.yaml`
so regulatory metadata stays decoupled from Python evaluation logic.
"""

from __future__ import annotations

from dpia_as_code.models import (
    AIRiskTier,
    DataFlowModel,
    Jurisdiction,
    JurisdictionThresholdResult,
    LawfulBasis,
    ProcessingOperation,
    ProcessingScale,
    RedLineViolation,
    ThresholdAssessment,
    TransferMechanism,
    TriggeredCriterion,
)
from dpia_as_code.rules_loader import RulePackBundle


def _evaluate_red_line_condition(
    condition_key: str,
    model: DataFlowModel,
) -> tuple[bool, str, list[str]]:
    """Evaluate a statutory zero-tolerance red-line condition against `DataFlowModel`."""
    assets = model.data_asset_map()

    if condition_key == "ai_prohibited_practice":
        ai = model.metadata.ai_system
        if ai and (ai.prohibited_practices or ai.risk_tier == AIRiskTier.PROHIBITED):
            practices = [p.value for p in ai.prohibited_practices] or ["risk_tier=prohibited"]
            return (
                True,
                f"系统声明了 EU AI Act Art. 5 禁止类 AI 实践：{', '.join(practices)}。",
                ["metadata.ai_system"],
            )
        return False, "", []

    if condition_key == "missing_lawful_basis_or_sensitive_prerequisite":
        bad_procs = [p.id for p in model.processes if p.lawful_basis == LawfulBasis.UNSPECIFIED]
        # Check PIPL sensitive data or minors under 14 without separate_consent
        pipl_active = Jurisdiction.PIPL in model.metadata.jurisdictions
        missing_sep_consent: list[str] = []
        if pipl_active:
            for proc in model.processes:
                # Find assets processed by this node
                proc_asset_ids = {
                    aid
                    for f in model.flows
                    if f.source == proc.id or f.target == proc.id
                    for aid in f.data
                }
                has_pipl_sensitive = any(
                    assets[aid].is_sensitive_for(Jurisdiction.PIPL) for aid in proc_asset_ids
                )
                if has_pipl_sensitive and proc.lawful_basis in (
                    LawfulBasis.CONSENT,
                    LawfulBasis.LEGITIMATE_INTERESTS,
                    LawfulBasis.UNSPECIFIED,
                ):
                    missing_sep_consent.append(proc.id)

        evidence = sorted(set(bad_procs + missing_sep_consent))
        if evidence:
            reasons: list[str] = []
            if bad_procs:
                reasons.append(f"处理节点 {bad_procs} 未声明合法性基础（unspecified）")
            if missing_sep_consent:
                reasons.append(
                    f"处理节点 {missing_sep_consent} 涉及 PIPL 敏感个人信息但未取得单独同意（separate_consent）或法定非同意基础"
                )
            return True, "；".join(reasons) + "。", evidence
        return False, "", []

    if condition_key == "unlawful_cross_border_transfer":
        bad_flows: list[str] = []
        details: list[str] = []
        for flow in model.get_cross_border_flows():
            flow_assets = [assets[aid] for aid in flow.data]
            has_imp_or_core = any(a.is_important_or_core for a in flow_assets)
            if flow.transfer_mechanism == TransferMechanism.NONE:
                bad_flows.append(flow.id)
                details.append(f"跨境流 '{flow.id}' 未配置任何法定跨境机制（transfer_mechanism=none）")
            elif (
                (model.metadata.is_ciio or has_imp_or_core)
                and flow.transfer_mechanism != TransferMechanism.PIPL_SECURITY_ASSESSMENT
            ):
                bad_flows.append(flow.id)
                details.append(
                    f"CIIO 或重要/核心数据跨境流 '{flow.id}' 必须通过网信办安全评估（pipl_security_assessment），当前为 '{flow.transfer_mechanism.value}'"
                )
        if bad_flows:
            return True, "；".join(details) + "。", sorted(set(bad_flows))
        return False, "", []

    if condition_key == "unprotected_high_sensitivity_data":
        exposed: list[str] = []
        details = []
        for flow in model.flows:
            has_high_sens = any(
                assets[aid].is_sensitive_any or assets[aid].is_important_or_core
                for aid in flow.data
            )
            if has_high_sens and not flow.encrypted_in_transit:
                exposed.append(flow.id)
                details.append(f"高敏/重要数据流 '{flow.id}' 未启用传输加密")
        for store in model.stores:
            has_high_sens = any(
                assets[aid].is_sensitive_any or assets[aid].is_important_or_core
                for aid in store.data
            )
            if has_high_sens and (not store.encrypted_at_rest and not store.access_control):
                exposed.append(store.id)
                details.append(f"高敏/重要数据存储 '{store.id}' 同时缺失静态加密与访问控制")
        if exposed:
            return True, "；".join(details) + "。", sorted(set(exposed))
        return False, "", []

    if condition_key == "high_impact_adm_without_human_oversight":
        bad_procs = [
            p.id
            for p in model.processes
            if ProcessingOperation.AUTOMATED_DECISION_MAKING in p.operations
            and p.prevents_rights_or_service
            and not p.human_review_available
        ]
        if bad_procs:
            return (
                True,
                f"处理节点 {bad_procs} 执行涉重大权益/拒绝服务的纯自动化决策，但未提供人工复核与申诉机制（human_review_available=false）。",
                bad_procs,
            )
        return False, "", []

    return False, "", []


def evaluate_red_lines(model: DataFlowModel, bundle: RulePackBundle) -> list[RedLineViolation]:
    """Evaluate all zero-tolerance statutory red lines (RL-01..RL-05)."""
    violations: list[RedLineViolation] = []
    active_jurisdictions = set(model.metadata.jurisdictions)

    for rl in bundle.red_lines.red_lines:
        # RL-01 applies whenever EU_AI_ACT is in jurisdictions OR prohibited_practices is explicitly set
        if rl.condition_key != "ai_prohibited_practice" and not (
            active_jurisdictions & set(rl.jurisdictions)
        ):
            continue
        hit, reason, evidence = _evaluate_red_line_condition(rl.condition_key, model)
        if hit:
            violations.append(
                RedLineViolation(
                    red_line_id=rl.id,
                    rule_id=rl.rule_id,
                    title=rl.title,
                    legal_reference="; ".join(rl.legal_references),
                    reason=reason,
                    evidence_elements=evidence,
                )
            )
    return violations


def _evaluate_threshold_condition(
    condition_key: str,
    model: DataFlowModel,
) -> tuple[bool, str, list[str]]:
    """Evaluate a single statutory DPIA/PIA/FRIA/Important-Data trigger criterion."""
    assets = model.data_asset_map()

    if condition_key == "process_has_profiling_or_scoring":
        hits = [
            p.id
            for p in model.processes
            if ProcessingOperation.PROFILING in p.operations
            or ProcessingOperation.SCORING in p.operations
        ]
        return (
            bool(hits),
            f"处理节点 {hits} 执行用户画像（profiling）或信用/风险打分（scoring）。",
            hits,
        )

    if condition_key == "process_high_impact_adm":
        hits = [
            p.id
            for p in model.processes
            if ProcessingOperation.AUTOMATED_DECISION_MAKING in p.operations
            and p.prevents_rights_or_service
        ]
        return (
            bool(hits),
            f"处理节点 {hits} 执行具有法律或重大影响的自动化决策。",
            hits,
        )

    if condition_key == "process_has_systematic_monitoring":
        hits = [
            p.id
            for p in model.processes
            if ProcessingOperation.SYSTEMATIC_MONITORING in p.operations
        ]
        return (bool(hits), f"处理节点 {hits} 执行系统性监控。", hits)

    if condition_key == "asset_sensitive_gdpr":
        hits = [a.id for a in model.data_assets if a.is_sensitive_for(Jurisdiction.GDPR)]
        return (
            bool(hits),
            f"数据资产 {hits} 属于 GDPR Art. 9/10 特殊类别或高度敏感个人数据。",
            hits,
        )

    if condition_key == "scale_is_large":
        if model.metadata.scale == ProcessingScale.LARGE:
            cnt = model.metadata.estimated_subjects
            suffix = f"（预估主体数：{cnt:,}）" if cnt is not None else ""
            return (True, f"系统处理规模为大规模（large）{suffix}。", ["metadata.scale"])
        return False, "", []

    if condition_key == "process_has_dataset_matching":
        hits = [
            p.id
            for p in model.processes
            if ProcessingOperation.DATASET_MATCHING in p.operations
        ]
        return (bool(hits), f"处理节点 {hits} 执行跨数据集匹配或融合。", hits)

    if condition_key == "subjects_include_vulnerable":
        if model.metadata.has_vulnerable_subjects:
            return (
                True,
                f"涉及弱势数据主体：{[s.value for s in model.metadata.data_subjects]}。",
                ["metadata.data_subjects"],
            )
        return False, "", []

    if condition_key == "process_uses_innovative_tech":
        hits = [
            p.id
            for p in model.processes
            if p.innovative_technology
            or ProcessingOperation.AI_TRAINING in p.operations
            or ProcessingOperation.BIOMETRIC_IDENTIFICATION in p.operations
        ]
        return (
            bool(hits),
            f"处理节点 {hits} 应用了创新技术（如生物识别、AI 训练或新兴算法）。",
            hits,
        )

    if condition_key == "process_prevents_rights_or_service":
        hits = [p.id for p in model.processes if p.prevents_rights_or_service]
        return (
            bool(hits),
            f"处理节点 {hits} 的结果可导致拒绝服务、合同或重大个人权益受限。",
            hits,
        )

    if condition_key == "asset_sensitive_pipl":
        hits = [a.id for a in model.data_assets if a.is_sensitive_for(Jurisdiction.PIPL)]
        return (
            bool(hits),
            f"数据资产 {hits} 属于中国 PIPL 第 28 条定义的敏感个人信息。",
            hits,
        )

    if condition_key == "process_has_adm_or_profiling":
        hits = [
            p.id
            for p in model.processes
            if ProcessingOperation.AUTOMATED_DECISION_MAKING in p.operations
            or ProcessingOperation.PROFILING in p.operations
        ]
        return (
            bool(hits),
            f"处理节点 {hits} 利用个人信息开展自动化决策或画像。",
            hits,
        )

    if condition_key == "has_third_party_or_public_disclosure":
        tp_flows = [f.id for f in model.get_third_party_flows()]
        pub_procs = [
            p.id
            for p in model.processes
            if ProcessingOperation.PUBLIC_DISCLOSURE in p.operations
        ]
        hits = tp_flows + pub_procs
        return (
            bool(hits),
            f"存在委托处理、向第三方提供或公开个人信息的情形（{hits}）。",
            hits,
        )

    if condition_key == "has_cross_border_personal_flow":
        hits = [
            f.id
            for f in model.get_cross_border_flows()
            if any(assets[aid].is_personal_data for aid in f.data)
        ]
        return (
            bool(hits),
            f"存在向境外提供个人信息的跨境数据流：{hits}。",
            hits,
        )

    if condition_key == "ai_prohibited_practice":
        return _evaluate_red_line_condition("ai_prohibited_practice", model)

    if condition_key == "ai_high_risk_or_biometric_credit":
        ai = model.metadata.ai_system
        if ai and ai.risk_tier == AIRiskTier.HIGH_RISK:
            return (
                True,
                "系统声明为 EU AI Act 高风险 AI（high_risk），强制触发基本权利影响评估（FRIA）。",
                ["metadata.ai_system"],
            )
        hits = [
            p.id
            for p in model.processes
            if ProcessingOperation.BIOMETRIC_IDENTIFICATION in p.operations
            or (
                ProcessingOperation.SCORING in p.operations
                and p.prevents_rights_or_service
            )
        ]
        if hits:
            return (
                True,
                f"处理节点 {hits} 涉及远程生物识别或影响服务准入的信用/风险打分（对应 EU AI Act Annex III 高风险场景）。",
                hits,
            )
        return False, "", []

    if condition_key == "ai_missing_transparency_notice":
        ai = model.metadata.ai_system
        if ai and ai.is_ai_system and not ai.transparency_notice:
            return (
                True,
                "系统已声明为 AI 系统，但未开启 AI 交互/生成透明告知（transparency_notice=false）。",
                ["metadata.ai_system"],
            )
        return False, "", []

    if condition_key == "has_important_or_core_data":
        hits = [a.id for a in model.data_assets if a.is_important_or_core]
        return (
            bool(hits),
            f"数据资产 {hits} 属于中国 DSL/GB/T 43697 定义的重要数据或核心数据，须开展年度风险评估。",
            hits,
        )

    if condition_key == "is_ciio_with_cross_border_or_change":
        if model.metadata.is_ciio:
            cb = [f.id for f in model.get_cross_border_flows()]
            evidence = cb if cb else ["metadata.is_ciio"]
            return (
                True,
                "运营者属于关键信息基础设施运营者（CIIO），须履行境内存储、年度测评及出境安全评估义务。",
                evidence,
            )
        return False, "", []

    if condition_key == "subjects_exceed_10m":
        cnt = model.metadata.estimated_subjects
        if cnt is not None and cnt >= 10_000_000:
            return (
                True,
                f"预估受影响自然人达 {cnt:,} 人（≥ 1000 万），触发《网络数据安全管理条例》第 28 条参照重要数据处理者保护义务。",
                ["metadata.estimated_subjects"],
            )
        return False, "", []

    return False, "", []


def _evaluate_cross_jurisdiction_conflicts(
    model: DataFlowModel,
    bundle: RulePackBundle,
) -> list[str]:
    """Detect legal conflicts when multiple jurisdictions apply concurrently."""
    conflicts: list[str] = []
    active = set(model.metadata.jurisdictions)

    for rule in bundle.thresholds.cross_jurisdiction_conflicts:
        if not set(rule.jurisdictions).issubset(active):
            continue
        if rule.condition_key == "pipl_uses_legitimate_interests":
            bad = [
                p.id
                for p in model.processes
                if p.lawful_basis == LawfulBasis.LEGITIMATE_INTERESTS
            ]
            if bad:
                conflicts.append(
                    f"[{rule.conflict_id}] 处理节点 {bad} 使用了 `legitimate_interests`（合法利益），"
                    "该基础在 GDPR 下有效但在中国 PIPL 第 13 条下不存在，请为中国业务切换法定基础。"
                )
        elif rule.condition_key == "pipl_only_sensitive_category_present":
            pipl_only = [
                a.id
                for a in model.data_assets
                if a.is_sensitive_for(Jurisdiction.PIPL)
                and not a.is_sensitive_for(Jurisdiction.GDPR)
            ]
            if pipl_only:
                conflicts.append(
                    f"[{rule.conflict_id}] 资产 {pipl_only} 在 GDPR Art. 9 中非特殊类别，"
                    "但在中国 PIPL 第 28 条下属于敏感个人信息（须单独同意并触发强制 PIA）。"
                )
    return conflicts


def evaluate_thresholds(model: DataFlowModel, bundle: RulePackBundle) -> ThresholdAssessment:
    """Evaluate all applicable regulatory frameworks and return `ThresholdAssessment`."""
    results: list[JurisdictionThresholdResult] = []
    any_dpia_required = False
    fria_required = False
    important_data_required = False

    # Evaluate declared jurisdictions; also auto-evaluate EU_AI_ACT if ai_system is declared,
    # and CN_DSL_NDSR if is_ciio or important/core data or >=10M subjects is declared.
    jurisdictions_to_check: list[Jurisdiction] = list(model.metadata.jurisdictions)
    if (
        model.metadata.ai_system is not None
        and Jurisdiction.EU_AI_ACT not in jurisdictions_to_check
    ):
        jurisdictions_to_check.append(Jurisdiction.EU_AI_ACT)
    if (
        (
            model.metadata.is_ciio
            or model.has_important_or_core_data
            or (model.metadata.estimated_subjects or 0) >= 10_000_000
        )
        and Jurisdiction.CN_DSL_NDSR not in jurisdictions_to_check
    ):
        jurisdictions_to_check.append(Jurisdiction.CN_DSL_NDSR)

    for jurisdiction in jurisdictions_to_check:
        j_pack = bundle.thresholds.jurisdiction_rules.get(jurisdiction)
        if j_pack is None:
            continue

        triggered: list[TriggeredCriterion] = []
        for criterion in j_pack.criteria:
            hit, reason, evidence = _evaluate_threshold_condition(criterion.condition_key, model)
            if hit:
                triggered.append(
                    TriggeredCriterion(
                        rule_id=criterion.rule_id,
                        jurisdiction=jurisdiction,
                        title=criterion.title,
                        legal_reference=criterion.legal_reference,
                        reason=reason,
                        evidence_elements=evidence,
                    )
                )

        required = len(triggered) >= j_pack.dpia_trigger_min_criteria
        if jurisdiction in (Jurisdiction.GDPR, Jurisdiction.PIPL) and required:
            any_dpia_required = True
        if jurisdiction == Jurisdiction.EU_AI_ACT:
            ai_decl = model.metadata.ai_system
            if ai_decl and ai_decl.fria_required_override is not None:
                fria_required = ai_decl.fria_required_override
            elif any(c.rule_id == "AIA-ART06-HRAI" for c in triggered):
                fria_required = True
                any_dpia_required = True
        if jurisdiction == Jurisdiction.CN_DSL_NDSR and required:
            important_data_required = True
            any_dpia_required = True

        summary = (
            f"命中 {len(triggered)} 项标准（阈值 ≥ {j_pack.dpia_trigger_min_criteria}），强制触发合规影响评估。"
            if required
            else f"命中 {len(triggered)} 项标准（低于强制阈值 {j_pack.dpia_trigger_min_criteria}），无需强制评估。"
        )
        results.append(
            JurisdictionThresholdResult(
                jurisdiction=jurisdiction,
                dpia_required=required,
                summary=summary,
                triggered_criteria=triggered,
            )
        )

    conflicts = _evaluate_cross_jurisdiction_conflicts(model, bundle)
    return ThresholdAssessment(
        dpia_required=any_dpia_required,
        fria_required=fria_required,
        important_data_assessment_required=important_data_required,
        jurisdiction_conflicts=conflicts,
        results=results,
    )
