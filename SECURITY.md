# Security Policy

## Scope

**DPIA-as-Code** 是一个面向合规评估与 CI/CD 门禁的 GRC-as-Code 引擎。我们尤其重视以下两类安全与合规完整性问题：

1. **传统应用安全漏洞**
   - Web 工作台（FastAPI 后端或前端静态页面）中的 XSS、模板/HTML 注入、路径遍历、任意文件读取或 SSRF；
   - `dataflow.yaml` / `rules/*.yaml` 解析过程中的不安全反序列化或 DoS；
   - 依赖组件的高危已知漏洞。
2. **门禁绕过与规则失效（Gate Bypass / False-Negative）**
   - 能够绕过法定红线（`RL-01`..`RL-05`）拦截、过期 `RiskWaiver` 校验或跨法域冲突阻断的边界漏洞；
   - `planned` 控制错误获得风险折减（“纸面洗绿”漏洞）。

## Reporting a Vulnerability

**请勿在公开 Issue 中披露未修复的安全漏洞或门禁绕过利用细节。**

请通过以下私密渠道报告：

- 使用 GitHub 的 **Private Vulnerability Reporting** 功能：在仓库 **Security -> Advisories -> Report a vulnerability** 提交报告。

请在报告中尽量包含：

- 受影响的组件/文件路径及版本（或 commit hash）；
- 最小可复现的 `dataflow.yaml` 片段或 HTTP 请求示例；
- 预期行为与实际观察到的风险/绕过结果；
- 如有修复建议，欢迎一并附上。

## Response Timeline

- 我们会在 **3 个工作日内** 确认收到报告；
- 会在 **7 个工作日内** 给出问题定级与修复排期；
- 补丁发布后，我们会在 Release Notes 与 [CHANGELOG.md](CHANGELOG.md) 中向报告者致谢（除非报告者要求匿名）。

## Supported Versions

| Version | Supported |
| ------- | --------- |
| `0.1.x` / `main` | ✅ Active |
