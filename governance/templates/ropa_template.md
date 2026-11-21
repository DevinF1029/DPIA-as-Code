# 处理活动记录台账模板（Record of Processing Activities, RoPA）

> **模板编号**：`TPL-ROPA-002` ｜ **法定依据**：GDPR Art. 30(1)/(2)、中国 PIPL 第 56 条（留存 ≥ 3 年）、《网络数据安全管理条例》数据目录管理要求
> **维护方式**：由 DPIA-as-Code 引擎根据各业务仓库 `dataflow.yaml` 自动聚合生成，每季度由 DPO 办公室复核归档。

---

## 一、 控制者与治理联系人信息

| 项目 | 内容 |
| :--- | :--- |
| **数据控制者 / 个人信息处理者全称** | `<controller>` |
| **适用法域 / 总部所在地** | `<jurisdictions>` / `<home_region>` |
| **数据保护官 (DPO) / 数据安全负责人** | `<dpo_contact>` |
| **欧盟代表 / 境内专门机构（如适用）** | `<representative_contact>` |
| **台账快照版本 / 生成日期** | `<version>` / `YYYY-MM-DD` |

---

## 二、 处理活动明细台账（Art. 30(1)）

| 处理活动 ID | 系统 / 处理节点名称 | 处理目的 (`purposes`) | 合法性基础 (`lawful_basis`) | 数据主体类别 (`data_subjects`) | 个人数据类别 & 是否敏感 / 重要数据 | 接收方与第三方角色 (`recipients`) | 跨境目的地与法定传输机制 | 留存期限 (`retention_days`) | 核心技术与组织安全措施 (`PC-xxx`) | 关联 DPIA / PIA 报告编号 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ROPA-001` | `<process_name>` | `<purpose>` | `<lawful_basis>` | `<subjects>` | `<categories / sensitivity>` | `<third_party (role) / DPA状态>` | `<CN→SG / 机制>` | `<180天 / 自动清理>` | `PC-ENC-01, PC-ENC-02, PC-ACC-01` | `DPIA-YYYYMMDD-001` |

---

## 三、 审计复核记录

| 复核日期 | 复核人 (DPO Office) | 覆盖仓库 / Commit 范围 | 发现差异与整改单号 | 归档状态 |
| :--- | :--- | :--- | :--- | :--- |
| `YYYY-MM-DD` | `<name>` | `<repo@sha>` | `<无 / Ticket ID>` | 已归档（保留至 YYYY+3） |
