"""Core domain enumerations and regulatory taxonomies for DPIA-as-Code.

Aligned with:
- GDPR (EU 2016/679) Art. 6, Art. 9, Art. 10, Art. 30, Art. 35 & WP29/EDPB Guidelines
- EU AI Act (EU 2024/1689) Art. 5, Art. 6/Annex III, Art. 14, Art. 27 (FRIA)
- China "三法两条例": CSL, DSL (Art. 21/30/31), PIPL (Art. 13/28/38/55), CIIO Regs, NDSR (2025)
- GB/T 39335-2020 & GB/T 43697-2024 (Data Classification & Grading)
- Financial Sector Hook: NFRA 《银行保险机构数据安全管理办法》 & JR/T 0197
- LINDDUN Privacy Threat Modeling Framework & CNIL PIA Methodology
"""

from __future__ import annotations

from enum import StrEnum


class Jurisdiction(StrEnum):
    """Supported privacy, data security, and AI regulatory frameworks."""

    GDPR = "GDPR"
    PIPL = "PIPL"
    EU_AI_ACT = "EU_AI_ACT"
    CN_DSL_NDSR = "CN_DSL_NDSR"  # China DSL + CIIO Regs + Network Data Security Regs
    CN_FIN_NFRA = "CN_FIN_NFRA"  # Reserved hook for China Banking/Insurance (NFRA + JR/T 0197)


class IndustrySector(StrEnum):
    """Industry sector tag enabling optional sector-specific GRC rule packs."""

    GENERAL = "general"
    BANKING = "banking"
    INSURANCE = "insurance"
    FINTECH = "fintech"
    HEALTHCARE = "healthcare"
    OTHER = "other"


class DataClassification(StrEnum):
    """China DSL Art. 21 & GB/T 43697-2024 statutory data classification."""

    GENERAL = "general"  # 一般数据
    IMPORTANT = "important"  # 重要数据
    CORE = "core"  # 核心数据


class FinancialDataLevel(StrEnum):
    """Optional JR/T 0197 financial data security grading hook (Level 1 to Level 5)."""

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"


class AIRiskTier(StrEnum):
    """EU AI Act (EU 2024/1689) risk classification tiers."""

    NONE = "none"
    MINIMAL = "minimal"
    LIMITED = "limited"  # Art. 50 transparency obligations
    HIGH_RISK = "high_risk"  # Art. 6 & Annex III (triggers FRIA Art. 27)
    PROHIBITED = "prohibited"  # Art. 5 zero-tolerance red line (RL-01)


class ProhibitedAIPractice(StrEnum):
    """EU AI Act Art. 5 prohibited AI practices (Zero-Tolerance Red Line RL-01)."""

    SOCIAL_SCORING = "social_scoring"
    UNTARGETED_FACIAL_SCRAPING = "untargeted_facial_scraping"
    WORKPLACE_EDUCATION_EMOTION_RECOGNITION = "workplace_education_emotion_recognition"
    SUBLIMINAL_MANIPULATION = "subliminal_manipulation"
    BIOMETRIC_SENSITIVE_INFERENCE = "biometric_sensitive_inference"
    REALTIME_REMOTE_BIOMETRIC_PUBLIC = "realtime_remote_biometric_public"


class RedLineId(StrEnum):
    """Statutory zero-tolerance red lines defined in governance/01_governance_policy.md."""

    RL_01 = "RL-01"  # EU AI Act Art. 5 prohibited AI practices
    RL_02 = "RL-02"  # Unlawful processing / missing sensitive or minor-under-14 prerequisites
    RL_03 = "RL-03"  # Unlawful cross-border transfer of important/CIIO/personal data
    RL_04 = "RL-04"  # Unprotected exposure of sensitive/important data (plaintext/no AC)
    RL_05 = "RL-05"  # High-impact fully automated decision-making without human oversight


class DataCategory(StrEnum):
    """Standardized personal data categories mapped to GDPR Art. 9/10 and PIPL Art. 28."""

    # Non-personal / general personal data
    NON_PERSONAL = "non_personal"
    BASIC_IDENTITY = "basic_identity"  # Name, username, avatar
    CONTACT_INFO = "contact_info"  # Email, phone number, postal address
    DEVICE_IDENTIFIER = "device_identifier"  # IP, cookie ID, IDFA, MAC, device fingerprint
    ONLINE_BEHAVIOR = "online_behavior"  # Browsing history, clickstream, preferences
    EMPLOYMENT_INFO = "employment_info"  # Job title, payroll, HR records
    GOVERNMENT_ID = "government_id"  # National ID, passport, driver's license

    # Sensitive / special categories (GDPR Art. 9/10 and/or PIPL Art. 28)
    BIOMETRIC = "biometric"  # Faceprint, fingerprint, voiceprint, iris
    HEALTH_MEDICAL = "health_medical"  # Medical records, physiological metrics
    GENETIC = "genetic"  # DNA / genomic data
    FINANCIAL_ACCOUNT = "financial_account"  # Bank account, credit card, payment/credit score
    PRECISE_LOCATION = "precise_location"  # GPS trajectory, real-time geolocation
    RELIGIOUS_POLITICAL = "religious_political"  # Religious beliefs, political opinions, union
    SEXUAL_ORIENTATION = "sexual_orientation"  # Sex life or sexual orientation
    CRIMINAL_RECORD = "criminal_record"  # Criminal convictions and offences (GDPR Art. 10)
    MINOR_UNDER_14 = "minor_under_14"  # PIPL Art. 28 explicit threshold (< 14 years)
    MINOR_UNDER_16 = "minor_under_16"  # GDPR Art. 8 baseline threshold (< 16 years)


