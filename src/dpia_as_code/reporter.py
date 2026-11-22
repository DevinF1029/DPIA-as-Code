"""Audit-grade Chinese Markdown report, PR comment, and JSON renderers."""

from __future__ import annotations

from datetime import timedelta

from jinja2 import Environment

from dpia_as_code.models import (
    AssessmentReport,
    DataFlowModel,
    HumanReviewSheet,
    Jurisdiction,
    PETType,
    RemediationItem,
    RiskLevel,
    SignOffEntry,
)

_PET_DEFAULT_CONTROL: dict[PETType, str] = {
    PETType.PURPOSE_LIMITATION: "PC-GOV-01",
    PETType.CONSENT_MANAGEMENT: "PC-GOV-02",
    PETType.PRIVACY_NOTICE_TRANSPARENCY: "PC-GOV-03",
    PETType.DATA_MINIMIZATION: "PC-DAT-01",
    PETType.RETENTION_ENFORCEMENT: "PC-DAT-03",
    PETType.DATA_MASKING: "PC-DAT-04",
    PETType.ENCRYPTION_IN_TRANSIT: "PC-ENC-01",
    PETType.ENCRYPTION_AT_REST: "PC-ENC-02",
    PETType.PSEUDONYMIZATION: "PC-ENC-03",
    PETType.ANONYMIZATION: "PC-ENC-04",
    PETType.DIFFERENTIAL_PRIVACY: "PC-ENC-05",
    PETType.FEDERATED_LEARNING: "PC-ENC-06",
    PETType.ZERO_KNOWLEDGE_PROOF: "PC-ENC-06",
    PETType.ACCESS_CONTROL_RBAC: "PC-ACC-01",
    PETType.AUDIT_LOGGING: "PC-ACC-02",
    PETType.HUMAN_IN_THE_LOOP: "PC-AI-01",
    PETType.SCC_TRANSFER_MECHANISM: "PC-XBD-01",
    PETType.PIPL_SECURITY_ASSESSMENT: "PC-XBD-02",
    PETType.PIPL_STANDARD_CONTRACT: "PC-XBD-02",
    PETType.DPA_CONTRACT: "PC-XBD-03",
    PETType.SECURITY_AUDIT: "PC-GOV-05",
}


def build_default_remediations(report: AssessmentReport) -> list[RemediationItem]:
    """Generate initial RemediationItem rows from Medium/High/Critical residual findings."""
    items: list[RemediationItem] = []
    idx = 0
    for finding in report.findings:
        if finding.residual_risk.level == RiskLevel.LOW:
            continue
        idx += 1
        first_pet = finding.recommended_pets[0] if finding.recommended_pets else None
        ctrl_id = _PET_DEFAULT_CONTROL.get(first_pet, "") if first_pet else ""
        sla_days = (
            14
            if finding.residual_risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            else 30
        )
        due = (report.generated_at.date() + timedelta(days=sla_days)).isoformat()
        items.append(
            RemediationItem(
                rem_id=f"REM-{idx:02d}",
                finding_id=finding.finding_id,
                control_id=ctrl_id,
                action=f"针对 {finding.element_name}（{finding.title}）落实缓解控制并补充审计证据",
                owner="",
                due_date=due,
                evidence="",
                status="Open",
            )
        )
    return items


def build_default_signoffs(model: DataFlowModel) -> list[SignOffEntry]:
    """Build the standard 3-role sign-off rows pre-populated with `dpo_signoff` if present."""
    dpo = model.metadata.dpo_signoff
    return [
        SignOffEntry(role="业务负责人 (BO)", decision="待确认"),
        SignOffEntry(role="隐私工程 / 安全 (2LoD)", decision="待技术验证"),
        SignOffEntry(
            role="数据保护官 (DPO)",
            name=dpo.reviewer if (dpo and dpo.reviewer) else "",
            decision="已签批" if (dpo and dpo.approved) else "待审批",
            comments=dpo.ticket if (dpo and dpo.ticket) else "",
            signed_date=dpo.reviewed_at.isoformat() if (dpo and dpo.reviewed_at) else "",
        ),
    ]


