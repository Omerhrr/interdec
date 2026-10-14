<script setup lang="ts">
// Reports page - 5 report types + exchange rates + HTML export (mirrors original)
const { shipments, vendors, shippers, projects, vendorName, shipperName, projectName, agentName, costUsd, landedUsd } = useData();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { COMPANIES, STATUS_ORDER, STATUS_LABELS, STATUS_COLORS, fmtDate, fmtEta } = useConstants();

const activeReport = ref<string | null>(null);
const ratesModal = ref(false);
// server-stored rates shared with the dashboard and projects
const { fx, fxLabel } = useData();
const rates = computed(() => fx.value.rates);

const toUsd = (s: any) => (Number(s.value) || 0) * (rates.value[s.currency] ?? 1);
const totalUsd = (list: any[]) => list.reduce((a, s) => a + toUsd(s), 0);
const fmtUsd = (n: number) => `$ ${Math.round(n).toLocaleString()}`;

const reportMeta: Record<string, { icon: string; title: string; desc: string; color: string }> = {
  status: { icon: "chart", title: "Shipments by Status", desc: "All shipments grouped by Order Placed, Under Production, In Transit, Completed", color: "#3b82f6" },
  project: { icon: "clipboard", title: "Shipments by Project", desc: "Shipment breakdown per project with total values", color: "#8b5cf6" },
  company: { icon: "grid", title: "Shipments by Company", desc: "Facade, Davinci and Doortec: shipments and total values", color: "#f59e0b" },
  vendor: { icon: "factory", title: "Shipments by Vendor", desc: "All shipments grouped by vendor with total order values", color: "#10b981" },
  shipper: { icon: "ship", title: "Shipments by Shipper", desc: "Shipper usage and freight costs paid", color: "#06b6d4" },
  costs: { icon: "coins", title: "Landed cost", desc: "Goods + shipping + clearing per shipment, and what's still unpaid", color: "#0f766e" },
  budget: { icon: "trophy", title: "Budget vs actual", desc: "Each project's contract value (won quotes) against what its imports cost", color: "#16a34a" },
  payables: { icon: "alert", title: "Payables", desc: "Everything still owed: vendor balances, unpaid shipping and clearing", color: "#dc2626" },
};
const { request } = useApi();
const budgets = ref<Record<string, any>>({});
watch(() => activeReport.value, (r) => { if (r === "budget") request("/api/projects/budgets").then((b: any) => (budgets.value = b)).catch(() => {}); });
const bRows = computed(() => projects.value.map((p: any) => ({ p, b: budgets.value[p.id] })).filter((x: any) => x.b));
const nShort = (n: number) => { const a = Math.abs(n || 0); return (n < 0 ? "−₦" : "₦") + (a >= 1e9 ? (a / 1e9).toFixed(2) + "B" : a >= 1e6 ? (a / 1e6).toFixed(1) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : Math.round(a)); };
const bSum = (k: string) => bRows.value.reduce((a: number, x: any) => a + (x.b[k] || 0), 0);
// payables: vendor balances + unpaid shipping/clearing
const payRows = computed(() => {
  const out: any[] = [];
  for (const s of shipments.value as any[]) {
    if (s.vendorBalance > 0.005 && s.value) out.push({ s, what: "Vendor", to: vendorName(s.vendorId), amt: `${s.currency} ${Number(s.vendorBalance).toLocaleString()}`, usd: s.vendorBalance * (rates.value[s.currency] ?? 1), due: s.vendorPaymentDue });
    if (s.shippingCost?.total && !s.shippingCost.paid) out.push({ s, what: "Shipping", to: shipperName(s.shipperId), amt: `${s.shippingCost.currency} ${Number(s.shippingCost.total).toLocaleString()}`, usd: costUsd(s.shippingCost), due: true });
    if (s.clearingCost?.total && !s.clearingCost.paid) out.push({ s, what: "Clearing", to: agentName(s.clearingAgentId), amt: `${s.clearingCost.currency} ${Number(s.clearingCost.total).toLocaleString()}`, usd: costUsd(s.clearingCost), due: true });
  }
  return out.sort((a, b) => Number(b.due) - Number(a.due) || b.usd - a.usd);
});
// shipped goods and their costs (landed cost report)
const costRows = computed(() => shipments.value.filter((s: any) => ["in_transit", "completed"].includes(s.status) || s.shippingCost || s.clearingCost));
const costSum = (f: (s: any) => number) => costRows.value.reduce((a: number, s: any) => a + f(s), 0);
const paidChip = (c: any) => (!c?.total ? "" : c.paid ? "Paid" : "Unpaid");