# Statutory sensitivity sets used by the Threshold Engine and Risk Scorer
GDPR_SPECIAL_CATEGORIES: frozenset[DataCategory] = frozenset(
    {
        DataCategory.BIOMETRIC,
        DataCategory.HEALTH_MEDICAL,
        DataCategory.GENETIC,
        DataCategory.RELIGIOUS_POLITICAL,
        DataCategory.SEXUAL_ORIENTATION,
        DataCategory.CRIMINAL_RECORD,
        DataCategory.MINOR_UNDER_14,
        DataCategory.MINOR_UNDER_16,
    }
)

PIPL_SENSITIVE_CATEGORIES: frozenset[DataCategory] = frozenset(
    {
        DataCategory.BIOMETRIC,
        DataCategory.HEALTH_MEDICAL,
        DataCategory.GENETIC,
        DataCategory.FINANCIAL_ACCOUNT,
        DataCategory.PRECISE_LOCATION,
        DataCategory.RELIGIOUS_POLITICAL,
        DataCategory.GOVERNMENT_ID,
        DataCategory.MINOR_UNDER_14,
    }
)


class IdentifiabilityLevel(StrEnum):
    """Degree to which a data asset can identify a natural person."""

    DIRECTLY_IDENTIFIABLE = "directly_identifiable"
    PSEUDONYMIZED = "pseudonymized"
    AGGREGATED = "aggregated"
    ANONYMIZED = "anonymized"


class DataSubjectCategory(StrEnum):
    """Categories of natural persons whose data is processed."""

    CUSTOMERS = "customers"
    WEBSITE_VISITORS = "website_visitors"
    EMPLOYEES = "employees"
    MINORS = "minors"
    PATIENTS = "patients"
    ELDERLY = "elderly"
    VULNERABLE_GROUPS = "vulnerable_groups"
    BUSINESS_CONTACTS = "business_contacts"


VULNERABLE_DATA_SUBJECTS: frozenset[DataSubjectCategory] = frozenset(
    {
        DataSubjectCategory.EMPLOYEES,
        DataSubjectCategory.MINORS,
        DataSubjectCategory.PATIENTS,
        DataSubjectCategory.ELDERLY,
        DataSubjectCategory.VULNERABLE_GROUPS,
    }
)


class LawfulBasis(StrEnum):
    """Legal basis for processing under GDPR Art. 6 and PIPL Art. 13."""

    CONSENT = "consent"
    SEPARATE_CONSENT = "separate_consent"  # PIPL 单独同意 (sensitive/cross-border/third-party)
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_TASK = "public_task"
    LEGITIMATE_INTERESTS = "legitimate_interests"  # GDPR Art. 6(1)(f) only
    HR_MANAGEMENT = "hr_management"  # PIPL Art. 13(2)
    PUBLICLY_AVAILABLE = "publicly_available"  # PIPL Art. 13(6)
    UNSPECIFIED = "unspecified"


class EntityRole(StrEnum):
    """Role of an external entity in the data lifecycle."""

    DATA_SUBJECT = "data_subject"
    INTERNAL_USER = "internal_user"
    PROCESSOR = "processor"  # 受托处理者 / Data Processor
    THIRD_PARTY_CONTROLLER = "third_party_controller"  # 第三方独立处理者
    JOINT_CONTROLLER = "joint_controller"  # 共同处理者
    PUBLIC_AUTHORITY = "public_authority"


THIRD_PARTY_ROLES: frozenset[EntityRole] = frozenset(
    {
        EntityRole.PROCESSOR,
        EntityRole.THIRD_PARTY_CONTROLLER,
        EntityRole.JOINT_CONTROLLER,
        EntityRole.PUBLIC_AUTHORITY,
    }
)


