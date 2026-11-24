"""Declarative input models representing `dataflow.yaml`.

This module defines the single source of truth for the DPIA-as-Code specification.
It is used both for runtime validation (Pydantic v2) and for generating the
official JSON Schema (`schemas/dataflow.schema.json`) for IDE autocomplete and CI linting.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dpia_as_code.models.enums import (
    GDPR_SPECIAL_CATEGORIES,
    PIPL_SENSITIVE_CATEGORIES,
    THIRD_PARTY_ROLES,
    VULNERABLE_DATA_SUBJECTS,
    AIRiskTier,
    DataCategory,
    DataClassification,
    DataSubjectCategory,
    DFDElementType,
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
    ProcessingScale,
    ProhibitedAIPractice,
    RedLineId,
    RiskLevel,
    TransferMechanism,
)

SlugId = Annotated[
    str,
    Field(
        pattern=r"^[a-z][a-z0-9_-]{1,63}$",
        description=(
            "Unique lowercase identifier (2-64 chars, starting with a letter; "
            "letters, digits, hyphens, underscores). Safe for Mermaid node IDs."
        ),
    ),
]

RegionCode = Annotated[
    str,
    Field(
        min_length=2,
        max_length=16,
        pattern=r"^[A-Z]{2}(-[A-Z0-9]{1,12})?$",
        description="ISO-like region/jurisdiction code in uppercase (e.g., CN, EU, US, SG, EU-DE).",
    ),
]

ControlId = Annotated[
    str,
    Field(
        pattern=r"^PC-(GOV|DAT|ENC|ACC|AI|XBD)-\d{2}$",
        description=(
            "Standardized privacy/security control ID from governance/04_control_catalog.md "
            "(e.g., PC-GOV-01, PC-ENC-02, PC-AI-01)."
        ),
    ),
]


class StrictBaseModel(BaseModel):
    """Base model that forbids unknown keys so YAML typos fail fast."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DPOSignOff(StrictBaseModel):
    """Formal DPO / Privacy Team review sign-off for high/critical risk architectures."""

    approved: bool = Field(default=False, description="Whether DPO/Privacy review has approved.")
    reviewer: str | None = Field(default=None, description="Name or handle of the approving DPO.")
    reviewed_at: date | None = Field(default=None, description="Date of approval (YYYY-MM-DD).")
    ticket: str | None = Field(
        default=None, description="Reference to review ticket or audit record URL/ID."
    )

    @model_validator(mode="after")
    def _validate_approval_details(self) -> DPOSignOff:
        if self.approved and not self.reviewer:
            raise ValueError("`dpo_signoff.reviewer` is required when `approved` is true.")
        return self


class AISystemDeclaration(StrictBaseModel):
    """EU AI Act (EU 2024/1689) and AI governance declaration for the system."""

    is_ai_system: bool = Field(
        default=True,
        description="Whether the architecture incorporates an AI / ML decision or generation model.",
    )
    risk_tier: AIRiskTier = Field(
        default=AIRiskTier.MINIMAL,
        description="Declared EU AI Act risk tier (none/minimal/limited/high_risk/prohibited).",
    )
    prohibited_practices: list[ProhibitedAIPractice] = Field(
        default_factory=list,
        description=(
            "EU AI Act Art. 5 prohibited AI practices present in this system. "
            "Any non-empty value triggers Hard Block red line RL-01."
        ),
    )
    transparency_notice: bool = Field(
        default=False,
        description="Whether natural persons are explicitly informed of AI interaction/generation (Art. 13/50).",
    )
    fria_required_override: bool | None = Field(
        default=None,
        description="Optional manual override for EU AI Act Art. 27 FRIA requirement.",
    )
    model_card_ref: str | None = Field(
        default=None,
        description="Reference URL or path to the AI Model Card / technical documentation.",
    )

    @model_validator(mode="after")
    def _validate_ai_declaration(self) -> AISystemDeclaration:
        if self.prohibited_practices and self.risk_tier == AIRiskTier.NONE:
            raise ValueError(
                "ai_system.risk_tier cannot be 'none' when prohibited_practices are declared."
            )
        return self