</script>

<template>
  <div class="page">
    <div class="head">
      <h1 class="ph">Reports</h1>
      <div style="display: flex; gap: 8px; align-items: center">
        <button class="btn btn-secondary btn-sm" @click="ratesModal = true"><UiIcon name="coins" :size="14" /> Exchange rates</button>
        <IfExportMenu v-if="!activeReport" kind="report" :params="{ type: 'all' }" label="Export all reports" />
        <button v-if="activeReport" class="btn btn-secondary btn-sm" @click="activeReport = null">← Choose Report</button>
      </div>
    </div>

    <!-- rates banner -->
    <div v-if="activeReport" class="rates-banner">
      Values converted to USD using {{ fxLabel }}:
      {{ Object.entries(rates).filter(([k]) => k !== "USD").map(([k, v]) => `${k}=${v}`).join(" · ") }}
      <button style="background: none; border: none; cursor: pointer; color: #3b82f6; font-weight: 700; font-family: inherit; font-size: 11px; margin-left: 4px" @click="ratesModal = true">Edit</button>
    </div>

    <!-- report picker -->
    <div v-if="!activeReport">
      <p style="margin: 0 0 16px; font-size: 13px; color: #64748b">Select the type of report you'd like to generate:</p>
      <div class="r-grid">
        <button v-for="(m, key) in reportMeta" :key="key" class="r-card" :style="{ border: '1.5px solid #f1f5f9' }" @click="activeReport = key">
          <div class="r-ic" :style="{ background: m.color + '14', color: m.color }"><UiIcon :name="m.icon" :size="20" /></div>
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
          <h2 style="margin: 0; font-size: 17px; font-weight: 700">Shipments by Status</h2>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #64748b">
            {{ shipments.length }} shipments · Total value: <strong class="mono" style="color: #0f172a">{{ fmtUsd(totalUsd(shipments)) }}</strong>
          </p>
        </div>
        <IfExportMenu kind="report" :params="{ type: 'status' }" label="Export report" />
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
          <h3 :style="{ color: STATUS_COLORS[st], fontSize: '13px', margin: '18px 0 8px' }">● {{ STATUS_LABELS[st] }} ({{ shipments.filter((s) => s.status === st).length }})</h3>
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
          <h2 style="margin: 0; font-size: 17px; font-weight: 700">Shipments by Project</h2>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #64748b">{{ projects.length }} projects · {{ shipments.length }} shipments · {{ fmtUsd(totalUsd(shipments)) }}</p>
        </div>
        <IfExportMenu kind="report" :params="{ type: 'project' }" label="Export report" />
      </div>
      <div v-for="p in projects" :key="p.id" style="margin-bottom: 18px">
        <h3 style="font-size: 14px; margin: 0 0 4px">{{ p.name }} <span style="color: #64748b; font-weight: 400; font-size: 12px">{{ p.client }}</span></h3>
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
        <h3 style="font-size: 14px; margin: 0 0 4px">General stock</h3>
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
          <h2 style="margin: 0; font-size: 17px; font-weight: 700">Shipments by Company</h2>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #64748b">Facade, Davinci, Doortec · {{ fmtUsd(totalUsd(shipments)) }}</p>
        </div>
        <IfExportMenu kind="report" :params="{ type: 'company' }" label="Export report" />
      </div>
      <div v-for="c in COMPANIES" :key="c.id" style="margin-bottom: 18px">
        <h3 :style="{ fontSize: '14px', margin: '0 0 4px', color: c.color }">{{ c.name }}</h3>
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
          <h2 style="margin: 0; font-size: 17px; font-weight: 700">Shipments by Vendor</h2>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #64748b">{{ vendors.length }} vendors · {{ fmtUsd(totalUsd(shipments)) }}</p>
        </div>
        <IfExportMenu kind="report" :params="{ type: 'vendor' }" label="Export report" />
      </div>
      <div v-for="v in vendors" :key="v.id" style="margin-bottom: 18px">
        <template v-if="shipments.filter((s) => s.vendorId === v.id).length">
          <h3 style="font-size: 14px; margin: 0 0 4px">{{ v.name }} <span style="color: #64748b; font-weight: 400; font-size: 12px">{{ v.country }} · {{ v.category }}</span></h3>
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
          <h2 style="margin: 0; font-size: 17px; font-weight: 700">Shipments by Shipper</h2>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #64748b">{{ shippers.length }} shippers · {{ fmtUsd(totalUsd(shipments)) }}</p>
        </div>
        <IfExportMenu kind="report" :params="{ type: 'shipper' }" label="Export report" />
      </div>
      <div v-for="sp in shippers" :key="sp.id" style="margin-bottom: 18px">
        <template v-if="shipments.filter((s) => s.shipperId === sp.id).length">
          <h3 style="font-size: 14px; margin: 0 0 4px">{{ sp.name }} <span style="color: #64748b; font-weight: 400; font-size: 12px">{{ sp.country }} · {{ sp.category }}</span></h3>
          <p style="font-size: 12.5px; color: #475569; margin: 0 0 8px">{{ fmtUsd(totalUsd(shipments.filter((s) => s.shipperId === sp.id))) }} · {{ shipments.filter((s) => s.shipperId === sp.id).length }} shipments</p>
          <table class="r-table">
            <thead><tr><th>Ref</th><th>Company</th><th>Description</th><th>Method</th><th>ETA</th><th>Value</th></tr></thead>
            <tbody>
              <tr v-for="s in shipments.filter((x) => x.shipperId === sp.id)" :key="s.id">
                <td class="mono" style="color: #3b82f6; font-weight: 700">{{ s.ref }}</td>
                <td><UiCompanyChip :id="s.companyId" /></td>
                <td>{{ s.description }}</td>
                <td>{{ s.shipMethod || "N/A" }}</td>
                <td>{{ fmtEta(s.eta) || "N/A" }}</td>
                <td class="mono" style="font-weight: 700">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </div>

    <!-- ============ LANDED COST ============ -->
    <div v-else-if="activeReport === 'costs'">
      <div class="r-head">
        <div>
          <h2 style="margin: 0; font-size: 17px; font-weight: 700">Landed cost</h2>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #64748b">{{ costRows.length }} shipped shipments · landed <strong class="mono" style="color: #0f172a">{{ fmtUsd(costSum(landedUsd)) }}</strong></p>
        </div>
        <IfExportMenu kind="report" :params="{ type: 'costs' }" label="Export report" />
      </div>
      <div class="stat4">
        <div class="stat4-card" style="border-top: 3px solid #64748b"><div class="mono" style="font-size: 18px; font-weight: 800">{{ fmtUsd(costSum(toUsd)) }}</div><div style="font-size: 12px; color: #475569; font-weight: 600">Goods</div></div>
        <div class="stat4-card" style="border-top: 3px solid #06b6d4"><div class="mono" style="font-size: 18px; font-weight: 800">{{ fmtUsd(costSum((s) => costUsd(s.shippingCost))) }}</div><div style="font-size: 12px; color: #475569; font-weight: 600">Shipping</div></div>
        <div class="stat4-card" style="border-top: 3px solid #8b5cf6"><div class="mono" style="font-size: 18px; font-weight: 800">{{ fmtUsd(costSum((s) => costUsd(s.clearingCost))) }}</div><div style="font-size: 12px; color: #475569; font-weight: 600">Clearing</div></div>
        <div class="stat4-card" style="border-top: 3px solid #0f766e"><div class="mono" style="font-size: 18px; font-weight: 800; color: #0f766e">{{ fmtUsd(costSum(landedUsd)) }}</div><div style="font-size: 12px; color: #475569; font-weight: 600">Landed cost</div></div>
      </div>
      <div style="overflow-x: auto">
        <table class="r-table">
          <thead><tr><th>Ref</th><th>Description</th><th>Clearing agent</th><th style="text-align: right">Goods</th><th style="text-align: right">Shipping</th><th style="text-align: right">Clearing</th><th style="text-align: right">Landed</th></tr></thead>
          <tbody>
            <tr v-for="s in costRows" :key="s.id">
              <td class="mono" style="color: #3b82f6; font-weight: 700">{{ s.ref }}</td>
              <td>{{ s.description }}</td>
              <td>{{ s.clearingAgentId ? agentName(s.clearingAgentId) : "—" }}</td>
              <td class="mono" style="text-align: right">{{ fmtUsd(toUsd(s)) }}</td>
              <td class="mono" style="text-align: right">
                <template v-if="s.shippingCost?.total">{{ fmtUsd(costUsd(s.shippingCost)) }} <span class="pc" :class="{ un: !s.shippingCost.paid }">{{ paidChip(s.shippingCost) }}</span></template>
                <span v-else style="color: #b45309">to record</span>
              </td>
              <td class="mono" style="text-align: right">
                <template v-if="s.clearingCost?.total">{{ fmtUsd(costUsd(s.clearingCost)) }} <span class="pc" :class="{ un: !s.clearingCost.paid }">{{ paidChip(s.clearingCost) }}</span></template>
                <span v-else style="color: #b45309">to record</span>
              </td>
              <td class="mono" style="text-align: right; font-weight: 800">{{ fmtUsd(landedUsd(s)) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ============ BUDGET VS ACTUAL ============ -->
    <div v-else-if="activeReport === 'budget'">
      <div class="r-head">
        <div>
          <h2 style="margin: 0; font-size: 17px; font-weight: 700">Budget vs actual</h2>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #64748b">Contract {{ nShort(bSum("contract")) }} · spent {{ nShort(bSum("spent")) }} · margin {{ nShort(bSum("contract") - bSum("spent")) }}</p>
        </div>
        <IfExportMenu kind="report" :params="{ type: 'budget' }" label="Export report" />
      </div>
      <div style="overflow-x: auto">
        <table class="r-table">
          <thead><tr><th>Project</th><th>Won quotes</th><th style="text-align: right">Contract</th><th style="text-align: right">Spent</th><th style="text-align: right">Margin</th><th style="text-align: right">Owed to vendors</th></tr></thead>
          <tbody>
            <tr v-for="x in bRows" :key="x.p.id">
              <td><strong>{{ x.p.name }}</strong><div style="font-size: 11.5px; color: #64748b">{{ x.p.client }}</div></td>
              <td class="mono" style="font-size: 12px">{{ x.b.wonQuotes.map((q: any) => q.number).join(", ") || "—" }}</td>
              <td class="mono" style="text-align: right">{{ x.b.contract ? nShort(x.b.contract) : "—" }}</td>
              <td class="mono" style="text-align: right">{{ nShort(x.b.spent) }}<div v-if="x.b.usedPct !== null" style="font-size: 11px; color: #64748b">{{ x.b.usedPct }}%</div></td>
              <td class="mono" style="text-align: right; font-weight: 800" :style="{ color: !x.b.contract ? '#64748b' : x.b.margin < 0 ? '#b91c1c' : '#047857' }">{{ x.b.contract ? `${nShort(x.b.margin)} (${x.b.marginPct}%)` : "—" }}</td>
              <td class="mono" style="text-align: right" :style="{ color: x.b.vendorOwed > 0 ? '#b45309' : undefined }">{{ nShort(x.b.vendorOwed) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ============ PAYABLES ============ -->
    <div v-else-if="activeReport === 'payables'">
      <div class="r-head">
        <div>
          <h2 style="margin: 0; font-size: 17px; font-weight: 700">Payables</h2>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #64748b">{{ payRows.length }} unpaid items · {{ fmtUsd(payRows.reduce((a, r) => a + r.usd, 0)) }} · due now {{ fmtUsd(payRows.filter((r) => r.due).reduce((a, r) => a + r.usd, 0)) }}</p>
        </div>
        <IfExportMenu kind="report" :params="{ type: 'payables' }" label="Export report" />
      </div>
      <p v-if="!payRows.length" class="r-empty">Nothing owed. Everything is paid.</p>
      <div v-else style="overflow-x: auto">
        <table class="r-table">
          <thead><tr><th>Shipment</th><th>Owed for</th><th>To</th><th style="text-align: right">Amount</th><th style="text-align: right">USD</th><th></th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in payRows" :key="i">
              <td class="mono" style="color: #3b82f6; font-weight: 700">{{ r.s.ref }}</td>
              <td>{{ r.what }}</td>
              <td>{{ r.to }}</td>
              <td class="mono" style="text-align: right">{{ r.amt }}</td>
              <td class="mono" style="text-align: right; font-weight: 700">{{ fmtUsd(r.usd) }}</td>
              <td><span v-if="r.due" class="pc un">Due now</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <IfFxRatesModal v-if="ratesModal" @close="ratesModal = false" />
  </div>
</template>

<style scoped>
.r-empty { font-size: 13px; color: #047857; background: #ecfdf5; border-radius: 8px; padding: 12px; }
.pc { font-family: inherit; font-size: 10px; font-weight: 800; border-radius: 20px; padding: 1px 6px; background: #dcfce7; color: #166534; margin-left: 4px; }
.pc.un { background: #fef3c7; color: #92400e; }
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; animation: fadeIn .3s; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
.ph { font-size: 20px; font-weight: 800; }
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
.r-ic { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.r-title { font-size: 14px; font-weight: 700; color: #0f172a; margin-bottom: 3px; }
.r-desc { font-size: 12px; color: #64748b; line-height: 1.4; }
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