_AUDIT_REPORT_TEMPLATE = """# 综合隐私、数据安全与 AI 影响评估报告（Unified DPIA / PIA / FRIA Report）

> **模板对标**：`TPL-DPIA-001` ｜ **评估编号**：`{{ assessment_id }}` ｜ **生成时间**：`{{ generated_at }}`
> **法定归档提示**：本报告及支撑证据须保存至少 **3 年**（重要数据及涉监管报送项目不少于 5 年）。

---

## 一、 评估基本档案（Executive Summary）

| 评估属性 | 评估内容 |
| :--- | :--- |
| **系统 / 功能名称** | {{ model.metadata.name }} (`{{ model.metadata.system_id }}`) |
| **数据控制者 / 处理者** | {{ model.metadata.controller }} |
| **业务负责人 (BO)** | {{ review.business_owner or '待填写' }} |
| **行业板块 / CIIO 标识** | `{{ model.metadata.industry_sector.value }}` ｜ CIIO：`{{ "是" if model.metadata.is_ciio else "否" }}` |
| **适用法域** | {{ jurisdictions_str }} |
| **触发评估类型** | DPIA/PIA：`{{ "强制触发" if report.threshold.dpia_required else "未触发" }}` ｜ FRIA：`{{ "强制触发" if report.threshold.fria_required else "未触发" }}` ｜ 重要数据评估：`{{ "强制触发" if report.threshold.important_data_assessment_required else "未触发" }}` |
| **DPO / 合规联络人** | `{{ model.metadata.dpo_contact }}` |
| **固有最高风险 → 残余最高风险** | `{{ report.risk_summary.overall_inherent_level.value.upper() }} ({{ report.risk_summary.max_inherent_score }})` → `{{ report.risk_summary.overall_residual_level.value.upper() }} ({{ report.risk_summary.max_residual_score }})` |
| **CI/CD 门禁结论** | **{{ gate_badge }}** (Exit Code: `{{ report.gate.exit_code }}`) |
| **建议下次复评日期** | `{{ next_review_date }}` |

### 门禁决策说明
{% for reason in report.gate.reasons %}
* {{ reason }}
{% endfor %}

---

## 二、 架构数据流图与处理活动记录（DFD & RoPA）

### 2.1 数据流向图（Mermaid DFD）

```mermaid
{{ report.mermaid_dfd }}
```
{% if report.topology_warnings %}

> **架构建模提示**：
{% for warn in report.topology_warnings %}
> * {{ warn }}
{% endfor %}
{% endif %}

### 2.2 数据分类分级与敏感资产清单

| 资产 ID | 资产名称 | 数据类别 | 分类分级 (GB/T 43697) | 金融分级 (JR/T 0197) | 可识别度 | GDPR 特殊 | PIPL 敏感 |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
{% for asset in model.data_assets %}
| `{{ asset.id }}` | {{ asset.name }} | {{ asset.categories | map(attribute='value') | join(', ') }} | `{{ asset.data_classification.value }}` | {{ asset.financial_data_level.value if asset.financial_data_level else '-' }} | `{{ asset.identifiability.value }}` | {{ "是" if asset.is_sensitive_for(GDPR) else "否" }} | {{ "是" if asset.is_sensitive_for(PIPL) else "否" }} |
{% endfor %}

### 2.3 处理活动记录草案（RoPA 摘要）

| 处理节点 | 处理目的 | 合法性基础 | 涉及主体 | 第三方接收方 / 跨境路径 | 留存期限 | 已生效控制 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{% for row in report.ropa %}
| {{ row.process_name }} (`{{ row.process_id }}`) | {{ row.purposes | join('; ') }} | `{{ row.lawful_basis.value }}` | {{ row.data_subjects | join(', ') }} | {{ (row.recipients + row.cross_border_transfers) | join('; ') or '无' }} | {{ row.retention_policies | join('; ') or '未关联存储' }} | {{ row.security_measures | join('; ') or '无' }} |
{% endfor %}

---

## 三、 法定红线校验与多法域强制评估触发判定

### 3.1 法定红线（Zero-Tolerance）校验结果
{% if not report.gate.red_line_violations %}
* [x] 未命中任何法定红线（`RL-01` 至 `RL-05`）
{% else %}
* [x] **命中法定红线（强制阻断、禁止豁免）**：
{% for rl in report.gate.red_line_violations %}
  * **`{{ rl.red_line_id.value }}` (`{{ rl.rule_id }}`) — {{ rl.title }}**：{{ rl.reason }}（依据：`{{ rl.legal_reference }}`，涉及元素：`{{ rl.evidence_elements | join(', ') }}`）
{% endfor %}
{% endif %}

### 3.2 法定触发阈值判定明细

| 法域 | 是否强制触发 | 判定摘要 | 命中的规则 ID 与涉及元素 |
| :--- | :---: | :--- | :--- |
{% for res in report.threshold.results %}
| **{{ res.jurisdiction.value }}** | {{ "是" if res.dpia_required else "否" }} | {{ res.summary }} | {% if res.triggered_criteria %}{% for c in res.triggered_criteria %}`{{ c.rule_id }}` ({{ c.evidence_elements | join(', ') }}){% if not loop.last %}; {% endif %}{% endfor %}{% else %}无{% endif %} |
{% endfor %}
{% if report.threshold.jurisdiction_conflicts %}

### 3.3 跨法域合规冲突提示
{% for conflict in report.threshold.jurisdiction_conflicts %}
* {{ conflict }}
{% endfor %}
{% endif %}

---

## 四、 合法性、必要性与比例性实质审查（DPO 人工审查章节）

> **说明**：自动化引擎已完成客观事实核验与阈值判定，以下实质裁量由业务负责人起草并经 DPO 复核确认。

1. **合法性基础适格性论证**：{{ review.lawful_basis_rationale or '<请确认所选合法性基础覆盖所有适用法域，且未在中国业务中误用 GDPR 合法利益>' }}
2. **最小必要与比例性论证**：{{ review.necessity_proportionality or '<请论证采集敏感字段/生物识别/金融数据的不可替代性及已评估的低侵入替代方案>' }}
3. **数据主体权利保障机制**：{{ review.data_subject_rights_sla or '<请说明告知、撤回同意、查询删除、关闭个性化与人工申诉的 SLA 与操作路径>' }}
{% if report.threshold.fria_required or report.threshold.important_data_assessment_required %}

---

## 五、 专项影响评估（按需自动激活）
{% if report.threshold.fria_required %}

### 5.1 EU AI Act 基本权利影响评估（FRIA — Art. 27）
* **AI 风险定级与模型卡片**：`{{ model.metadata.ai_system.risk_tier.value if model.metadata.ai_system else 'inferred_high_risk' }}` / `{{ model.metadata.ai_system.model_card_ref if model.metadata.ai_system and model.metadata.ai_system.model_card_ref else '待补充' }}`
* **受影响群体与部署频次**：{{ review.fria_affected_groups or '<请说明受影响的自然人群体范围、弱势群体排查与调用频次>' }}
* **平等权与非歧视风险评估**：{{ review.fria_fairness_bias or '<请补充训练数据代表性、群体误拒率偏差测试结论>' }}
* **人工监督落地措施（Art. 14）**：{{ review.fria_human_oversight or '<请补充操作员复核 SOP 与一键中止 Kill-Switch 演练记录>' }}
{% endif %}
{% if report.threshold.important_data_assessment_required %}

### 5.2 重要数据 / CIIO 安全评估（DSL Art. 30 / 网数条例 Art. 31）
* **国家安全与公共利益影响评估**：{{ review.important_data_impact or '<请补充重要/核心数据共享与出境影响分析>' }}
* **年度主管部门报送/出境评估回执编号**：{{ review.important_data_filing_ref or '<请填写备案或申报编号>' }}
{% endif %}
{% endif %}

---

## 六、 LINDDUN 隐私威胁建模与量化风险矩阵

### 6.1 威胁评估与控制折减明细

* **发现总数**：`{{ report.risk_summary.total_findings }}`（Critical: `{{ counts.critical }}` ｜ High: `{{ counts.high }}` ｜ Medium: `{{ counts.medium }}` ｜ Low: `{{ counts.low }}`）

{% if report.findings %}
| 发现 ID | 节点 / 流 | LINDDUN 类别 | 固有风险 (L×S) | 已生效控制 | 残余风险 (L×S) | 计划项 / 推荐 PETs |
| :--- | :--- | :--- | :---: | :--- | :---: | :--- |
{% for f in report.findings %}
| `{{ f.finding_id }}` | {{ f.element_name }} (`{{ f.element_id }}`) | `{{ f.category.value }}` | `{{ f.inherent_risk.level.value.upper() }}` ({{ f.inherent_risk.likelihood }}×{{ f.inherent_risk.severity }}={{ f.inherent_risk.score }}) | {{ f.applied_mitigations | join(', ') or '无' }} | **`{{ f.residual_risk.level.value.upper() }}`** ({{ f.residual_risk.likelihood }}×{{ f.residual_risk.severity }}={{ f.residual_risk.score }}) | 计划: {{ f.planned_mitigations | join(', ') or '无' }}；推荐: {{ f.recommended_pets | map(attribute='value') | join(', ') }} |
{% endfor %}
{% else %}
* 当前架构未检出需额外处置的 LINDDUN 隐私威胁。
{% endif %}
{% if remediations %}

### 6.2 整改追踪与行动计划（Remediation Plan）

| 整改编号 | 关联发现 ID | 对应控制编号 | 具体整改动作 | 责任人 | 目标完成日 | 验证证据链接 | 状态 |
| :--- | :--- | :---: | :--- | :--- | :---: | :--- | :---: |
{% for item in remediations %}
| `{{ item.rem_id }}` | `{{ item.finding_id or '-' }}` | `{{ item.control_id or '-' }}` | {{ item.action }} | {{ item.owner or '待指派' }} | `{{ item.due_date or '-' }}` | {{ item.evidence or '-' }} | `{{ item.status }}` |
{% endfor %}
{% endif %}
{% if report.gate.waiver_evaluations %}

### 6.3 限时风险豁免单（Risk Waivers）核验状态

| 豁免单号 | 覆盖发现项 | 状态 | 硬性到期日 | 说明 |
| :--- | :--- | :---: | :---: | :--- |
{% for w in report.gate.waiver_evaluations %}
| `{{ w.waiver_id }}` | {{ w.target_findings | join(', ') }} | `{{ w.status.upper() }}` | `{{ w.expires_at }}` | {{ w.reason or '' }} |
{% endfor %}
{% endif %}

---

## 七、 最终合规意见与签批页（Sign-Off）

| 角色 | 姓名 / 部门 | 审批结论 | 意见与附带条件 | 日期 |
| :--- | :--- | :--- | :--- | :---: |
{% for row in signoffs %}
| **{{ row.role }}** | {{ row.name }} | {{ row.decision }} | {{ row.comments }} | {{ row.signed_date }} |
{% endfor %}
"""

