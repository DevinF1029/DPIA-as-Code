# 04. 隐私、数据安全与 AI 治理控制措施库（Privacy Control Catalog）

| 文档属性 | 内容 |
| :--- | :--- |
| **文档编号** | `CAT-CTRL-004` |
| **版本号** | `v1.0` |
| **设计定位** | 参照 ISO/IEC 27701、NIST Privacy Framework、GB/T 39335 及 EU AI Act，构建**可工程化落地、可客观审计验收**的统一控制基线 |
| **双向联动** | 本文档为人可读基线，与机器可读规则库 `rules/control_catalog.yaml` 保持 1:1 严格一致 |

---

## 一、 控制域总览

| 控制域代码 | 控制域名称 | 核心治理目标 |
| :---: | :--- | :--- |
| `PC-GOV` | 治理、合法性与透明度控制 | 确保合法性基础、单独同意、清晰告知、主体权利响应与 3 年合规留档 |
| `PC-DAT` | 数据分类分级与全生命周期控制 | 落实数据最小化、分类分级（一般/重要/核心）与硬性留存到期清理 |
| `PC-ENC` | 密码学与隐私增强技术（PETs） | 通过加密、假名化、匿名化、差分隐私、联邦学习降低泄露与重识别风险 |
| `PC-ACC` | 访问控制与审计追溯 | 最小权限隔离、防内部滥用、满足等保 6 个月以上不可篡改日志留存 |
| `PC-AI` | 算法与自动化决策治理（AI Safety） | 落实人工监督、可解释性、拒绝画像、模型偏差评估与高风险 AI 测试 |
| `PC-XBD` | 跨境传输与第三方供应链治理 | 落实 DPA 合同约束、SCC/TIA、中国出境安全评估/标准合同备案与出境审计 |

---

## 二、 分域控制清单与审计验收证据

> **折减维度说明**：`L` = 降低发生可能性（Likelihood）；`S` = 降低影响严重度（Severity）。

### 2.1 `PC-GOV` 治理、合法性与透明度控制

| 控制编号 | 控制名称 (`pet_type` 映射) | 缓解 LINDDUN 威胁 | 对标法规 | 折减维度 | 审计验收证据清单（`verified` 必备） |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `PC-GOV-01` | 合法性基础与目的限定 (`purpose_limitation`) | `Non-compliance` | GDPR Art. 5/6；PIPL Art. 6/13 | `L` | 隐私政策合法性映射表；接口级目的校验逻辑或网关拦截策略 |
| `PC-GOV-02` | 同意与敏感信息单独同意管理 (`consent_management`) | `Unawareness`, `Non-compliance` | GDPR Art. 7/9；PIPL Art. 14/28-31 | `L` | 独立授权弹窗 UI 截图；不可抵赖的同意流水日志（含时间戳、版本号、主体 ID）；撤回同意接口测试报告 |
| `PC-GOV-03` | 隐私与 AI 交互透明告知 (`privacy_notice_transparency`) | `Unawareness` | GDPR Art. 13/14；PIPL Art. 17；EU AI Act Art. 13/50 | `L` | 上线版隐私政策链接、分层告知（Layered Notice）界面、AI 生成/交互显著标识截图 |
| `PC-GOV-04` | 处理活动记录与 3 年合规归档 (`audit_logging` / 治理流程) | `Non-compliance` | GDPR Art. 30；PIPL Art. 56（≥3年）；网数条例 | `L` | 最新版 RoPA 台账；只读归档存储保留策略（Retention ≥ 1095 天）证明 |
| `PC-GOV-05` | 独立审计与监管事前咨询升级 (`security_audit`) | `Non-compliance` | GDPR Art. 36；PIPL Art. 54；网数条例 Art. 31 | `L` | 年度独立合规审计报告、整改闭环追踪表、监管咨询/报送回执 |
| `PC-GOV-06` | 重要数据/CIIO/超千万人年度风险评估与监管报送 (`security_audit`) | `Non-compliance` | DSL Art. 30；CIIO 条例 Art. 17/19；网数条例 Art. 28/31 | `L` | 数据安全负责人与管理机构任命文件、重要数据/CIIO 年度风险评估报告及省级以上主管部门报送回执 |

