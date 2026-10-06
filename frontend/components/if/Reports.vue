<script setup lang="ts">
// Reports page - 5 report types + exchange rates + HTML export (mirrors original)
const { shipments, vendors, shippers, projects, vendorName, shipperName, projectName } = useData();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { COMPANIES, STATUS_ORDER, STATUS_LABELS, STATUS_COLORS, DEFAULT_RATES, fmtDate } = useConstants();

const activeReport = ref<string | null>(null);
const ratesModal = ref(false);
const rates = ref<Record<string, number>>({ ...DEFAULT_RATES });

const toUsd = (s: any) => (s.value || 0) * (rates.value[s.currency] || 1);
const totalUsd = (list: any[]) => list.reduce((a, s) => a + toUsd(s), 0);
const fmtUsd = (n: number) => `$ ${Math.round(n).toLocaleString()}`;

const reportMeta: Record<string, { icon: string; title: string; desc: string; color: string }> = {
  status: { icon: "📊", title: "Shipments by Status", desc: "All shipments grouped by Order Placed, Under Production, In Transit, Completed", color: "#3b82f6" },
  project: { icon: "📋", title: "Shipments by Project", desc: "Shipment breakdown per project with total values", color: "#8b5cf6" },
  company: { icon: "🏢", title: "Shipments by Company", desc: "Facade, Davinci and Doortec: shipments and total values", color: "#f59e0b" },
  vendor: { icon: "🏭", title: "Shipments by Vendor", desc: "All shipments grouped by vendor with total order values", color: "#10b981" },
  shipper: { icon: "🚢", title: "Shipments by Shipper", desc: "Shipper usage and freight costs paid", color: "#06b6d4" },
};