_RED_LINE_VALUES: frozenset[str] = frozenset(item.value for item in RedLineId)


class RiskWaiver(StrictBaseModel):
    """Time-bounded Risk Acceptance / Waiver record (governance/01_governance_policy.md §4).

    Statutory red lines (RL-01..RL-05) are strictly non-waivable.
    """

    waiver_id: SlugId = Field(description="Unique waiver identifier (e.g., waiver_credit_2026q1).")
    target_findings: list[str] = Field(
        min_length=1,
        description="Finding IDs or element IDs covered by this waiver (cannot target RL-01..RL-05).",
    )
    risk_level: Literal[RiskLevel.HIGH, RiskLevel.CRITICAL] = Field(
        description="Risk tier being waived: 'high' (max 90 days) or 'critical' (max 30 days)."
    )
    business_justification: str = Field(
        min_length=10,
        description="Substantive business necessity explaining why pre-launch remediation is infeasible.",
    )
    compensating_controls: list[str] = Field(
        min_length=1,
        description="Temporary compensating controls active during the waiver window.",
    )
    remediation_ticket: str = Field(
        min_length=1,
        description="Tracking ticket or PR reference for permanent remediation.",
    )
    owner: str = Field(min_length=1, description="Business/engineering owner accountable for closure.")
    approved_by: str = Field(
        min_length=1,
        description="Approving DPO (High) or C-Level/VP + DPO (Critical).",
    )
    approved_at: date = Field(description="Waiver approval date (YYYY-MM-DD).")
    expires_at: date = Field(
        description="Mandatory hard expiration date (YYYY-MM-DD). Auto-reverts CI gate to BLOCK on expiry."
    )
    renewal_count: int = Field(
        default=0,
        ge=0,
        le=1,
        description="Number of renewals used (governance policy allows at most 1 renewal).",
    )
    excludes_red_lines: bool = Field(
        default=True,
        description="Mandatory attestation confirming no statutory red line (RL-01..RL-05) is waived.",
    )

    @model_validator(mode="after")
    def _validate_waiver_policy(self) -> RiskWaiver:
        if not self.excludes_red_lines:
            raise ValueError(
                f"RiskWaiver '{self.waiver_id}' must set `excludes_red_lines: true`; "
                "statutory red lines (RL-01..RL-05) cannot be waived."
            )
        forbidden = [t for t in self.target_findings if t.upper() in _RED_LINE_VALUES]
        if forbidden:
            raise ValueError(
                f"RiskWaiver '{self.waiver_id}' cannot target statutory red lines: {forbidden}."
            )
        if self.expires_at <= self.approved_at:
            raise ValueError(
                f"RiskWaiver '{self.waiver_id}': `expires_at` ({self.expires_at}) "
                f"must be strictly after `approved_at` ({self.approved_at})."
            )
        duration_days = (self.expires_at - self.approved_at).days
        max_days = 90 if self.risk_level == RiskLevel.HIGH else 30
        if duration_days > max_days:
            raise ValueError(
                f"RiskWaiver '{self.waiver_id}': duration of {duration_days} days exceeds "
                f"maximum {max_days} days allowed for '{self.risk_level.value}' risk."
            )
        return self

    def is_active(self, as_of: date | None = None) -> bool:
        """Return True if this waiver is currently within its approved validity window."""
        check_date = as_of or date.today()
        return self.approved_at <= check_date <= self.expires_at