class ProcessingScale(StrEnum):
    """Scale of personal data processing."""

    SMALL = "small"  # < 10,000 subjects
    MEDIUM = "medium"  # 10,000 - 99,999 subjects
    LARGE = "large"  # >= 100,000 subjects (or continuous high-volume processing)


class ProcessingOperation(StrEnum):
    """Semantic operations performed by a Process node."""

    COLLECTION = "collection"
    STORAGE = "storage"
    PROFILING = "profiling"
    SCORING = "scoring"
    AUTOMATED_DECISION_MAKING = "automated_decision_making"
    SYSTEMATIC_MONITORING = "systematic_monitoring"
    DATASET_MATCHING = "dataset_matching"
    AI_TRAINING = "ai_training"
    BIOMETRIC_IDENTIFICATION = "biometric_identification"
    PUBLIC_DISCLOSURE = "public_disclosure"
    ANALYTICS = "analytics"
    ARCHIVAL = "archival"
    DELETION = "deletion"


class DFDElementType(StrEnum):
    """Standard Data Flow Diagram (DFD) element types for LINDDUN mapping."""

    EXTERNAL_ENTITY = "external_entity"
    PROCESS = "process"
    DATA_STORE = "data_store"
    DATA_FLOW = "data_flow"


class LINDDUNCategory(StrEnum):
    """The 7 LINDDUN privacy threat categories."""

    LINKABILITY = "linkability"
    IDENTIFIABILITY = "identifiability"
    NON_REPUDIATION = "non_repudiation"
    DETECTABILITY = "detectability"
    DISCLOSURE = "disclosure"
    UNAWARENESS = "unawareness"  # Unawareness & Unintervenability
    NON_COMPLIANCE = "non_compliance"


class PETType(StrEnum):
    """Privacy-Enhancing Technologies (PETs) and organizational safeguards."""

    ENCRYPTION_IN_TRANSIT = "encryption_in_transit"
    ENCRYPTION_AT_REST = "encryption_at_rest"
    PSEUDONYMIZATION = "pseudonymization"
    ANONYMIZATION = "anonymization"
    DIFFERENTIAL_PRIVACY = "differential_privacy"
    DATA_MINIMIZATION = "data_minimization"
    ACCESS_CONTROL_RBAC = "access_control_rbac"
    PURPOSE_LIMITATION = "purpose_limitation"
    CONSENT_MANAGEMENT = "consent_management"
    PRIVACY_NOTICE_TRANSPARENCY = "privacy_notice_transparency"
    HUMAN_IN_THE_LOOP = "human_in_the_loop"
    RETENTION_ENFORCEMENT = "retention_enforcement"
    FEDERATED_LEARNING = "federated_learning"
    ZERO_KNOWLEDGE_PROOF = "zero_knowledge_proof"
    DATA_MASKING = "data_masking"
    AUDIT_LOGGING = "audit_logging"
    DPA_CONTRACT = "dpa_contract"
    SCC_TRANSFER_MECHANISM = "scc_transfer_mechanism"
    PIPL_SECURITY_ASSESSMENT = "pipl_security_assessment"
    PIPL_STANDARD_CONTRACT = "pipl_standard_contract"
    SECURITY_AUDIT = "security_audit"
    OTHER = "other"


class MitigationStatus(StrEnum):
    """Verification maturity of a declared mitigation control."""

    PLANNED = "planned"  # Declared in roadmap; NOT yet effective in production
    IMPLEMENTED = "implemented"  # Deployed in code/infra with reference evidence
    VERIFIED = "verified"  # Independently audited or security-tested


class TransferMechanism(StrEnum):
    """Legal mechanism authorizing cross-border data transfers."""

    NONE = "none"
    ADEQUACY_DECISION = "adequacy_decision"
    SCC = "scc"  # EU Standard Contractual Clauses
    BCR = "bcr"  # Binding Corporate Rules
    PIPL_SECURITY_ASSESSMENT = "pipl_security_assessment"  # 网信办数据出境安全评估
    PIPL_STANDARD_CONTRACT = "pipl_standard_contract"  # 个人信息出境标准合同备案
    PIPL_CERTIFICATION = "pipl_certification"  # 个人信息保护认证
    PIPL_EXEMPTION = "pipl_exemption"  # 2024 跨境新规法定豁免情形
    EXPLICIT_CONSENT_DEROGATION = "explicit_consent_derogation"


class RiskLevel(StrEnum):
    """4-level privacy risk rating aligned with CNIL PIA and GB/T 39335."""

    LOW = "low"  # Score 1-4 (Acceptable / 可接受)
    MEDIUM = "medium"  # Score 5-8 (Moderate / 中风险)
    HIGH = "high"  # Score 9-12 (High / 高风险 - triggers CI gate without mitigation)
    CRITICAL = "critical"  # Score 13-16 (Critical / 极高风险 - requires mitigation + DPO sign-off)