const tableRow = (cells: string[], head = false) =>
  `<tr>${cells
    .map(
      (c) =>
        `<${head ? "th" : "td"} style="padding:10px 14px;text-align:left;border-bottom:1px solid #e2e8f0;${head ? "font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;background:#f8fafc;" : ""}">${c}</${head ? "th" : "td"}>`
    )
    .join("")}</tr>`;

const buildHtml = (type: string) => {
  const titles: Record<string, string> = {
    status: "Shipments by Status", project: "Shipments by Project", company: "Shipments by Company",
    vendor: "Shipments by Vendor", shipper: "Shipments by Shipper",
  };
  const date = new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  let body = "";

  if (type === "status") {
    const total = totalUsd(shipments.value);
    body += `<div style="display:flex;gap:16px;margin-bottom:24px">${STATUS_ORDER.map((st) => {
      const list = shipments.value.filter((s) => s.status === st);
      return `<div style="flex:1;padding:16px;border-radius:10px;border-top:4px solid ${STATUS_COLORS[st]};background:${STATUS_COLORS[st]}08">
        <div style="font-size:28px;font-weight:800;color:${STATUS_COLORS[st]}">${list.length}</div>
        <div style="font-size:12px;font-weight:600;color:#475569">${STATUS_LABELS[st]}</div>
        <div style="font-size:13px;color:#64748b;margin-top:4px">${fmtUsd(totalUsd(list))}</div></div>`;
    }).join("")}</div>`;
    body += `<p style="color:#64748b;font-size:13px;margin-bottom:20px">Total shipments: <strong>${shipments.value.length}</strong> · Total value: <strong>${fmtUsd(total)}</strong></p>`;
    STATUS_ORDER.forEach((st) => {
      const list = shipments.value.filter((s) => s.status === st);
      if (!list.length) return;
      body += `<h3 style="color:${STATUS_COLORS[st]};font-size:14px;margin:20px 0 8px">● ${STATUS_LABELS[st]} (${list.length})</h3>
        <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px">
        ${tableRow(["Ref", "Company", "Description", "Vendor", "Value"], true)}
        ${list.map((s) => tableRow([s.ref, COMPANIES.find((c) => c.id === s.companyId)?.name || "", s.description, vendorName(s.vendorId), `${s.currency || "USD"} ${(s.value || 0).toLocaleString()}`])).join("")}
        </table>`;
    });
  } else if (type === "project") {
    const total = totalUsd(shipments.value);
    body += `<p style="color:#64748b;font-size:13px;margin-bottom:20px">Total: <strong>${shipments.value.length} shipments</strong> · Value: <strong>${fmtUsd(total)}</strong></p>`;
    projects.value.forEach((p) => {
      const list = shipments.value.filter((s) => s.projectId === p.id);
      if (!list.length) return;
      body += `<h3 style="font-size:14px;margin:20px 0 4px">${p.name} <span style="color:#94a3b8;font-weight:400;font-size:12px">${p.client || ""}</span></h3>
        <p style="font-size:13px;color:#475569;margin:0 0 8px">${fmtUsd(totalUsd(list))} · ${list.length} shipments</p>
        <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px">
        ${tableRow(["Ref", "Company", "Description", "Status", "Value"], true)}
        ${list.map((s) => tableRow([s.ref, COMPANIES.find((c) => c.id === s.companyId)?.name || "", s.description, STATUS_LABELS[s.status], `${s.currency || "USD"} ${(s.value || 0).toLocaleString()}`])).join("")}
        </table>`;
    });
    const stock = shipments.value.filter((s) => !s.projectId);
    if (stock.length) {
      body += `<h3 style="font-size:14px;margin:20px 0 4px">📦 General Stock</h3>
        <p style="font-size:13px;color:#475569;margin:0 0 8px">${fmtUsd(totalUsd(stock))} · ${stock.length} shipments</p>
        <table style="width:100%;border-collapse:collapse;font-size:12px">
        ${tableRow(["Ref", "Company", "Description", "Status", "Value"], true)}
        ${stock.map((s) => tableRow([s.ref, COMPANIES.find((c) => c.id === s.companyId)?.name || "", s.description, STATUS_LABELS[s.status], `${s.currency || "USD"} ${(s.value || 0).toLocaleString()}`])).join("")}
        </table>`;
    }
  } else if (type === "company") {
    COMPANIES.forEach((c) => {
      const list = shipments.value.filter((s) => s.companyId === c.id);
      if (!list.length) return;
      const active = list.filter((s) => s.status !== "completed").length;
      body += `<h3 style="font-size:14px;margin:20px 0 4px;color:${c.color}">${c.name}</h3>
        <p style="font-size:13px;color:#475569;margin:0 0 8px">${fmtUsd(totalUsd(list))} · ${list.length} shipments (${active} active)</p>
        <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px">
        ${tableRow(["Ref", "Description", "Status", "Project", "Value"], true)}
        ${list.map((s) => tableRow([s.ref, s.description, STATUS_LABELS[s.status], projectName(s.projectId), `${s.currency || "USD"} ${(s.value || 0).toLocaleString()}`])).join("")}
        </table>`;
    });
  } else if (type === "vendor") {
    vendors.value.forEach((v) => {
      const list = shipments.value.filter((s) => s.vendorId === v.id);
      if (!list.length) return;
      body += `<h3 style="font-size:14px;margin:20px 0 4px">${v.name} <span style="color:#94a3b8;font-weight:400;font-size:12px">${v.country || ""} · ${v.category || ""}</span></h3>
        <p style="font-size:13px;color:#475569;margin:0 0 8px">${fmtUsd(totalUsd(list))} · ${list.length} shipments</p>
        <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px">
        ${tableRow(["Ref", "Company", "Description", "Status", "Value"], true)}
        ${list.map((s) => tableRow([s.ref, COMPANIES.find((c) => c.id === s.companyId)?.name || "", s.description, STATUS_LABELS[s.status], `${s.currency || "USD"} ${(s.value || 0).toLocaleString()}`])).join("")}
        </table>`;
    });
  } else if (type === "shipper") {
    shippers.value.forEach((sp) => {
      const list = shipments.value.filter((s) => s.shipperId === sp.id);
      if (!list.length) return;
      body += `<h3 style="font-size:14px;margin:20px 0 4px">${sp.name} <span style="color:#94a3b8;font-weight:400;font-size:12px">${sp.country || ""} · ${sp.category || ""}</span></h3>
        <p style="font-size:13px;color:#475569;margin:0 0 8px">${fmtUsd(totalUsd(list))} · ${list.length} shipments</p>
        <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:8px">
        ${tableRow(["Ref", "Company", "Description", "Method", "ETA", "Value"], true)}
        ${list.map((s) => tableRow([s.ref, COMPANIES.find((c) => c.id === s.companyId)?.name || "", s.description, s.shipMethod || "N/A", s.eta || "N/A", `${s.currency || "USD"} ${(s.value || 0).toLocaleString()}`])).join("")}
        </table>`;
    });
  }

  return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Interdec ${titles[type]}</title></head>
  <body style="font-family:'DM Sans',system-ui,sans-serif;color:#0f172a;max-width:900px;margin:0 auto;padding:40px 24px">
    <h1 style="font-size:22px;margin:0 0 4px">${reportMeta[type].icon} ${titles[type]}</h1>
    <p style="color:#94a3b8;font-size:12px;margin:0 0 12px">Interdec Platform · Generated ${date} · Values converted to USD</p>
    <p style="color:#64748b;font-size:11px;margin:0 0 24px">💱 Rates: ${Object.entries(rates.value).filter(([k]) => k !== "USD").map(([k, v]) => `${k}=${v}`).join(" · ")}</p>
    ${body}
  </body></html>`;
};

