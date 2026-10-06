<script setup lang="ts">
// Quotations app - native pricing module backed by the server-side engine
const props = defineProps<{ page?: string }>();
const emit = defineEmits<{ (e: "nav", k: string): void }>();

const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request, download } = useApi();
const { projects, loadAll } = useData();
const user = useAuth().user;

const view = ref<"list" | "editor" | "detail">("list");
const quotes = ref<any[]>([]);
const catalog = ref<any>(null);
const loading = ref(true);
const search = ref("");
const statusFilter = ref("All");

// editor/detail payload passed to child components
const editing = ref<any>(null);   // { quoteId?, revisionId?, rev?, status?, meta, items, markupPct, vatPct }
const detailId = ref<string | null>(null);

const role = computed(() => user.value?.apps?.quotes?.role || user.value?.apps?.facade?.role || "sales");
const isAdmin = computed(() => user.value?.platformRole === "admin");

const loadCatalog = async () => {
  catalog.value = await request("/api/quotes/catalog");
};

const load = async () => {
  loading.value = true;
  try {
    await loadCatalog();
    quotes.value = await request("/api/quotes");
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  await load();
  if (!projects.value.length) loadAll();
});

const filtered = computed(() =>
  (quotes.value || []).filter((q) => {
    const s = search.value.toLowerCase();
    const hit =
      !q ||
      q.number?.toLowerCase().includes(s) ||
      q.clientName?.toLowerCase().includes(s) ||
      q.projectName?.toLowerCase().includes(s) ||
      q.salesPerson?.toLowerCase().includes(s);
    return hit && (statusFilter.value === "All" || q.status === statusFilter.value);
  })
);

const fmtN = (n: number) => "₦" + Math.round(n || 0).toLocaleString("en-NG");

const blankItem = (): any => ({
  id: Math.random().toString(36).slice(2, 10),
  product: "et_window",
  subTypeId: "etw_fixed",
  width: null, height: null, length: null, qty: 1,
  glassTypeId: "", glassThickness: "", glassColour: "",
  glassDguOuter: "", glassDguInner: "",
  acpPanelId: "", ovGlassRate: null,
  hasMosq: false, hasSubframe: false,
  elements: [], note: "",
});

const openNew = () => {
  const s = catalog.value?.values?.settings || {};
  editing.value = {
    quoteId: null, revisionId: null, rev: 0, status: "draft",
    meta: { projectId: "", clientName: "", clientPhone: "", clientEmail: "", salesPerson: "", notes: "" },
    items: [blankItem()],
    markupPct: s.defaultMarkup ?? 100,
    vatPct: s.vatRate ?? 7.5,
  };
  view.value = "editor";
};

const openEdit = async (q: any) => {
  try {
    const full = await request(`/api/quotes/${q.id}`);
    const latest = full.latest || { items: [], markupPct: 100, vatPct: 7.5, status: "draft" };
    editing.value = {
      quoteId: full.id, revisionId: latest.id, rev: latest.rev, status: latest.status,
      number: full.number,
      meta: {
        projectId: full.projectId || "", clientName: full.clientName || "",
        clientPhone: full.clientPhone || "", clientEmail: full.clientEmail || "",
        salesPerson: full.salesPerson || "", notes: full.notes || "",
      },
      items: JSON.parse(JSON.stringify(latest.items || [])),
      markupPct: latest.markupPct, vatPct: latest.vatPct,
    };
    view.value = "editor";
  } catch (e: any) {
    notify(e.message, "error");
  }
};

const openDetail = (id: string) => {
  detailId.value = id;
  view.value = "detail";
};

const backToList = async () => {
  view.value = "list";
  editing.value = null;
  await load();
};

const del = async (q: any) => {
  if (!confirm(`Delete ${q.number}? This removes all revisions.`)) return;
  try {
    await request(`/api/quotes/${q.id}`, { method: "DELETE" });
    notify(`${q.number} deleted`);
    await load();
  } catch (e: any) {
    notify(e.message, "error");
  }
};

const saveBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
};

const exporting = ref(false);
const exportAll = async () => {
  exporting.value = true;
  try {
    const { blob, filename } = await download("/api/quotes/export/all");
    saveBlob(blob, filename);
    notify("Quotes exported to Excel");
  } catch (e: any) {
    notify(e.message || "Export failed", "error");
  } finally {
    exporting.value = false;
  }
};

const statusChip = (s: string) => {
  const map: any = {
    draft: { bg: "#F3F4F6", fg: "#4B5563", label: "Draft" },
    sent: { bg: "#DBEAFE", fg: "#1D4ED8", label: "Sent" },
    won: { bg: "#DCFCE7", fg: "#15803D", label: "Won" },
    lost: { bg: "#FEE2E2", fg: "#B91C1C", label: "Lost" },
  };
  return map[s] || map.draft;
};

const stats = computed(() => {
  const qs = quotes.value || [];
  const won = qs.filter((q) => q.status === "won");
  return {
    count: qs.length,
    pipeline: qs.filter((q) => ["draft", "sent"].includes(q.status)).reduce((s, q) => s + (q.total || 0), 0),
    wonValue: won.reduce((s, q) => s + (q.total || 0), 0),
    wonCount: won.length,
  };
});

// child components emit these
const saved = async (msg: string) => {
  notify(msg);
  await backToList();
};
const cancelled = () => backToList();
</script>