### 2.2 `PC-DAT` 数据分类分级与全生命周期控制

| 控制编号 | 控制名称 (`pet_type` 映射) | 缓解 LINDDUN 威胁 | 对标法规 | 折减维度 | 审计验收证据清单（`verified` 必备） |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `PC-DAT-01` | 源头数据最小化采集 (`data_minimization`) | `Linkability`, `Identifiability`, `Disclosure` | GDPR Art. 5(1)(c)/25；PIPL Art. 6 | `S` + `L` | API Schema 裁剪 PR、必要字段论证记录、非必要字段下线确认 |
| `PC-DAT-02` | 数据分类分级与重要数据打标（结合 `data_classification`） | `Non-compliance`, `Disclosure` | DSL Art. 21；网数条例 Art. 29；GB/T 43697 | `L` | 数据库/数仓元数据打标清单、重要数据识别申报回执 |
| `PC-DAT-03` | 留存期限硬性自动清理 (`retention_enforcement`) | `Linkability`, `Non-repudiation`, `Non-compliance` | GDPR Art. 5(1)(e)；PIPL Art. 19/47 | `S` + `L` | TTL 配置、定时清理脚本/CronJob 执行日志、到期彻底销毁验证记录 |
| `PC-DAT-04` | 前端/日志动态脱敏与掩码 (`data_masking`) | `Identifiability`, `Disclosure` | GDPR Art. 32；PIPL Art. 51；CSL Art. 21 | `L` | 日志脱敏正则/中间件配置、客服后台字段掩码截图、日志扫描无明文敏感字段报告 |

### 2.3 `PC-ENC` 密码学与隐私增强技术（PETs）

| 控制编号 | 控制名称 (`pet_type` 映射) | 缓解 LINDDUN 威胁 | 对标法规 | 折减维度 | 审计验收证据清单（`verified` 必备） |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `PC-ENC-01` | 传输层强加密 (`encryption_in_transit`) | `Disclosure`, `Detectability` | GDPR Art. 32；PIPL Art. 51；CSL Art. 21 | `L` | TLS 1.2/1.3 强制策略、Istio/Service Mesh mTLS 配置文件、SSL Labs/扫描验证报告 |
| `PC-ENC-02` | 静态存储加密与密钥分离 (`encryption_at_rest`) | `Disclosure`, `Identifiability` | GDPR Art. 32；PIPL Art. 51 | `L` | 数据库/对象存储 KMS/AES-256（或国密 SM4）开启截图、IaC (Terraform) 代码、密钥轮换记录 |
| `PC-ENC-03` | 强假名化与映射表隔离 (`pseudonymization`) | `Identifiability`, `Linkability` | GDPR Art. 4(5)/25/32；PIPL Art. 51（去标识化） | `S` + `L` | 令牌化/加盐哈希实现代码、映射表独立库与独立 KMS 权限隔离证明 |
| `PC-ENC-04` | 不可逆匿名化 (`anonymization`) | `Identifiability`, `Linkability`, `Detectability` | GDPR Recital 26；PIPL Art. 4/73 | `S` + `L` | k-匿名 / l-多样性处理脚本、重识别攻击测试报告（证明无法复原特定自然人） |
| `PC-ENC-05` | 差分隐私 (`differential_privacy`) | `Linkability`, `Identifiability`, `Detectability` | GDPR Art. 25；EU AI Act Art. 10 | `S` + `L` | 隐私预算（ε, δ）参数评审文档、噪声注入库配置与隐私效用测试报告 |
| `PC-ENC-06` | 联邦学习 / 零知识证明 (`federated_learning`, `zero_knowledge_proof`) | `Disclosure`, `Linkability`, `Non-repudiation` | GDPR Art. 25；PIPL Art. 51 | `S` + `L` | 架构设计评审纪要、本地梯度/证明验证协议安全评估报告 |

### 2.4 `PC-ACC` 访问控制与审计追溯