_PR_COMMENT_TEMPLATE = """## DPIA-as-Code 隐私与合规门禁摘要

* **系统**：{{ model.metadata.name }} (`{{ model.metadata.system_id }}`)
* **门禁结论**：**{{ gate_badge }}**（固有最高：`{{ report.risk_summary.overall_inherent_level.value.upper() }} {{ report.risk_summary.max_inherent_score }}` → 残余最高：`{{ report.risk_summary.overall_residual_level.value.upper() }} {{ report.risk_summary.max_residual_score }}`）
* **强制评估触发**：DPIA/PIA=`{{ "是" if report.threshold.dpia_required else "否" }}` ｜ FRIA=`{{ "是" if report.threshold.fria_required else "否" }}` ｜ 重要数据=`{{ "是" if report.threshold.important_data_assessment_required else "否" }}`
* **威胁统计**：总计 `{{ report.risk_summary.total_findings }}` 项（Critical: `{{ counts.critical }}` / High: `{{ counts.high }}` / Medium: `{{ counts.medium }}` / Low: `{{ counts.low }}`）

### 关键阻断 / 提示原因
{% for reason in report.gate.reasons %}
* {{ reason }}
{% endfor %}
"""


def _gate_badge(status: str) -> str:
    return {
        "pass": "PASS（自动放行）",
        "warn": "WARN（警示放行）",
        "block": "BLOCK（阻断合并）",
    }.get(status, status.upper())