<template>
  <!-- LIST -->
  <div v-if="view === 'list'" class="wrap">
    <div class="stats">
      <div class="stat"><div class="stat-v">{{ stats.count }}</div><div class="stat-l">Quotes</div></div>
      <div class="stat"><div class="stat-v">{{ fmtN(stats.pipeline) }}</div><div class="stat-l">Open Pipeline</div></div>
      <div class="stat"><div class="stat-v">{{ fmtN(stats.wonValue) }}</div><div class="stat-l">Won Value</div></div>
      <div class="stat"><div class="stat-v">{{ stats.wonCount }}</div><div class="stat-l">Jobs Won</div></div>
    </div>

    <div class="card">
      <div class="card-head">
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
          <input v-model="search" class="inp search" placeholder="Search number, client, project..." />
          <select v-model="statusFilter" class="inp" style="width: 130px">
            <option>All</option><option>draft</option><option>sent</option><option>won</option><option>lost</option>
          </select>
          <button class="btn-export" :disabled="exporting || !quotes.length" @click="exportAll">
            {{ exporting ? "Exporting..." : "⬇ Export" }}
          </button>
        </div>
        <button class="btn-primary" @click="openNew">+ New Quote</button>
      </div>

      <div v-if="loading" class="empty">Loading quotations...</div>
      <div v-else-if="!filtered.length" class="empty">
        <div style="font-size: 30px; margin-bottom: 8px">🧾</div>
        No quotations yet. Create your first quote to price aluminium windows, doors and facades.
      </div>
      <div v-else class="tscroll">
        <table class="tbl">
          <thead>
            <tr>
              <th>Number</th><th>Client</th><th>Project</th><th>Sales</th>
              <th>Status</th><th style="text-align: right">Total</th><th>Updated</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="q in filtered" :key="q.id" class="row" @click="openDetail(q.id)">
              <td class="mono strong">{{ q.number }}</td>
              <td>{{ q.clientName || "N/A" }}</td>
              <td>{{ q.projectName || "N/A" }}</td>
              <td>{{ q.salesPerson || "N/A" }}</td>
              <td>
                <span class="chip" :style="{ background: statusChip(q.status).bg, color: statusChip(q.status).fg }">
                  {{ statusChip(q.status).label }}
                </span>
              </td>
              <td style="text-align: right" class="strong">{{ fmtN(q.total) }}</td>
              <td class="dim">{{ new Date(q.updated).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) }}</td>
              <td style="white-space: nowrap">
                <button class="btn-sm" @click.stop="openEdit(q)">Edit</button>
                <button v-if="isAdmin" class="btn-sm danger" @click.stop="del(q)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- EDITOR -->
  <QuoteEditor
    v-else-if="view === 'editor' && catalog"
    :editing="editing"
    :catalog="catalog"
    :projects="projects"
    @saved="saved"
    @cancel="cancelled"
  />

  <!-- DETAIL -->
  <QuoteDetail
    v-else-if="view === 'detail' && detailId"
    :quote-id="detailId"
    :catalog="catalog"
    @back="backToList"
    @changed="load"
    @edit="openEdit"
  />
</template>

<style scoped>
.wrap { padding: 22px; max-width: 1200px; margin: 0 auto; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.stat { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; }
.stat-v { font-size: 17px; font-weight: 800; color: #0f172a; letter-spacing: -.3px; }
.stat-l { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .8px; color: #94a3b8; margin-top: 3px; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 14px 16px; border-bottom: 1px solid #f1f5f9; flex-wrap: wrap; }
.search { width: 260px; }
.inp { padding: 8px 10px; border: 1px solid #dde4ec; border-radius: 8px; font-family: inherit; font-size: 12.5px; background: #fff; outline: none; }
.inp:focus { border-color: #f59e0b; }
.btn-primary { background: linear-gradient(135deg, #f59e0b, #ea580c); color: #fff; border: none; border-radius: 8px; padding: 9px 16px; font-family: inherit; font-size: 12.5px; font-weight: 700; cursor: pointer; }
.btn-primary:hover { filter: brightness(1.05); }
.btn-export { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 14px; font-family: inherit; font-size: 12.5px; font-weight: 700; color: #475569; cursor: pointer; }
.btn-export:hover:not(:disabled) { border-color: #16a34a; color: #15803d; }
.btn-export:disabled { opacity: .5; cursor: default; }
.empty { padding: 46px 20px; text-align: center; color: #94a3b8; font-size: 13px; }
.tscroll { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th { text-align: left; padding: 10px 14px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .7px; color: #94a3b8; border-bottom: 1px solid #f1f5f9; white-space: nowrap; }
.tbl td { padding: 11px 14px; border-bottom: 1px solid #f8fafc; color: #334155; }
.row { cursor: pointer; }
.row:hover { background: #fffbeb; }
.mono { font-family: ui-monospace, "Courier New", monospace; }
.strong { font-weight: 700; color: #0f172a; }
.dim { color: #94a3b8; font-size: 11.5px; }
.chip { border-radius: 20px; padding: 3px 10px; font-size: 10.5px; font-weight: 700; }
.btn-sm { padding: 5px 10px; border-radius: 6px; border: 1px solid #e2e8f0; background: #fff; color: #475569; font-family: inherit; font-size: 11px; font-weight: 600; cursor: pointer; margin-right: 5px; }
.btn-sm:hover { border-color: #f59e0b; color: #b45309; }
.btn-sm.danger:hover { border-color: #ef4444; color: #ef4444; }
@media (max-width: 860px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .wrap { padding: 14px; }
}
</style>