const exportReport = (type: string) => {
  const html = buildHtml(type);
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `interdec-report-${type}-${new Date().toISOString().slice(0, 10)}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 300);
  notify("Report exported");
};
</script>

<template>
  <div class="page">
    <div class="head">
      <h2>Reports</h2>
      <div style="display: flex; gap: 8px; align-items: center">
        <button class="btn btn-ghost btn-sm" style="font-size: 11px; color: #94a3b8" @click="ratesModal = true">💱 Exchange Rates</button>
        <button v-if="activeReport" class="btn btn-secondary btn-sm" @click="activeReport = null">← Choose Report</button>
      </div>
    </div>

    <!-- rates banner -->
    <div v-if="activeReport" class="rates-banner">
      💱 Values converted to USD ·
      {{ Object.entries(rates).filter(([k]) => k !== "USD").map(([k, v]) => `${k}=${v}`).join(" · ") }}
      <button style="background: none; border: none; cursor: pointer; color: #3b82f6; font-weight: 700; font-family: inherit; font-size: 11px; margin-left: 4px" @click="ratesModal = true">Edit</button>
    </div>

    <!-- report picker -->
    <div v-if="!activeReport">
      <p style="margin: 0 0 16px; font-size: 13px; color: #64748b">Select the type of report you'd like to generate:</p>
      <div class="r-grid">
        <button v-for="(m, key) in reportMeta" :key="key" class="r-card" :style="{ border: '1.5px solid #f1f5f9' }" @click="activeReport = key">
          <div class="r-ic" :style="{ background: m.color + '12', color: m.color }">{{ m.icon }}</div>
          <div>
            <div class="r-title">{{ m.title }}</div>
            <div class="r-desc">{{ m.desc }}</div>
          </div>
        </button>
      </div>
    </div>

    <!-- ============ STATUS REPORT ============ -->
    <div v-else-if="activeReport === 'status'">
      <div class="r-head">
        <div>
          <h3 style="margin: 0; font-size: 17px; font-weight: 700">📊 Shipments by Status</h3>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #94a3b8">
            {{ shipments.length }} shipments · Total value: <strong class="mono" style="color: #0f172a">{{ fmtUsd(totalUsd(shipments)) }}</strong>
          </p>
        </div>
        <button class="btn btn-accent btn-sm" @click="exportReport('status')">📄 Export PDF</button>
      </div>
      <div class="stat4">
        <div v-for="st in STATUS_ORDER" :key="st" class="stat4-card" :style="{ borderTop: `3px solid ${STATUS_COLORS[st]}` }">
          <div class="mono" style="font-size: 24px; font-weight: 800" :style="{ color: STATUS_COLORS[st] }">
            {{ shipments.filter((s) => s.status === st).length }}
          </div>
          <div style="font-size: 11px; font-weight: 600; color: #475569">{{ STATUS_LABELS[st] }}</div>
          <div style="font-size: 12px; color: #64748b; margin-top: 3px">{{ fmtUsd(totalUsd(shipments.filter((s) => s.status === st))) }}</div>
        </div>
      </div>
      <template v-for="st in STATUS_ORDER" :key="st">
        <template v-if="shipments.filter((s) => s.status === st).length">
          <h4 :style="{ color: STATUS_COLORS[st], fontSize: '13px', margin: '18px 0 8px' }">● {{ STATUS_LABELS[st] }} ({{ shipments.filter((s) => s.status === st).length }})</h4>
          <table class="r-table">
            <thead><tr><th>Ref</th><th>Company</th><th>Description</th><th>Vendor</th><th>Value</th></tr></thead>
            <tbody>
              <tr v-for="s in shipments.filter((x) => x.status === st)" :key="s.id">
                <td class="mono" style="color: #3b82f6; font-weight: 700">{{ s.ref }}</td>
                <td><UiCompanyChip :id="s.companyId" /></td>
                <td>{{ s.description }}</td>
                <td>{{ vendorName(s.vendorId) }}</td>
                <td class="mono" style="font-weight: 700">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </template>
    </div>

    <!-- ============ PROJECT REPORT ============ -->
    <div v-else-if="activeReport === 'project'">
      <div class="r-head">
        <div>
          <h3 style="margin: 0; font-size: 17px; font-weight: 700">📋 Shipments by Project</h3>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #94a3b8">{{ projects.length }} projects · {{ shipments.length }} shipments · {{ fmtUsd(totalUsd(shipments)) }}</p>
        </div>
        <button class="btn btn-accent btn-sm" @click="exportReport('project')">📄 Export PDF</button>
      </div>
      <div v-for="p in projects" :key="p.id" style="margin-bottom: 18px">
        <h4 style="font-size: 14px; margin: 0 0 4px">{{ p.name }} <span style="color: #94a3b8; font-weight: 400; font-size: 12px">{{ p.client }}</span></h4>
        <p style="font-size: 12.5px; color: #475569; margin: 0 0 8px">
          {{ fmtUsd(totalUsd(shipments.filter((s) => s.projectId === p.id))) }} · {{ shipments.filter((s) => s.projectId === p.id).length }} shipments
        </p>
        <table v-if="shipments.filter((s) => s.projectId === p.id).length" class="r-table">
          <thead><tr><th>Ref</th><th>Company</th><th>Description</th><th>Status</th><th>Value</th></tr></thead>
          <tbody>
            <tr v-for="s in shipments.filter((x) => x.projectId === p.id)" :key="s.id">
              <td class="mono" style="color: #3b82f6; font-weight: 700">{{ s.ref }}</td>
              <td><UiCompanyChip :id="s.companyId" /></td>
              <td>{{ s.description }}</td>
              <td><UiStatusChip :status="s.status" /></td>
              <td class="mono" style="font-weight: 700">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="shipments.filter((s) => !s.projectId).length">
        <h4 style="font-size: 14px; margin: 0 0 4px">📦 General Stock</h4>
        <p style="font-size: 12.5px; color: #475569; margin: 0 0 8px">{{ fmtUsd(totalUsd(shipments.filter((s) => !s.projectId))) }} · {{ shipments.filter((s) => !s.projectId).length }} shipments</p>
        <table class="r-table">
          <thead><tr><th>Ref</th><th>Company</th><th>Description</th><th>Status</th><th>Value</th></tr></thead>
          <tbody>
            <tr v-for="s in shipments.filter((x) => !x.projectId)" :key="s.id">
              <td class="mono" style="color: #3b82f6; font-weight: 700">{{ s.ref }}</td>
              <td><UiCompanyChip :id="s.companyId" /></td>
              <td>{{ s.description }}</td>
              <td><UiStatusChip :status="s.status" /></td>
              <td class="mono" style="font-weight: 700">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ============ COMPANY REPORT ============ -->
    <div v-else-if="activeReport === 'company'">
      <div class="r-head">
        <div>
          <h3 style="margin: 0; font-size: 17px; font-weight: 700">🏢 Shipments by Company</h3>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #94a3b8">Facade, Davinci, Doortec · {{ fmtUsd(totalUsd(shipments)) }}</p>
        </div>
        <button class="btn btn-accent btn-sm" @click="exportReport('company')">📄 Export PDF</button>
      </div>
      <div v-for="c in COMPANIES" :key="c.id" style="margin-bottom: 18px">
        <h4 :style="{ fontSize: '14px', margin: '0 0 4px', color: c.color }">{{ c.name }}</h4>
        <p style="font-size: 12.5px; color: #475569; margin: 0 0 8px">
          {{ fmtUsd(totalUsd(shipments.filter((s) => s.companyId === c.id))) }} ·
          {{ shipments.filter((s) => s.companyId === c.id).length }} shipments
          ({{ shipments.filter((s) => s.companyId === c.id && s.status !== "completed").length }} active)
        </p>
        <table v-if="shipments.filter((s) => s.companyId === c.id).length" class="r-table">
          <thead><tr><th>Ref</th><th>Description</th><th>Status</th><th>Project</th><th>Value</th></tr></thead>
          <tbody>
            <tr v-for="s in shipments.filter((x) => x.companyId === c.id)" :key="s.id">
              <td class="mono" style="color: #3b82f6; font-weight: 700">{{ s.ref }}</td>
              <td>{{ s.description }}</td>
              <td><UiStatusChip :status="s.status" /></td>
              <td>{{ projectName(s.projectId) }}</td>
              <td class="mono" style="font-weight: 700">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ============ VENDOR REPORT ============ -->
    <div v-else-if="activeReport === 'vendor'">
      <div class="r-head">
        <div>
          <h3 style="margin: 0; font-size: 17px; font-weight: 700">🏭 Shipments by Vendor</h3>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #94a3b8">{{ vendors.length }} vendors · {{ fmtUsd(totalUsd(shipments)) }}</p>
        </div>
        <button class="btn btn-accent btn-sm" @click="exportReport('vendor')">📄 Export PDF</button>
      </div>
      <div v-for="v in vendors" :key="v.id" style="margin-bottom: 18px">
        <template v-if="shipments.filter((s) => s.vendorId === v.id).length">
          <h4 style="font-size: 14px; margin: 0 0 4px">{{ v.name }} <span style="color: #94a3b8; font-weight: 400; font-size: 12px">{{ v.country }} · {{ v.category }}</span></h4>
          <p style="font-size: 12.5px; color: #475569; margin: 0 0 8px">{{ fmtUsd(totalUsd(shipments.filter((s) => s.vendorId === v.id))) }} · {{ shipments.filter((s) => s.vendorId === v.id).length }} shipments</p>
          <table class="r-table">
            <thead><tr><th>Ref</th><th>Company</th><th>Description</th><th>Status</th><th>Value</th></tr></thead>
            <tbody>
              <tr v-for="s in shipments.filter((x) => x.vendorId === v.id)" :key="s.id">
                <td class="mono" style="color: #3b82f6; font-weight: 700">{{ s.ref }}</td>
                <td><UiCompanyChip :id="s.companyId" /></td>
                <td>{{ s.description }}</td>
                <td><UiStatusChip :status="s.status" /></td>
                <td class="mono" style="font-weight: 700">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </div>

    <!-- ============ SHIPPER REPORT ============ -->
    <div v-else-if="activeReport === 'shipper'">
      <div class="r-head">
        <div>
          <h3 style="margin: 0; font-size: 17px; font-weight: 700">🚢 Shipments by Shipper</h3>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #94a3b8">{{ shippers.length }} shippers · {{ fmtUsd(totalUsd(shipments)) }}</p>
        </div>
        <button class="btn btn-accent btn-sm" @click="exportReport('shipper')">📄 Export PDF</button>
      </div>
      <div v-for="sp in shippers" :key="sp.id" style="margin-bottom: 18px">
        <template v-if="shipments.filter((s) => s.shipperId === sp.id).length">
          <h4 style="font-size: 14px; margin: 0 0 4px">{{ sp.name }} <span style="color: #94a3b8; font-weight: 400; font-size: 12px">{{ sp.country }} · {{ sp.category }}</span></h4>
          <p style="font-size: 12.5px; color: #475569; margin: 0 0 8px">{{ fmtUsd(totalUsd(shipments.filter((s) => s.shipperId === sp.id))) }} · {{ shipments.filter((s) => s.shipperId === sp.id).length }} shipments</p>
          <table class="r-table">
            <thead><tr><th>Ref</th><th>Company</th><th>Description</th><th>Method</th><th>ETA</th><th>Value</th></tr></thead>
            <tbody>
              <tr v-for="s in shipments.filter((x) => x.shipperId === sp.id)" :key="s.id">
                <td class="mono" style="color: #3b82f6; font-weight: 700">{{ s.ref }}</td>
                <td><UiCompanyChip :id="s.companyId" /></td>
                <td>{{ s.description }}</td>
                <td>{{ s.shipMethod || "N/A" }}</td>
                <td>{{ s.eta || "N/A" }}</td>
                <td class="mono" style="font-weight: 700">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </div>

    <!-- Exchange rates modal -->
    <UiAppModal :open="ratesModal" title="💱 Exchange Rates to USD" :width="400" @close="ratesModal = false">
      <p style="margin: 0 0 14px; font-size: 12.5px; color: #64748b">
        Set the conversion rate for each currency to USD. These rates are used to calculate consolidated dollar values in reports.
      </p>
      <div style="display: grid; gap: 8px">
        <div v-for="(r, k) in rates" :key="k" style="display: flex; align-items: center; gap: 10px">
          <span class="mono" style="font-size: 12.5px; font-weight: 700; color: #334155; width: 40px; flex-shrink: 0">{{ k }}</span>
          <span style="font-size: 11px; color: #94a3b8">1 {{ k }} =</span>
          <input v-model.number="rates[k]" type="number" step="0.0001" class="inp mono" style="flex: 1; padding: 7px 10px" :disabled="k === 'USD'" />
          <span style="font-size: 11px; color: #94a3b8">USD</span>
        </div>
      </div>
      <div style="display: flex; gap: 8px; justify-content: space-between; margin-top: 16px">
        <button class="btn btn-ghost btn-sm" @click="rates = { ...DEFAULT_RATES }">Reset Defaults</button>
        <button class="btn btn-accent" @click="ratesModal = false; notify('Rates updated')">Apply</button>
      </div>
    </UiAppModal>
  </div>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; animation: fadeIn .3s; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
h2 { font-size: 20px; font-weight: 800; }
.rates-banner {
  display: flex; align-items: center; gap: 6px; padding: 6px 12px; flex-wrap: wrap;
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 7px;
  font-size: 11px; color: #92400e; margin-bottom: 14px;
}
.r-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 800px) { .r-grid { grid-template-columns: 1fr; } }
.r-card {
  background: #fff; border-radius: 12px; padding: 20px; cursor: pointer; text-align: left;
  font-family: inherit; transition: all .15s; display: flex; gap: 14px; align-items: flex-start;
}
.r-card:hover { border-color: #93c5fd; background: #fafbff; }
.r-ic { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; }
.r-title { font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 3px; }
.r-desc { font-size: 12px; color: #94a3b8; line-height: 1.4; }
.r-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 10px; flex-wrap: wrap; }
.stat4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
@media (max-width: 800px) { .stat4 { grid-template-columns: 1fr 1fr; } }
.stat4-card { background: #fff; border-radius: 10px; padding: 14px 16px; border: 1px solid #f1f5f9; }
.r-table { width: 100%; border-collapse: collapse; font-size: 12px; background: #fff; border-radius: 8px; overflow: hidden; }
.r-table th {
  padding: 10px 14px; text-align: left; font-size: 10px; font-weight: 700; color: #64748b;
  text-transform: uppercase; background: #f8fafc; border-bottom: 1px solid #e2e8f0;
}
.r-table td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #f1f5f9; }
</style>
