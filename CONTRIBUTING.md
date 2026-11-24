# Contributing to DPIA-as-Code

感谢你对 **DPIA-as-Code** 的关注！无论是新增法域规则、完善 LINDDUN 威胁映射、改进 Web 合规工作台，还是修复文档与测试问题，我们都非常欢迎。

---

## 1. 本地开发环境搭建

需要 **Python >= 3.11**：

```bash
git clone https://github.com/DevinF1029/DPIA-as-Code.git
cd DPIA-as-Code

python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

pip install -e ".[web,dev]"
```

---

## 2. 日常检查命令

提交 PR 前，请确保本地以下命令全部通过：

```bash
# 运行全套单元测试（推荐 pytest，亦可使用 unittest）
pytest -v
python -m unittest discover -s tests -v

# 代码风格与静态检查
ruff check src tests

# 验证内置示例声明
dpia validate examples/static_marketing_site.yaml
dpia validate examples/facial_recognition_kyc.yaml
dpia validate examples/banking_retail_credit_ai.yaml
```

### ⚠️ 修改数据模型后的必做步骤

如果你修改了 `src/dpia_as_code/models/` 中的 Pydantic 模型或枚举，请务必重新导出 JSON Schema 并核对兼容性：

```bash
python -m dpia_as_code.schema_export
```

提交时请将更新后的 `schemas/dataflow.schema.json` 一并纳入 PR。

---

## 3. 贡献规则包与控制项（Policy-as-Code）

本项目遵循 **“治理体系为本，工程代码为用”** 的四层架构。新增或修改法域规则、红线或控制项时，请保持各层同步：

1. **第 1 层（`governance/`）**：补充对应的法规条文追溯（`02_regulatory_matrix.md`）或控制说明（`04_control_catalog.md`）。
2. **第 2 层（`rules/`）**：更新 `red_lines.yaml`、`thresholds.yaml`、`linddun_matrix.yaml` 或 `control_catalog.yaml`。
3. **第 4 层（`tests/`）**：在 `tests/test_rules.py` 与 `tests/test_engines.py` 中补充对应正例与反例测试。

---

## 4. Pull Request 流程

1. Fork 本仓库并从 `main` 创建特性分支（如 `feat/cn-fin-nfra-rules` 或 `fix/waiver-expiry`）。
2. 保持提交原子化，遵循 [Conventional Commits](https://www.conventionalcommits.org/) 风格（如 `feat:`、`fix:`、`docs:`、`test:`）。
3. 填写 PR 模板中的检查清单，确保 CI 门禁（`Unit Tests & Schema Integrity` 与 `DPIA / PIA / FRIA Gate`）全部通过。
4. 等待维护者 Review 并合并。

---

## 5. 合规声明

所有规则更新均应标明所依据的公开法律法规或标准条款（如 GDPR Art. 35、PIPL 第 55 条、EU AI Act Art. 27、GB/T 39335 等），避免引入未经核验的硬编码解释。