| 控制编号 | 控制名称 (`pet_type` 映射) | 缓解 LINDDUN 威胁 | 对标法规 | 折减维度 | 审计验收证据清单（`verified` 必备） |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `PC-ACC-01` | 最小权限与角色访问控制 (`access_control_rbac`) | `Disclosure`, `Linkability` | GDPR Art. 32；CSL Art. 21；PIPL Art. 51 | `L` | IAM/RBAC 策略文件、高敏库双人审批（Just-in-Time）记录、季度权限复核清单 |
| `PC-ACC-02` | 防篡改访问审计日志 (`audit_logging`) | `Disclosure`, `Non-compliance` | CSL Art. 21（≥6个月）；DSL Art. 27；GDPR Art. 32 | `L` | SIEM 日志接入证明、写保护策略（WORM）、异常批量导出告警演练记录 |

### 2.5 `PC-AI` 算法与自动化决策治理

| 控制编号 | 控制名称 (`pet_type` 映射) | 缓解 LINDDUN 威胁 | 对标法规 | 折减维度 | 审计验收证据清单（`verified` 必备） |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `PC-AI-01` | 人工监督与申诉复核机制 (`human_in_the_loop`) | `Unawareness`, `Non-compliance` | GDPR Art. 22；PIPL Art. 24；EU AI Act Art. 14 | `S` + `L` | 人工复核 SLA 规范、申诉通道界面、操作员一键覆写/中止（Kill-Switch）演练记录 |
| `PC-AI-02` | 个性化关闭与算法可解释性 (`privacy_notice_transparency` + `opt_out`) | `Unawareness`, `Linkability` | PIPL Art. 24（关闭个性化选项）；EU AI Act Art. 13 | `L` | 关闭定向推荐开关测试录屏、用户可读的决策关键因子说明模板 |
| `PC-AI-03` | 高风险 AI 风险管理与红队测试 (`security_audit`) | `Non-compliance`, `Disclosure` | EU AI Act Art. 9/15；网数条例 AI 合规 | `L` | 模型对抗/越狱测试报告、准确率与鲁棒性基线记录、算法备案凭证（如适用） |
| `PC-AI-04` | 训练数据合法性与偏差审计 (`data_minimization` / `security_audit`) | `Non-compliance`, `Identifiability` | EU AI Act Art. 10；网数条例生成式 AI 要求 | `S` + `L` | 训练数据集卡片（Data Card）、版权与授权来源证明、群体公平性/偏差测试报告 |

### 2.6 `PC-XBD` 跨境传输与第三方供应链治理

| 控制编号 | 控制名称 (`pet_type` 映射) | 缓解 LINDDUN 威胁 | 对标法规 | 折减维度 | 审计验收证据清单（`verified` 必备） |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `PC-XBD-01` | 欧盟跨境传输机制与 TIA (`scc_transfer_mechanism`) | `Non-compliance`, `Disclosure` | GDPR Chapter V (Art. 44–49) | `L` | 双方签署版 EU SCC 协议、Transfer Impact Assessment (TIA) 评估结论、补充加密措施 |
| `PC-XBD-02` | 中国数据出境法定路径 (`pipl_security_assessment`, `pipl_standard_contract`) | `Non-compliance`, `Disclosure` | PIPL Art. 38–40；CSL Art. 37；DSL Art. 31；网数条例 Art. 35–39；2024 跨境新规 | `L` | 网信办数据出境安全评估通过批复 / 省级网信办标准合同备案回执 / 个人信息保护认证证书 / 豁免法律评估单 |
| `PC-XBD-03` | 第三方数据处理协议与供应商尽调 (`dpa_contract`) | `Non-compliance`, `Disclosure`, `Linkability` | GDPR Art. 28；PIPL Art. 21/23；网数条例 Art. 29 | `L` | 签署版 DPA / 委托处理协议、子处理者清单、供应商 SOC 2 / ISO 27001/27701 审计报告 |

---

## 三、 控制库维护原则

* **控制编号稳定性**：`PC-xxx-xx` 编号一经发布不得随意复用或变更含义，废弃控制须标记为 `DEPRECATED` 并保留审计映射历史。
* **多控制协同**：高风险场景（如跨境生物识别）通常需要**技术控制（`PC-ENC`）+ 治理控制（`PC-GOV`）+ 跨境法定机制（`PC-XBD`）**组合落地，单一控制不能替代跨维度合规要件。