class SystemMetadata(StrictBaseModel):
    """Top-level governance metadata for the system or feature being assessed."""

    system_id: SlugId = Field(description="Unique identifier for this system or service.")
    name: str = Field(min_length=1, max_length=120, description="Human-readable system name.")
    description: str | None = Field(default=None, description="Short architecture summary.")
    controller: str = Field(
        min_length=1,
        description="Legal entity acting as Data Controller / Personal Information Handler.",
    )
    dpo_contact: str = Field(
        min_length=1,
        description="Contact email or team handle of the DPO / Privacy Engineering team.",
    )
    jurisdictions: list[Jurisdiction] = Field(
        default_factory=lambda: [Jurisdiction.GDPR, Jurisdiction.PIPL],
        min_length=1,
        description="Regulatory frameworks to evaluate against.",
    )
    home_region: RegionCode = Field(
        description="Primary legal/deployment region of the controller (e.g., CN, EU, US)."
    )
    data_subjects: list[DataSubjectCategory] = Field(
        default_factory=lambda: [DataSubjectCategory.CUSTOMERS],
        min_length=1,
        description="Categories of natural persons whose data is processed.",
    )
    estimated_subjects: int | None = Field(
        default=None,
        ge=0,
        description="Estimated count of affected individuals (used to infer processing scale).",
    )
    scale: ProcessingScale | None = Field(
        default=None,
        description=(
            "Processing scale (small/medium/large). Automatically inferred from "
            "`estimated_subjects` if omitted."
        ),
    )
    dpo_signoff: DPOSignOff | None = Field(
        default=None, description="Optional DPO approval metadata for critical/high-risk gates."
    )
    is_ciio: bool = Field(
        default=False,
        description=(
            "Whether the controller is designated as a Critical Information Infrastructure "
            "Operator (CIIO) under China CSL Art. 37 / CIIO Regulations."
        ),
    )
    industry_sector: IndustrySector = Field(
        default=IndustrySector.GENERAL,
        description=(
            "Optional industry sector tag (e.g., general, banking, insurance) reserving a clean "
            "extension hook for sector-specific GRC packs such as NFRA financial rules."
        ),
    )
    ai_system: AISystemDeclaration | None = Field(
        default=None,
        description="Optional EU AI Act (EU 2024/1689) and AI governance declaration.",
    )
    risk_waivers: list[RiskWaiver] = Field(
        default_factory=list,
        description="Time-bounded risk acceptance waivers (forbidden for statutory red lines).",
    )

    @model_validator(mode="after")
    def _infer_scale(self) -> SystemMetadata:
        if self.scale is None:
            if self.estimated_subjects is None:
                self.scale = ProcessingScale.SMALL
            elif self.estimated_subjects >= 100_000:
                self.scale = ProcessingScale.LARGE
            elif self.estimated_subjects >= 10_000:
                self.scale = ProcessingScale.MEDIUM
            else:
                self.scale = ProcessingScale.SMALL
        return self

    @property
    def has_vulnerable_subjects(self) -> bool:
        """Whether the system processes data of vulnerable individuals (WP29 Criterion #7)."""
        return any(subject in VULNERABLE_DATA_SUBJECTS for subject in self.data_subjects)


class DataAsset(StrictBaseModel):
    """Logical personal data asset flowing through or stored in the architecture."""

    id: SlugId = Field(description="Unique identifier referenced by stores and flows.")
    name: str = Field(min_length=1, max_length=120, description="Human-readable data asset name.")
    categories: list[DataCategory] = Field(
        min_length=1, description="Standardized data categories contained in this asset."
    )
    identifiability: IdentifiabilityLevel = Field(
        default=IdentifiabilityLevel.DIRECTLY_IDENTIFIABLE,
        description="Degree of identifiability of the data asset.",
    )
    is_sensitive_override: bool | None = Field(
        default=None,
        description="Optional manual override for statutory sensitivity classification.",
    )
    data_classification: DataClassification = Field(
        default=DataClassification.GENERAL,
        description=(
            "China DSL Art. 21 & GB/T 43697-2024 data classification "
            "(general / important / core)."
        ),
    )
    financial_data_level: FinancialDataLevel | None = Field(
        default=None,
        description=(
            "Optional JR/T 0197 financial data security grading hook (L1-L5) "
            "for banking and insurance sector governance."
        ),
    )
    description: str | None = Field(default=None, description="Details of fields in this asset.")

    @property
    def is_important_or_core(self) -> bool:
        """True if classified as China statutory Important Data or Core Data."""
        return self.data_classification in (
            DataClassification.IMPORTANT,
            DataClassification.CORE,
        )

    @property
    def is_personal_data(self) -> bool:
        """True if this asset represents personal data (non-anonymized & not purely non-personal)."""
        if self.identifiability == IdentifiabilityLevel.ANONYMIZED:
            return False
        return any(cat != DataCategory.NON_PERSONAL for cat in self.categories)

    def is_sensitive_for(self, jurisdiction: Jurisdiction) -> bool:
        """Return whether this asset is legally sensitive under the given jurisdiction."""
        if not self.is_personal_data:
            return False
        if self.is_sensitive_override is not None:
            return self.is_sensitive_override
        if jurisdiction == Jurisdiction.GDPR:
            return any(cat in GDPR_SPECIAL_CATEGORIES for cat in self.categories)
        if jurisdiction == Jurisdiction.PIPL:
            return any(cat in PIPL_SENSITIVE_CATEGORIES for cat in self.categories)
        return False

    @property
    def is_sensitive_any(self) -> bool:
        """True if sensitive under either GDPR or PIPL."""
        return self.is_sensitive_for(Jurisdiction.GDPR) or self.is_sensitive_for(Jurisdiction.PIPL)