def _build_context(
    model: DataFlowModel,
    report: AssessmentReport,
    review: HumanReviewSheet | None = None,
) -> dict:
    review_days = 180 if report.risk_summary.overall_residual_level == RiskLevel.MEDIUM else 365
    if report.risk_summary.overall_residual_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        review_days = 90
    next_review = (report.generated_at.date() + timedelta(days=review_days)).isoformat()
    counts = {
        "critical": report.risk_summary.residual_counts[RiskLevel.CRITICAL],
        "high": report.risk_summary.residual_counts[RiskLevel.HIGH],
        "medium": report.risk_summary.residual_counts[RiskLevel.MEDIUM],
        "low": report.risk_summary.residual_counts[RiskLevel.LOW],
    }
    sheet = review or HumanReviewSheet()
    assessment_id = (
        sheet.assessment_id
        or f"DPIA-{report.generated_at.strftime('%Y%m%d')}-{model.metadata.system_id[:16].upper()}"
    )
    remediations = sheet.remediations if sheet.remediations else build_default_remediations(report)
    signoffs = sheet.signoffs if sheet.signoffs else build_default_signoffs(model)
    return {
        "model": model,
        "report": report,
        "review": sheet,
        "assessment_id": assessment_id,
        "remediations": remediations,
        "signoffs": signoffs,
        "generated_at": report.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "jurisdictions_str": ", ".join(j.value for j in model.metadata.jurisdictions),
        "gate_badge": _gate_badge(report.gate.status),
        "next_review_date": next_review,
        "counts": counts,
        "GDPR": Jurisdiction.GDPR,
        "PIPL": Jurisdiction.PIPL,
    }


def render_markdown_report(
    model: DataFlowModel,
    report: AssessmentReport,
    review: HumanReviewSheet | None = None,
) -> str:
    """Render the full audit-grade Chinese Markdown DPIA/PIA/FRIA report."""
    env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(_AUDIT_REPORT_TEMPLATE)
    return template.render(**_build_context(model, report, review=review)).strip() + "\n"


def render_pr_comment(model: DataFlowModel, report: AssessmentReport) -> str:
    """Render a compact Markdown summary designed for GitHub Actions PR comments."""
    env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(_PR_COMMENT_TEMPLATE)
    return template.render(**_build_context(model, report)).strip() + "\n"


def render_json_report(report: AssessmentReport) -> str:
    """Serialize `AssessmentReport` as formatted JSON."""
    return report.model_dump_json(indent=2) + "\n"
