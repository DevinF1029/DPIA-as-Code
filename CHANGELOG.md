# Changelog

All notable changes to **DPIA-as-Code** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-11-22

### Added
- **Four-Layer GRC-as-Code Architecture**:
  - Layer 1 (`governance/`): Governance policy, multi-jurisdiction regulatory traceability matrix (GDPR / EU AI Act / China CSL, DSL, PIPL, NDSR), integrated assessment methodology (LINDDUN × CNIL × GB/T 39335), 25-control catalog (`PC-xxx-xx`), SOP, and audit templates.
  - Layer 2 (`rules/`): Machine-readable Policy-as-Code packs for statutory red lines (`RL-01`..`RL-05`), multi-jurisdiction thresholds & cross-jurisdiction conflicts, LINDDUN mapping & maturity reduction parameters, and the 25-control catalog.
  - Layer 3 (`schemas/` & `models/`): Strict Pydantic v2 models and exported JSON Schema (Draft 2020-12) covering `AISystemDeclaration`, `RiskWaiver`, CIIO / important data classifications, and optional financial sector hooks (`industry_sector`, `financial_data_level`, `Jurisdiction.CN_FIN_NFRA`).
  - Layer 4 (`engines/`): DFD Mermaid & RoPA generator, threshold & red-line engine, LINDDUN scorer with anti-greenwashing maturity reduction (`planned = 0`, `implemented = -1`, `verified = -2`), and CI/CD merge gate with waiver expiry enforcement.
- **CLI & CI/CD Integration**:
  - `dpia validate`, `dpia assess` (`md` / `pr-comment` / `json`), and `dpia serve` commands.
  - GitHub Actions workflow (`.github/workflows/dpia-gate.yml`) for unit tests, schema verification, audit artifact upload, idempotent PR risk summary comments, and `BLOCK` merge gating.
- **Interactive Web Compliance Workbench**:
  - FastAPI backend (`src/dpia_as_code/web/api.py`) and zero-build Alpine.js + Tailwind + Mermaid frontend (`src/dpia_as_code/web/static/`).
  - 5-step guided wizard, What-if control maturity simulation, interactive dynamic DPIA assessment sheet (with conditional FRIA & Important Data sections), remediation CSV export, Markdown/PDF report export, and bidirectional `dataflow.yaml` import/export.
- **Examples & Sample Reports**:
  - `static_marketing_site.yaml` (`PASS`), `facial_recognition_kyc.yaml` (`BLOCK`), and `banking_retail_credit_ai.yaml` (`WARN`), along with generated Chinese audit reports in `examples/sample_reports/`.