class ExternalEntity(StrictBaseModel):
    """DFD External Entity: data subjects, internal operators, or third-party recipients."""

    id: SlugId = Field(description="Unique DFD node ID for this entity.")
    name: str = Field(min_length=1, max_length=120, description="Display name.")
    role: EntityRole = Field(description="Privacy/legal role of this external entity.")
    region: RegionCode | None = Field(
        default=None,
        description="Jurisdiction/region code. Defaults to `metadata.home_region` when omitted.",
    )
    trust_boundary: str | None = Field(
        default=None, description="Trust zone label for Mermaid subgraph grouping."
    )
    dpa_signed: bool = Field(
        default=False,
        description="Whether a Data Processing Agreement (DPA) / entrustment contract is executed.",
    )
    notice_provided: bool = Field(
        default=True,
        description="For data subjects: whether a clear privacy notice is presented.",
    )
    opt_out_available: bool = Field(
        default=False,
        description="For data subjects: whether opt-out / consent withdrawal mechanism is provided.",
    )

    @property
    def element_type(self) -> DFDElementType:
        return DFDElementType.EXTERNAL_ENTITY

    @property
    def is_third_party(self) -> bool:
        return self.role in THIRD_PARTY_ROLES


class ProcessNode(StrictBaseModel):
    """DFD Process: microservice, API endpoint, ML inference pipeline, or batch job."""

    id: SlugId = Field(description="Unique DFD node ID for this process.")
    name: str = Field(min_length=1, max_length=120, description="Display name.")
    description: str | None = Field(default=None, description="What this process does.")
    operations: list[ProcessingOperation] = Field(
        default_factory=lambda: [ProcessingOperation.COLLECTION],
        min_length=1,
        description="Processing operations executed by this component.",
    )
    purposes: list[str] = Field(
        min_length=1,
        description="Explicit business/legal purposes (populates GDPR Art. 30 RoPA).",
    )
    lawful_basis: LawfulBasis = Field(
        default=LawfulBasis.UNSPECIFIED,
        description="Lawful basis for processing under GDPR Art. 6 / PIPL Art. 13.",
    )
    region: RegionCode | None = Field(
        default=None,
        description="Deployment region. Defaults to `metadata.home_region` when omitted.",
    )
    trust_boundary: str | None = Field(
        default=None, description="Trust zone label (e.g., vpc_core, dmz)."
    )
    innovative_technology: bool = Field(
        default=False,
        description="Uses innovative/emerging tech (e.g., GenAI, facial recognition, IoT).",
    )
    prevents_rights_or_service: bool = Field(
        default=False,
        description=(
            "Output can deny a service, contract, or legal right (WP29 Criterion #9, "
            "e.g., automated credit rejection or account ban)."
        ),
    )
    human_review_available: bool = Field(
        default=False,
        description="Whether meaningful human-in-the-loop review exists for automated decisions.",
    )

    @property
    def element_type(self) -> DFDElementType:
        return DFDElementType.PROCESS


