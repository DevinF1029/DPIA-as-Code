"""FastAPI backend for the DPIA-as-Code Governance Workbench (interactive web UI).

The web layer is intentionally thin: it only exposes the existing, fully-tested
engines (`assess_dataflow`, renderers, rule bundle) over a small REST API so that
non-programmers (Business Owners, Legal, DPO, Auditors) can build `dataflow.yaml`
visually, run what-if simulations, and export audit reports.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ValidationError

from dpia_as_code.engines import assess_dataflow
from dpia_as_code.models import (
    AIRiskTier,
    DataCategory,
    DataClassification,
    DataFlowModel,
    DataSubjectCategory,
    EntityRole,
    FinancialDataLevel,
    IdentifiabilityLevel,
    IndustrySector,
    Jurisdiction,
    LawfulBasis,
    LINDDUNCategory,
    MitigationStatus,
    PETType,
    ProcessingOperation,
    ProhibitedAIPractice,
    RiskLevel,
    TransferMechanism,
)
from dpia_as_code.reporter import render_markdown_report, render_pr_comment
from dpia_as_code.rules_loader import RulePackBundle, load_rule_bundle

STATIC_DIR = Path(__file__).resolve().parent / "static"
REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples"

# ----------------------------------------------------------------------
# Chinese display labels for non-programmer friendly dropdowns
# ----------------------------------------------------------------------

_LABELS: dict[str, dict[str, str]] = {
    "Jurisdiction": {
        "GDPR": "欧盟 GDPR",
        "PIPL": "中国 个人信息保护法",
        "EU_AI_ACT": "欧盟 人工智能法案",
        "CN_DSL_NDSR": "中国 数安法/网数条例/关保",
        "CN_FIN_NFRA": "中国 金融监管（预留）",
    },
    "IndustrySector": {
        "general": "通用行业",
        "banking": "商业银行",
        "insurance": "保险业",
        "fintech": "金融科技",
        "healthcare": "医疗健康",
        "other": "其他",
    },
    "DataClassification": {"general": "一般数据", "important": "重要数据", "core": "核心数据"},
    "FinancialDataLevel": {
        "L1": "L1 公开",
        "L2": "L2 内部",
        "L3": "L3 敏感",
        "L4": "L4 高敏",
        "L5": "L5 极敏",
    },
    "AIRiskTier": {
        "none": "非 AI 系统",
        "minimal": "最小风险",
        "limited": "有限风险（透明义务）",
        "high_risk": "高风险（触发 FRIA）",
        "prohibited": "禁止类（红线）",
    },
    "ProhibitedAIPractice": {
        "social_scoring": "社会信用评分",
        "untargeted_facial_scraping": "无差别抓取人脸建库",
        "workplace_education_emotion_recognition": "职场/教育情绪识别",
        "subliminal_manipulation": "潜意识操纵",
        "biometric_sensitive_inference": "生物特征推断敏感属性",
        "realtime_remote_biometric_public": "公共场所实时远程生物识别",
    },
    "DataCategory": {
        "non_personal": "非个人数据",
        "basic_identity": "基本身份信息",
        "contact_info": "联系方式",
        "device_identifier": "设备标识符",
        "online_behavior": "上网行为/偏好",
        "employment_info": "雇佣/人事信息",
        "government_id": "身份证件号码",
        "biometric": "生物识别",
        "health_medical": "医疗健康",
        "genetic": "基因数据",
        "financial_account": "金融账户/征信",
        "precise_location": "精准位置/行踪轨迹",
        "religious_political": "宗教/政治观点",
        "sexual_orientation": "性取向",
        "criminal_record": "犯罪记录",
        "minor_under_14": "不满 14 周岁未成年人",
        "minor_under_16": "不满 16 周岁未成年人",
    },
    "IdentifiabilityLevel": {
        "directly_identifiable": "可直接识别",
        "pseudonymized": "假名化",
        "aggregated": "聚合统计",
        "anonymized": "匿名化",
    },
    "DataSubjectCategory": {
        "customers": "客户",
        "website_visitors": "网站访客",
        "employees": "员工",
        "minors": "未成年人",
        "patients": "患者",
        "elderly": "老年人",
        "vulnerable_groups": "其他弱势群体",
        "business_contacts": "商务联系人",
    },
    "LawfulBasis": {
        "consent": "同意",
        "separate_consent": "单独同意（PIPL）",
        "contract": "订立/履行合同所必需",
        "legal_obligation": "法定义务",
        "vital_interests": "重大利益/紧急情况",
        "public_task": "公共职责",
        "legitimate_interests": "合法利益（仅 GDPR）",
        "hr_management": "人力资源管理（PIPL）",
        "publicly_available": "已合法公开信息（PIPL）",
        "unspecified": "未声明（红线）",
    },
    "EntityRole": {
        "data_subject": "数据主体（用户）",
        "internal_user": "内部用户/操作员",
        "processor": "受托处理者",
        "third_party_controller": "第三方独立处理者",
        "joint_controller": "共同处理者",
        "public_authority": "公共机关/监管",
    },
    "ProcessingOperation": {
        "collection": "收集",
        "storage": "存储",
        "profiling": "用户画像",
        "scoring": "打分/评分",
        "automated_decision_making": "自动化决策",
        "systematic_monitoring": "系统性监控",
        "dataset_matching": "数据集匹配融合",
        "ai_training": "AI 模型训练",
        "biometric_identification": "生物识别核验",
        "public_disclosure": "公开披露",
        "analytics": "统计分析",
        "archival": "归档",
        "deletion": "删除",
    },
    "PETType": {
        "encryption_in_transit": "传输加密",
        "encryption_at_rest": "静态加密",
        "pseudonymization": "假名化",
        "anonymization": "匿名化",
        "differential_privacy": "差分隐私",
        "data_minimization": "数据最小化",
        "access_control_rbac": "访问控制 RBAC",
        "purpose_limitation": "目的限定",
        "consent_management": "同意管理",
        "privacy_notice_transparency": "透明告知",
        "human_in_the_loop": "人工复核",
        "retention_enforcement": "留存期限清理",
        "federated_learning": "联邦学习",
        "zero_knowledge_proof": "零知识证明",
        "data_masking": "脱敏掩码",
        "audit_logging": "审计日志",
        "dpa_contract": "数据处理协议 DPA",
        "scc_transfer_mechanism": "欧盟 SCC",
        "pipl_security_assessment": "出境安全评估",
        "pipl_standard_contract": "出境标准合同",
        "security_audit": "安全/合规审计",
        "other": "其他",
    },
    "MitigationStatus": {
        "planned": "计划中（不降分）",
        "implemented": "已落地（降 1 档）",
        "verified": "已验证（完全折减）",
    },
    "TransferMechanism": {
        "none": "未配置（红线）",
        "adequacy_decision": "欧盟充分性认定",
        "scc": "欧盟标准合同 SCC",
        "bcr": "约束性公司规则 BCR",
        "pipl_security_assessment": "网信办出境安全评估",
        "pipl_standard_contract": "个人信息出境标准合同",
        "pipl_certification": "个人信息保护认证",
        "pipl_exemption": "跨境新规法定豁免",
        "explicit_consent_derogation": "明确同意例外（GDPR）",
    },
    "LINDDUNCategory": {
        "linkability": "可链接性 L",
        "identifiability": "可识别性 I",
        "non_repudiation": "不可否认性 N",
        "detectability": "可探测性 D",
        "disclosure": "信息泄露 D",
        "unawareness": "不知情/不可干预 U",
        "non_compliance": "不合规 N",
    },
    "RiskLevel": {"low": "低", "medium": "中", "high": "高", "critical": "极高"},
}

_CONTROL_NAMES_ZH: dict[str, str] = {
    "PC-GOV-01": "合法性基础与目的限定",
    "PC-GOV-02": "同意与敏感信息单独同意管理",
    "PC-GOV-03": "隐私与 AI 交互透明告知",
    "PC-GOV-04": "处理活动记录与 3 年合规归档",
    "PC-GOV-05": "独立审计与监管事前咨询升级",
    "PC-GOV-06": "重要数据/CIIO/超千万人年度评估与报送",
    "PC-DAT-01": "源头数据最小化采集",
    "PC-DAT-02": "数据分类分级与重要数据打标",
    "PC-DAT-03": "留存期限硬性自动清理",
    "PC-DAT-04": "前端/日志动态脱敏与掩码",
    "PC-ENC-01": "传输层强加密（TLS/mTLS）",
    "PC-ENC-02": "静态存储加密与密钥分离（AES/SM4）",
    "PC-ENC-03": "强假名化与映射表隔离",
    "PC-ENC-04": "不可逆匿名化",
    "PC-ENC-05": "差分隐私",
    "PC-ENC-06": "联邦学习 / 零知识证明",
    "PC-ACC-01": "最小权限与角色访问控制",
    "PC-ACC-02": "防篡改访问审计日志（≥6 个月）",
    "PC-AI-01": "人工监督、申诉与一键中止",
    "PC-AI-02": "个性化关闭与算法可解释性",
    "PC-AI-03": "高风险 AI 风险管理与红队测试",
    "PC-AI-04": "训练数据合法性与偏差审计",
    "PC-XBD-01": "欧盟跨境传输机制与 TIA",
    "PC-XBD-02": "中国数据出境法定路径",
    "PC-XBD-03": "第三方 DPA 与供应商尽调",
}

_ENUMS: dict[str, type[StrEnum]] = {
    "Jurisdiction": Jurisdiction,
    "IndustrySector": IndustrySector,
    "DataClassification": DataClassification,
    "FinancialDataLevel": FinancialDataLevel,
    "AIRiskTier": AIRiskTier,
    "ProhibitedAIPractice": ProhibitedAIPractice,
    "DataCategory": DataCategory,
    "IdentifiabilityLevel": IdentifiabilityLevel,
    "DataSubjectCategory": DataSubjectCategory,
    "LawfulBasis": LawfulBasis,
    "EntityRole": EntityRole,
    "ProcessingOperation": ProcessingOperation,
    "PETType": PETType,
    "MitigationStatus": MitigationStatus,
    "TransferMechanism": TransferMechanism,
    "LINDDUNCategory": LINDDUNCategory,
    "RiskLevel": RiskLevel,
}


# ----------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------


class SpecRequest(BaseModel):
    spec: dict[str, Any]
    as_of: date | None = None


class YamlRequest(BaseModel):
    yaml_text: str


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


@lru_cache(maxsize=1)
def _bundle() -> RulePackBundle:
    return load_rule_bundle()


def _format_errors(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) if err["loc"] else "<root>"
        msg = str(err["msg"]).removeprefix("Value error, ")
        errors.append(f"{loc}: {msg}")
    return errors


def _validate_spec(spec: dict[str, Any]) -> DataFlowModel:
    try:
        return DataFlowModel.model_validate(spec)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "架构声明校验未通过", "errors": _format_errors(exc)},
        ) from exc


def _spec_to_ui_json(model: DataFlowModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)


def _list_examples() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not EXAMPLES_DIR.is_dir():
        return items
    for path in sorted(EXAMPLES_DIR.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            title = payload.get("metadata", {}).get("name", path.stem)
        except yaml.YAMLError:
            title = path.stem
        items.append({"id": path.stem, "title": title})
    return items


# ----------------------------------------------------------------------
# Application factory
# ----------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="DPIA-as-Code Governance Workbench",
        description="可视化隐私、数据安全与 AI 合规影响评估工作台 API",
        version="0.2.0",
    )

    @app.exception_handler(HTTPException)
    async def _http_exc_handler(_request, exc: HTTPException) -> JSONResponse:  # noqa: ANN001
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content=detail)

    @app.get("/", include_in_schema=False)
    async def index() -> HTMLResponse:
        return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))

    @app.get("/static/{filename}", include_in_schema=False)
    async def static_asset(filename: str) -> Response:
        path = (STATIC_DIR / filename).resolve()
        if not path.is_file() or path.parent != STATIC_DIR.resolve():
            raise HTTPException(status_code=404, detail={"message": f"静态资源 '{filename}' 不存在"})
        media = "application/javascript; charset=utf-8" if filename.endswith(".js") else "text/css; charset=utf-8"
        return Response(content=path.read_bytes(), media_type=media)

    @app.get("/api/meta")
    async def meta() -> dict[str, Any]:
        """Enum options (with Chinese labels), control catalog, and example list."""
        enums = {
            name: [
                {"value": item.value, "label": _LABELS.get(name, {}).get(item.value, item.value)}
                for item in enum_cls
            ]
            for name, enum_cls in _ENUMS.items()
        }
        controls = [
            {
                "id": c.id,
                "domain": c.domain,
                "name": c.name,
                "name_zh": _CONTROL_NAMES_ZH.get(c.id, c.name),
                "pet_types": [p.value for p in c.pet_types],
                "mitigates_threats": [t.value for t in c.mitigates_threats],
                "reduces_dimensions": list(c.reduces_dimensions),
                "regulations": list(c.regulations),
                "audit_evidence": c.audit_evidence,
            }
            for c in _bundle().control_catalog.controls
        ]
        red_lines = [
            {"id": r.id.value, "title": r.title, "legal_references": r.legal_references}
            for r in _bundle().red_lines.red_lines
        ]
        return {
            "enums": enums,
            "controls": controls,
            "red_lines": red_lines,
            "examples": _list_examples(),
        }

    @app.get("/api/examples/{example_id}")
    async def get_example(example_id: str) -> dict[str, Any]:
        path = EXAMPLES_DIR / f"{example_id}.yaml"
        if not path.is_file() or path.resolve().parent != EXAMPLES_DIR.resolve():
            raise HTTPException(status_code=404, detail={"message": f"示例 '{example_id}' 不存在"})
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return {"spec": _spec_to_ui_json(_validate_spec(payload))}

    @app.post("/api/parse-yaml")
    async def parse_yaml(req: YamlRequest) -> dict[str, Any]:
        try:
            payload = yaml.safe_load(req.yaml_text)
        except yaml.YAMLError as exc:
            raise HTTPException(
                status_code=422, detail={"message": "YAML 语法错误", "errors": [str(exc)]}
            ) from exc
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=422,
                detail={"message": "YAML 根节点必须是映射对象", "errors": ["Root must be a mapping."]},
            )
        return {"spec": _spec_to_ui_json(_validate_spec(payload))}

    @app.post("/api/assess")
    async def assess(req: SpecRequest) -> dict[str, Any]:
        model = _validate_spec(req.spec)
        report = assess_dataflow(model, rule_bundle=_bundle(), as_of=req.as_of)
        return {
            "report": report.model_dump(mode="json"),
            "markdown": render_markdown_report(model, report),
            "pr_comment": render_pr_comment(model, report),
            "topology_warnings": model.topology_warnings(),
        }

    @app.post("/api/export-yaml")
    async def export_yaml(req: SpecRequest) -> dict[str, Any]:
        model = _validate_spec(req.spec)
        body = yaml.safe_dump(req.spec, allow_unicode=True, sort_keys=False, width=100)
        header = (
            "# yaml-language-server: $schema=../schemas/dataflow.schema.json\n"
            "# Generated by DPIA-as-Code Governance Workbench\n"
        )
        return {"yaml_text": header + body, "filename": f"{model.metadata.system_id}.dataflow.yaml"}

    return app


app = create_app()
