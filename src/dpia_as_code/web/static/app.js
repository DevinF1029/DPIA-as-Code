/* DPIA-as-Code Governance Workbench — Alpine.js application state & logic. */

function uid(prefix) {
  return `${prefix}_${Math.random().toString(36).slice(2, 7)}`;
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function starterSpec() {
  return {
    schema_version: '1.0',
    metadata: {
      system_id: 'new-system',
      name: '新建业务系统',
      description: '',
      controller: '示例机构',
      dpo_contact: 'dpo@example.com',
      jurisdictions: ['GDPR', 'PIPL'],
      home_region: 'CN',
      data_subjects: ['customers'],
      estimated_subjects: 10000,
      is_ciio: false,
      industry_sector: 'general',
      risk_waivers: [],
    },
    data_assets: [
      { id: 'customer_profile', name: '客户基本信息', categories: ['basic_identity', 'contact_info'], identifiability: 'directly_identifiable', data_classification: 'general' },
    ],
    entities: [
      { id: 'end_user', name: '终端用户', role: 'data_subject', trust_boundary: 'public_internet', notice_provided: true, opt_out_available: true, dpa_signed: false },
    ],
    processes: [
      { id: 'core_api', name: '核心业务服务', operations: ['collection'], purposes: ['提供核心业务服务'], lawful_basis: 'contract', trust_boundary: 'vpc_core', innovative_technology: false, prevents_rights_or_service: false, human_review_available: false },
    ],
    stores: [],
    flows: [
      { id: 'flow_user_to_api', name: '用户提交信息', source: 'end_user', target: 'core_api', data: ['customer_profile'], protocol: 'HTTPS/TLS 1.3', encrypted_in_transit: true, transfer_mechanism: 'none' },
    ],
    mitigations: [],
  };
}

function defaultAiSystem() {
  return { is_ai_system: true, risk_tier: 'minimal', prohibited_practices: [], transparency_notice: false, model_card_ref: '' };
}

function defaultSignoff() {
  return { approved: false, reviewer: '', reviewed_at: '', ticket: '' };
}

function defaultReview(systemId = 'new-system') {
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const slug = String(systemId || 'SYS').slice(0, 14).toUpperCase();
  return {
    assessment_id: `DPIA-${stamp}-${slug}`,
    business_owner: '',
    lawful_basis_rationale: '',
    necessity_proportionality: '',
    data_subject_rights_sla: '',
    fria_affected_groups: '',
    fria_fairness_bias: '',
    fria_human_oversight: '',
    important_data_impact: '',
    important_data_filing_ref: '',
    remediations: [],
    signoffs: [],
  };
}

function normalizeSpec(raw) {
  const s = JSON.parse(JSON.stringify(raw));
  s.schema_version = s.schema_version || '1.0';
  const m = (s.metadata = s.metadata || {});
  m.jurisdictions = m.jurisdictions || [];
  m.data_subjects = m.data_subjects || [];
  m.risk_waivers = (m.risk_waivers || []).map((w) => ({ compensating_controls: [], target_findings: [], ...w }));
  m.industry_sector = m.industry_sector || 'general';
  m.is_ciio = !!m.is_ciio;
  m._ai_enabled = !!m.ai_system;
  m.ai_system = { ...defaultAiSystem(), ...(m.ai_system || {}) };
  m._signoff_enabled = !!m.dpo_signoff;
  m.dpo_signoff = { ...defaultSignoff(), ...(m.dpo_signoff || {}) };
  m.estimated_subjects = m.estimated_subjects ?? '';
  delete m.scale;

  for (const key of ['data_assets', 'entities', 'processes', 'stores', 'flows', 'mitigations']) s[key] = s[key] || [];
  s.data_assets.forEach((a) => { a.financial_data_level = a.financial_data_level || ''; a.data_classification = a.data_classification || 'general'; a.categories = a.categories || []; });
  s.processes.forEach((p) => { p.operations = p.operations || []; p.purposes = p.purposes || []; });
  s.stores.forEach((st) => { st.data = st.data || []; st.retention_days = st.retention_days ?? ''; st.access_control = st.access_control || ''; });
  s.flows.forEach((f) => { f.data = f.data || []; f.transfer_mechanism = f.transfer_mechanism || 'none'; });
  s.mitigations.forEach((mi) => { mi.control_id = mi.control_id || ''; mi.applies_to = mi.applies_to || []; mi.evidence = mi.evidence || ''; mi.owner = mi.owner || ''; });
  return s;
}

function cleanSpec(spec) {
  const s = JSON.parse(JSON.stringify(spec));
  const m = s.metadata;
  if (!m._ai_enabled) delete m.ai_system;
  if (!m._signoff_enabled) delete m.dpo_signoff;
  const strip = (obj) => {
    if (Array.isArray(obj)) return obj.map(strip);
    if (obj && typeof obj === 'object') {
      const out = {};
      for (const [k, v] of Object.entries(obj)) {
        if (k.startsWith('_') || v === '' || v === undefined) continue;
        if (typeof v === 'number' && Number.isNaN(v)) continue;
        out[k] = strip(v);
      }
      return out;
    }
    return obj;
  };
  return strip(s);
}

function workbench() {
  return {
    meta: { enums: {}, controls: [], red_lines: [], examples: [] },
    spec: normalizeSpec(starterSpec()),
    review: defaultReview('new-system'),
    result: null,
    errors: [],
    stale: false,
    loading: false,
    leftTab: 'system',
    rightTab: 'overview',
    matrixMode: 'residual',
    selectedExample: '',
    asOf: new Date().toISOString().slice(0, 10),
    toast: '',
    _timer: null,
    _seq: 0,
    _syncingReview: false,
    dfdSvg: '',

    async init() {
      mermaid.initialize({
        startOnLoad: false,
        theme: 'neutral',
        securityLevel: 'loose',
        flowchart: { htmlLabels: true, curve: 'linear' },
      });
      const res = await fetch('/api/meta');
      this.meta = await res.json();
      const preferred = this.meta.examples.find((e) => e.id === 'banking_retail_credit_ai') || this.meta.examples[0];
      if (preferred) await this.loadExample(preferred.id);
      else this.scheduleAssess(0);
      this.$watch('spec', () => this.scheduleAssess());
      this.$watch('asOf', () => this.scheduleAssess());
      this.$watch('review', () => {
        if (!this._syncingReview) this.scheduleAssess(450);
      });
    },

    // ---------------- labels & options ----------------
    opts(enumName) { return this.meta.enums[enumName] || []; },
    label(enumName, value) {
      const hit = (this.meta.enums[enumName] || []).find((o) => o.value === value);
      return hit ? hit.label : value;
    },
    controlById(id) { return this.meta.controls.find((c) => c.id === id); },
    get nodeOptions() {
      return [
        ...this.spec.entities.map((e) => ({ id: e.id, label: `[实体] ${e.name}` })),
        ...this.spec.processes.map((p) => ({ id: p.id, label: `[处理] ${p.name}` })),
        ...this.spec.stores.map((s) => ({ id: s.id, label: `[存储] ${s.name}` })),
      ];
    },
    get elementOptions() {
      return [
        { id: '*', label: '全系统 (*)' },
        ...this.nodeOptions,
        ...this.spec.flows.map((f) => ({ id: f.id, label: `[数据流] ${f.name || f.id}` })),
      ];
    },
    get findingOptions() { return (this.result?.report.findings || []).map((f) => f.finding_id); },

    // ---------------- CRUD helpers ----------------
    addAsset() { this.spec.data_assets.push({ id: uid('asset'), name: '新数据资产', categories: ['basic_identity'], identifiability: 'directly_identifiable', data_classification: 'general', financial_data_level: '' }); },
    addEntity() { this.spec.entities.push({ id: uid('entity'), name: '新外部实体', role: 'data_subject', region: '', trust_boundary: '', dpa_signed: false, notice_provided: true, opt_out_available: false }); },
    addProcess() { this.spec.processes.push({ id: uid('proc'), name: '新处理节点', operations: ['collection'], purposes: ['请填写处理目的'], lawful_basis: 'consent', region: '', trust_boundary: '', innovative_technology: false, prevents_rights_or_service: false, human_review_available: false }); },
    addStore() { this.spec.stores.push({ id: uid('store'), name: '新数据存储', technology: '', region: '', trust_boundary: '', data: this.spec.data_assets.slice(0, 1).map((a) => a.id), encrypted_at_rest: false, retention_days: '', access_control: '', audit_logging: false }); },
    addFlow() {
      const n = this.nodeOptions;
      this.spec.flows.push({ id: uid('flow'), name: '新数据流', source: n[0]?.id || '', target: n[1]?.id || '', data: this.spec.data_assets.slice(0, 1).map((a) => a.id), protocol: 'HTTPS/TLS 1.3', encrypted_in_transit: true, transfer_mechanism: 'none' });
    },
    addMitigation() { this.spec.mitigations.push({ id: uid('mit'), control_id: '', pet_type: 'encryption_in_transit', description: '请描述控制措施的具体实现', applies_to: ['*'], status: 'planned', evidence: '', owner: '' }); },
    addWaiver() {
      const today = new Date();
      const exp = new Date(today.getTime() + 60 * 86400000);
      this.spec.metadata.risk_waivers.push({
        waiver_id: uid('waiver'), target_findings: [], risk_level: 'high', business_justification: '请说明为何无法在上线前完成根治整改',
        compensating_controls: ['临时补偿性控制措施'], remediation_ticket: 'TICKET-001', owner: '', approved_by: '',
        approved_at: today.toISOString().slice(0, 10), expires_at: exp.toISOString().slice(0, 10), renewal_count: 0, excludes_red_lines: true,
      });
    },
    remove(list, idx) { list.splice(idx, 1); },
    onControlChange(mit) {
      const c = this.controlById(mit.control_id);
      if (c && c.pet_types.length) mit.pet_type = c.pet_types[0];
    },
    setLines(obj, key, text) { obj[key] = text.split('\n').map((s) => s.trim()).filter(Boolean); },

    // ---------------- API calls ----------------
    scheduleAssess(delay = 400) {
      clearTimeout(this._timer);
      this._timer = setTimeout(() => this.runAssess(), delay);
    },
    _syncReviewFromResult(data) {
      this._syncingReview = true;
      try {
        const existingByFinding = new Map(
          this.review.remediations.filter((r) => r.finding_id).map((r) => [r.finding_id, r]),
        );
        const customRows = this.review.remediations.filter((r) => !r.finding_id);
        const merged = (data.default_remediations || []).map((def) => {
          const prev = existingByFinding.get(def.finding_id);
          return prev ? { ...def, ...prev } : { ...def };
        });
        const combined = [...merged, ...customRows].map((row, i) => ({
          ...row,
          rem_id: `REM-${String(i + 1).padStart(2, '0')}`,
        }));
        if (JSON.stringify(combined) !== JSON.stringify(this.review.remediations)) {
          this.review.remediations = combined;
        }
        if (!this.review.signoffs.length && data.default_signoffs) {
          this.review.signoffs = data.default_signoffs.map((s) => ({ ...s }));
        }
      } finally {
        this.$nextTick(() => { this._syncingReview = false; });
      }
    },
    async runAssess() {
      this.loading = true;
      try {
        const res = await fetch('/api/assess', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ spec: cleanSpec(this.spec), as_of: this.asOf || null, review: this.review }),
        });
        const data = await res.json();
        if (!res.ok) { this.errors = data.errors || [data.message || '评估失败']; this.stale = !!this.result; return; }
        this.errors = []; this.stale = false; this.result = data;
        this._syncReviewFromResult(data);
        this.$nextTick(() => this.renderDfd());
      } catch (e) {
        this.errors = [`无法连接评估服务：${e.message}`];
      } finally { this.loading = false; }
    },
    addRemediation() {
      const idx = this.review.remediations.length + 1;
      const due = new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10);
      this.review.remediations.push({
        rem_id: `REM-${String(idx).padStart(2, '0')}`,
        finding_id: '',
        control_id: '',
        action: '请填写整改措施',
        owner: '',
        due_date: due,
        evidence: '',
        status: 'Open',
      });
    },
    fillSampleReview() {
      const name = this.spec.metadata.name || '本系统';
      const today = new Date().toISOString().slice(0, 10);
      this.review.business_owner = this.review.business_owner || '业务条线负责人（零售/产品部）';
      this.review.lawful_basis_rationale =
        `已逐一核验 ${name} 各处理节点合法性基础：涉敏感个人信息与外部征信/身份核验环节均采用单独同意（separate_consent）或法定合同必需，未在中国业务场景下混用 GDPR 合法利益。`;
      this.review.necessity_proportionality =
        '已按最小必要原则裁剪非核心字段，仅保留实现身份核验与风险决策所必需的衍生特征，避免原始明文生物特征长期留存，且已评估人工审核替代方案的时效成本。';
      this.review.data_subject_rights_sla =
        '在产品端提供分层隐私政策告知、独立撤回授权入口与拒绝自动化决策申诉通道；数据主体查询、更正、删除及人工复核请求承诺在 15 个工作日内闭环响应。';
      if (this.result?.report.threshold.fria_required) {
        this.review.fria_affected_groups = '面向成年个人客户群体，已排除未满 14 周岁未成年人，日均调用属高频自动化评估场景。';
        this.review.fria_fairness_bias = '已完成跨年龄、性别及地域维度的群体误拒率（FPR/FNR）偏差测试，差异控制在 2% 阈值以内。';
        this.review.fria_human_oversight = '风控操作员具备逐案人工复核、结果覆写及一键中止模型服务（Kill-Switch）权限，并已纳入季度应急演练。';
      }
      if (this.result?.report.threshold.important_data_assessment_required) {
        this.review.important_data_impact = '重要数据严格在境内生产专网闭环存储与处理，未向境外提供；对外接口经由金融专线与双向 mTLS 加密。';
        this.review.important_data_filing_ref = 'IMP-ASSESS-2026-001（已纳入年度重要数据风险评估报送计划）';
      }
      if (this.review.signoffs.length >= 2) {
        this.review.signoffs[0].name = this.review.signoffs[0].name || '张明 / 零售业务部';
        this.review.signoffs[0].decision = '确认提交并承担剩余风险';
        this.review.signoffs[0].signed_date = this.review.signoffs[0].signed_date || today;
        this.review.signoffs[1].name = this.review.signoffs[1].name || '李华 / 信息安全与隐私工程部';
        this.review.signoffs[1].decision = '技术控制核验通过';
        this.review.signoffs[1].signed_date = this.review.signoffs[1].signed_date || today;
      }
      this.notify('已填入示范审查内容，最终报告已同步更新');
    },
    exportRemediationCsv() {
      const rows = this.review.remediations || [];
      const header = ['整改编号', '关联发现ID', '控制编号', '具体整改动作', '责任人', '目标完成日', '验证证据', '状态'];
      const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
      const lines = [
        header.map(esc).join(','),
        ...rows.map((r) => [r.rem_id, r.finding_id, r.control_id, r.action, r.owner, r.due_date, r.evidence, r.status].map(esc).join(',')),
      ];
      this.download(`${this.spec.metadata.system_id}_整改台账.csv`, '\uFEFF' + lines.join('\r\n'), 'text/csv');
    },
    async renderDfd() {
      const el = document.getElementById('dfd-canvas');
      if (!el || !this.result) return;
      try {
        const { svg } = await mermaid.render(`dfd_svg_${++this._seq}`, this.result.report.mermaid_dfd);
        el.innerHTML = svg; this.dfdSvg = svg;
      } catch (e) {
        el.innerHTML = `<pre class="text-xs text-red-700 whitespace-pre-wrap">DFD 渲染失败：${escapeHtml(e.message)}</pre>`;
      }
    },
    async loadExample(id) {
      if (!id) return;
      const res = await fetch(`/api/examples/${id}`);
      const data = await res.json();
      if (!res.ok) { this.notify(data.message || '加载失败'); return; }
      this._syncingReview = true;
      this.spec = normalizeSpec(data.spec);
      this.review = defaultReview(this.spec.metadata.system_id);
      this.selectedExample = id;
      this.$nextTick(() => { this._syncingReview = false; });
      this.notify('已载入模板：' + (this.meta.examples.find((e) => e.id === id)?.title || id));
      this.scheduleAssess(0);
    },
    newBlank() {
      this._syncingReview = true;
      this.spec = normalizeSpec(starterSpec());
      this.review = defaultReview('new-system');
      this.selectedExample = '';
      this.$nextTick(() => { this._syncingReview = false; });
      this.notify('已新建空白评估');
      this.scheduleAssess(0);
    },
    async importYaml(evt) {
      const file = evt.target.files[0]; if (!file) return;
      const text = await file.text(); evt.target.value = '';
      const res = await fetch('/api/parse-yaml', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ yaml_text: text }) });
      const data = await res.json();
      if (!res.ok) { this.errors = data.errors || [data.message]; this.notify('导入失败：YAML 未通过校验'); return; }
      this._syncingReview = true;
      this.spec = normalizeSpec(data.spec);
      this.review = defaultReview(this.spec.metadata.system_id);
      this.selectedExample = '';
      this.$nextTick(() => { this._syncingReview = false; });
      this.notify(`已导入 ${file.name}`);
      this.scheduleAssess(0);
    },
    async exportYaml() {
      const res = await fetch('/api/export-yaml', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ spec: cleanSpec(this.spec) }) });
      const data = await res.json();
      if (!res.ok) { this.errors = data.errors || [data.message]; this.notify('导出失败：请先修正校验错误'); return; }
      this.download(data.filename, data.yaml_text, 'text/yaml');
    },
    exportMarkdown() {
      if (!this.result) return;
      this.download(`${this.spec.metadata.system_id}_DPIA_报告.md`, this.result.markdown, 'text/markdown');
    },
    download(name, text, mime) {
      const blob = new Blob([text], { type: `${mime};charset=utf-8` });
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      this.notify(`已下载 ${name}`);
    },
    reportHtml() {
      if (!this.result) return '';
      const wrap = document.createElement('div');
      wrap.innerHTML = marked.parse(this.result.markdown);
      wrap.querySelectorAll('code.language-mermaid').forEach((code) => {
        const div = document.createElement('div'); div.className = 'dfd-print'; div.innerHTML = this.dfdSvg || '';
        code.closest('pre').replaceWith(div);
      });
      return wrap.innerHTML;
    },
    printReport() {
      const w = window.open('', '_blank');
      w.document.write(`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escapeHtml(this.spec.metadata.name)} - DPIA 审计报告</title>
        <style>body{font-family:"PingFang SC","Noto Sans SC","Microsoft YaHei",sans-serif;max-width:960px;margin:28px auto;color:#18181b;font-size:13px;line-height:1.65}
        table{border-collapse:collapse;width:100%;margin:10px 0;font-size:12px}th,td{border:1px solid #d4d4d8;padding:5px 8px;text-align:left;vertical-align:top}
        th{background:#f4f4f5;font-weight:600}h1{font-size:20px;border-bottom:2px solid #18181b;padding-bottom:6px}h2{font-size:15px;color:#18181b;margin-top:24px;border-left:3px solid #1e3a5f;padding-left:8px}
        blockquote{border-left:3px solid #a1a1aa;margin:8px 0;padding:6px 12px;color:#52525b;background:#fafafa}code{font-family:Consolas,monospace;background:#f4f4f5;padding:1px 4px;border-radius:3px}
        .dfd-print svg{max-width:100%;height:auto}@media print{h2{page-break-after:avoid}table{page-break-inside:auto}}</style></head>
        <body>${this.reportHtml()}<script>setTimeout(()=>window.print(),400)<\/script></body></html>`);
      w.document.close();
    },
    notify(msg) { this.toast = msg; setTimeout(() => { if (this.toast === msg) this.toast = ''; }, 2400); },

    // ---------------- view helpers ----------------
    gateStyle(status) {
      return {
        pass: { border: 'border-l-emerald-700', dot: 'bg-emerald-700', titleColor: 'text-emerald-800', text: 'PASS / 自动放行', sub: '未命中法定红线，残余风险处于可接受范围' },
        warn: { border: 'border-l-amber-600', dot: 'bg-amber-600', titleColor: 'text-amber-800', text: 'WARN / 警示放行', sub: '允许上线，须在规定期限内闭环缓解计划' },
        block: { border: 'border-l-red-700', dot: 'bg-red-700', titleColor: 'text-red-800', text: 'BLOCK / 阻断合并', sub: '禁止上线，须完成整改或按制度履行审批' },
      }[status] || { border: 'border-l-slate-400', dot: 'bg-slate-400', titleColor: 'text-slate-700', text: '评估中', sub: '' };
    },
    levelClass(level) {
      return {
        low: 'bg-emerald-50 text-emerald-800 border border-emerald-200',
        medium: 'bg-amber-50 text-amber-800 border border-amber-200',
        high: 'bg-orange-50 text-orange-900 border border-orange-300',
        critical: 'bg-red-50 text-red-800 border border-red-300',
      }[level] || 'bg-slate-100 text-slate-700 border border-slate-200';
    },
    cellClass(l, s) {
      const score = l * s;
      if (score >= 13) return 'bg-red-100 text-red-900 border border-red-200';
      if (score >= 9) return 'bg-orange-100 text-orange-900 border border-orange-200';
      if (score >= 5) return 'bg-amber-50 text-amber-900 border border-amber-200';
      return 'bg-emerald-50 text-emerald-900 border border-emerald-200';
    },
    matrixCount(l, s) {
      const key = this.matrixMode === 'residual' ? 'residual_risk' : 'inherent_risk';
      return (this.result?.report.findings || []).filter((f) => f[key].likelihood === l && f[key].severity === s).length;
    },
    get juriResults() { return this.result?.report.threshold.results || []; },
    get matrixCells() {
      const cells = [];
      for (const s of [4, 3, 2, 1]) for (const l of [1, 2, 3, 4]) cells.push({ key: `${l}-${s}`, l, s });
      return cells;
    },
  };
}