class DataStore(StrictBaseModel):
    """DFD Data Store: database, object storage, cache, data warehouse, or log sink."""

    id: SlugId = Field(description="Unique DFD node ID for this data store.")
    name: str = Field(min_length=1, max_length=120, description="Display name.")
    technology: str | None = Field(
        default=None, description="Underlying storage tech (e.g., PostgreSQL, S3, Redis, Milvus)."
    )
    region: RegionCode | None = Field(
        default=None,
        description="Physical storage region. Defaults to `metadata.home_region` when omitted.",
    )
    trust_boundary: str | None = Field(
        default=None, description="Trust zone label (e.g., private_data_tier)."
    )
    data: list[SlugId] = Field(
        min_length=1, description="IDs of declared `data_assets` persisted in this store."
    )
    encrypted_at_rest: bool = Field(
        default=False, description="Whether data at rest is encrypted (e.g., KMS/AES-256)."
    )
    retention_days: int | None = Field(
        default=None,
        ge=0,
        description="Maximum retention duration in days (`null` implies indefinite retention).",
    )
    access_control: str | None = Field(
        default=None, description="Access control model (e.g., RBAC, ABAC, least_privilege)."
    )
    audit_logging: bool = Field(
        default=False, description="Whether access/read audit logs are recorded and protected."
    )

    @property
    def element_type(self) -> DFDElementType:
        return DFDElementType.DATA_STORE


class DataFlow(StrictBaseModel):
    """DFD Data Flow: directed transfer of personal data between two DFD nodes."""

    id: SlugId = Field(description="Unique DFD identifier for this data flow.")
    name: str | None = Field(
        default=None, description="Optional label shown on Mermaid edges and reports."
    )
    source: SlugId = Field(description="Origin node ID (entity, process, or store).")
    target: SlugId = Field(description="Destination node ID (entity, process, or store).")
    data: list[SlugId] = Field(
        min_length=1, description="IDs of declared `data_assets` transmitted over this flow."
    )
    protocol: str | None = Field(
        default="HTTPS/TLS 1.3", description="Transport protocol (e.g., HTTPS/TLS 1.3, gRPC, Kafka)."
    )
    encrypted_in_transit: bool = Field(
        default=True, description="Whether transport-layer or end-to-end encryption is enforced."
    )
    transfer_mechanism: TransferMechanism = Field(
        default=TransferMechanism.NONE,
        description="Legal safeguard applied if this flow crosses jurisdictional borders.",
    )
    description: str | None = Field(default=None, description="Purpose or context of this flow.")

    @model_validator(mode="after")
    def _validate_and_label(self) -> DataFlow:
        if self.source == self.target:
            raise ValueError(f"Flow '{self.id}' cannot have identical source and target '{self.source}'.")
        if not self.name:
            self.name = f"{self.source} -> {self.target}"
        return self

    @property
    def element_type(self) -> DFDElementType:
        return DFDElementType.DATA_FLOW


class Mitigation(StrictBaseModel):
    """Privacy-Enhancing Technology (PET) or governance safeguard applied to elements."""

    id: SlugId = Field(description="Unique mitigation identifier.")
    control_id: ControlId | None = Field(
        default=None,
        description=(
            "Standardized control ID from governance/04_control_catalog.md & "
            "rules/control_catalog.yaml (e.g., PC-ENC-02, PC-AI-01)."
        ),
    )
    pet_type: PETType = Field(description="Standardized PET or control category.")
    description: str = Field(
        min_length=1, description="Concrete description of how this control is implemented."
    )
    applies_to: list[str] = Field(
        min_length=1,
        description="List of element IDs (entity/process/store/flow) or ['*'] for system-wide.",
    )
    addresses_threats: list[LINDDUNCategory] | None = Field(
        default=None,
        description=(
            "Optional explicit LINDDUN threats mitigated. If omitted, inferred from the "
            "built-in PET-to-LINDDUN knowledge base."
        ),
    )
    status: MitigationStatus = Field(
        default=MitigationStatus.PLANNED,
        description="Implementation maturity. Only implemented/verified controls fully reduce risk.",
    )
    evidence: str | None = Field(
        default=None,
        description="Verifiable evidence reference (PR URL, IaC path, audit report ID, or ticket).",
    )
    owner: str | None = Field(default=None, description="Responsible engineer or team.")

    @model_validator(mode="after")
    def _validate_verified_evidence(self) -> Mitigation:
        if self.status == MitigationStatus.VERIFIED and not self.evidence:
            raise ValueError(
                f"Mitigation '{self.id}' is marked 'verified' and must provide an `evidence` reference."
            )
        return self


DFDNode = ExternalEntity | ProcessNode | DataStore
DFDElement = ExternalEntity | ProcessNode | DataStore | DataFlow


class DataFlowModel(StrictBaseModel):
    """Root specification model for a `dataflow.yaml` file."""

    schema_version: Literal["1.0"] = Field(
        default="1.0", description="Specification schema version."
    )
    metadata: SystemMetadata = Field(description="System governance and regulatory context.")
    data_assets: list[DataAsset] = Field(
        min_length=1, description="Catalog of personal data assets processed by the system."
    )
    entities: list[ExternalEntity] = Field(
        default_factory=list, description="External entities (users, third parties, regulators)."
    )
    processes: list[ProcessNode] = Field(
        min_length=1, description="Processing components (APIs, services, ML pipelines)."
    )
    stores: list[DataStore] = Field(
        default_factory=list, description="Persistent or temporary data stores."
    )
    flows: list[DataFlow] = Field(
        min_length=1, description="Directed data flows linking entities, processes, and stores."
    )
    mitigations: list[Mitigation] = Field(
        default_factory=list, description="Declared privacy controls and PETs."
    )

    @model_validator(mode="after")
    def _validate_integrity_and_defaults(self) -> DataFlowModel:
        # 1. Propagate default region from metadata.home_region to nodes without an explicit region
        default_region = self.metadata.home_region
        for entity in self.entities:
            if entity.region is None:
                entity.region = default_region
        for proc in self.processes:
            if proc.region is None:
                proc.region = default_region
        for store in self.stores:
            if store.region is None:
                store.region = default_region

        # 2. Enforce unique IDs within data assets, mitigations, waivers, and across all DFD elements
        asset_ids = self._check_unique([a.id for a in self.data_assets], "data_assets")
        self._check_unique([m.id for m in self.mitigations], "mitigations")
        self._check_unique([w.waiver_id for w in self.metadata.risk_waivers], "risk_waivers")

        node_ids = self._check_unique(
            [e.id for e in self.entities]
            + [p.id for p in self.processes]
            + [s.id for s in self.stores],
            "DFD nodes (entities/processes/stores)",
        )
        flow_ids = self._check_unique([f.id for f in self.flows], "flows")
        overlap = node_ids & flow_ids
        if overlap:
            raise ValueError(f"Duplicate IDs shared between nodes and flows: {sorted(overlap)}")
        all_element_ids = node_ids | flow_ids

        # 3. Validate DataStore -> DataAsset references
        for store in self.stores:
            missing_assets = [aid for aid in store.data if aid not in asset_ids]
            if missing_assets:
                raise ValueError(
                    f"DataStore '{store.id}' references undefined data_assets: {missing_assets}"
                )

        # 4. Validate DataFlow -> source/target/data references
        for flow in self.flows:
            if flow.source not in node_ids:
                raise ValueError(
                    f"DataFlow '{flow.id}' references undefined source node '{flow.source}'."
                )
            if flow.target not in node_ids:
                raise ValueError(
                    f"DataFlow '{flow.id}' references undefined target node '{flow.target}'."
                )
            missing_assets = [aid for aid in flow.data if aid not in asset_ids]
            if missing_assets:
                raise ValueError(
                    f"DataFlow '{flow.id}' references undefined data_assets: {missing_assets}"
                )

        # 5. Validate Mitigation -> applies_to references
        for mitigation in self.mitigations:
            for target_id in mitigation.applies_to:
                if target_id != "*" and target_id not in all_element_ids:
                    raise ValueError(
                        f"Mitigation '{mitigation.id}' applies_to undefined element '{target_id}'."
                    )

        return self

    @staticmethod
    def _check_unique(ids: list[str], scope: str) -> set[str]:
        seen: set[str] = set()
        dups: set[str] = set()
        for item_id in ids:
            if item_id in seen:
                dups.add(item_id)
            seen.add(item_id)
        if dups:
            raise ValueError(f"Duplicate IDs found in {scope}: {sorted(dups)}")
        return seen

    # ------------------------------------------------------------------
    # Query & topology helper methods for downstream analysis engines
    # ------------------------------------------------------------------

    def data_asset_map(self) -> dict[str, DataAsset]:
        return {a.id: a for a in self.data_assets}

    def node_map(self) -> dict[str, DFDNode]:
        nodes: dict[str, DFDNode] = {}
        for entity in self.entities:
            nodes[entity.id] = entity
        for proc in self.processes:
            nodes[proc.id] = proc
        for store in self.stores:
            nodes[store.id] = store
        return nodes

    def element_map(self) -> dict[str, DFDElement]:
        elements: dict[str, DFDElement] = dict(self.node_map())
        for flow in self.flows:
            elements[flow.id] = flow
        return elements

    def get_element(self, element_id: str) -> DFDElement:
        return self.element_map()[element_id]

    def resolve_region(self, node_id: str) -> str:
        node = self.node_map()[node_id]
        return node.region or self.metadata.home_region

    @staticmethod
    def _jurisdiction_root(region: str) -> str:
        """Normalize sub-region codes (e.g., EU-DE -> EU, CN-SH -> CN) for border checks."""
        return region.split("-", maxsplit=1)[0]

    def is_cross_border_flow(self, flow: DataFlow) -> bool:
        """True if a flow carries personal or important/core data across distinct jurisdictional roots."""
        assets = self.data_asset_map()
        if not any(
            assets[aid].is_personal_data or assets[aid].is_important_or_core for aid in flow.data
        ):
            return False
        src_root = self._jurisdiction_root(self.resolve_region(flow.source))
        dst_root = self._jurisdiction_root(self.resolve_region(flow.target))
        return src_root != dst_root

    @property
    def has_important_or_core_data(self) -> bool:
        """True if any declared asset is classified as Important or Core Data."""
        return any(asset.is_important_or_core for asset in self.data_assets)

    def get_active_waivers(self, as_of: date | None = None) -> list[RiskWaiver]:
        """Return all risk waivers active on the given date (defaults to today)."""
        return [w for w in self.metadata.risk_waivers if w.is_active(as_of)]

    def get_cross_border_flows(self) -> list[DataFlow]:
        """Return all flows that transfer personal data across borders."""
        return [flow for flow in self.flows if self.is_cross_border_flow(flow)]

    def get_third_party_flows(self) -> list[DataFlow]:
        """Return all flows sending personal data to a third-party external entity."""
        entities_by_id = {e.id: e for e in self.entities}
        assets = self.data_asset_map()
        result: list[DataFlow] = []
        for flow in self.flows:
            target = entities_by_id.get(flow.target)
            if target and target.is_third_party and any(
                assets[aid].is_personal_data for aid in flow.data
            ):
                result.append(flow)
        return result

    def get_mitigations_for(self, element_id: str) -> list[Mitigation]:
        """Return all mitigations targeting a specific element ID or wildcard '*'."""
        return [
            m for m in self.mitigations if "*" in m.applies_to or element_id in m.applies_to
        ]

    def topology_warnings(self) -> list[str]:
        """Return non-fatal DFD modeling best-practice warnings."""
        warnings: list[str] = []
        nodes = self.node_map()
        for flow in self.flows:
            src = nodes[flow.source]
            dst = nodes[flow.target]
            if isinstance(src, ExternalEntity) and isinstance(dst, DataStore):
                warnings.append(
                    f"Flow '{flow.id}': ExternalEntity '{src.id}' connects directly to "
                    f"DataStore '{dst.id}' without an intermediate Process."
                )
            elif isinstance(src, DataStore) and isinstance(dst, ExternalEntity):
                warnings.append(
                    f"Flow '{flow.id}': DataStore '{src.id}' connects directly to "
                    f"ExternalEntity '{dst.id}' without an intermediate Process."
                )
            elif isinstance(src, DataStore) and isinstance(dst, DataStore):
                warnings.append(
                    f"Flow '{flow.id}': DataStore '{src.id}' connects directly to "
                    f"DataStore '{dst.id}' without an intermediate Process."
                )
        return warnings
