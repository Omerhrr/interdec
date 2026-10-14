<script setup lang="ts">
// Quotations app - native pricing module backed by the server-side engine
// The URL decides the view: /platform/quotes, /quotes/new, /quotes/<id>, /quotes/<id>/edit
const props = defineProps<{ routeView?: string; routeId?: string | null }>();
const router = useRouter();
const route = useRoute();

const notify = inject<(m: string, t?: string) => void>("notify")!;
const { confirm } = useConfirm();
const { request, download } = useApi();
const { projects, loadAll } = useData();
const user = useAuth().user;

const view = computed<"list" | "editor" | "detail">(() =>
  props.routeView === "new" || props.routeView === "edit" ? "editor" : props.routeView === "detail" ? "detail" : "list"
);
const quotes = ref<any[]>([]);
const catalog = ref<any>(null);
const loading = ref(true);
// list filters live in the URL query: they survive Back/refresh and can be shared
const qp = (k: string, d: string) => (typeof route.query[k] === "string" ? (route.query[k] as string) : d);
const search = ref(qp("q", ""));
const statusFilter = ref(qp("status", "All"));

// editor/detail payload passed to child components
const editing = ref<any>(null);   // { quoteId?, revisionId?, rev?, status?, meta, items, markupPct, vatPct }
const detailId = computed(() => (view.value === "detail" ? props.routeId || null : null));

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

const sortBy = ref(qp("sort", "updated"));
const listQuery = computed(() => {
  const q: Record<string, string> = {};
  if (search.value) q.q = search.value;
  if (statusFilter.value !== "All") q.status = statusFilter.value;
  if (sortBy.value !== "updated") q.sort = sortBy.value;
  return q;
});
watch(listQuery, (q) => { if (view.value === "list") router.replace({ query: q }); });
// totals in naira so quotes in different currencies can be added and compared
const ngnOf = (q: any) => Number(q?.totalNgn ?? (q?.total || 0) * (q?.fxRate || 1)) || 0;
const mixed = computed(() => quotes.value.some((q: any) => (q.currency || "NGN") !== "NGN"));
const SORTS: Record<string, (a: any, b: any) => number> = {
  updated: (a, b) => (b.updated || 0) - (a.updated || 0),
  total: (a, b) => ngnOf(b) - ngnOf(a),
  number: (a, b) => String(b.number).localeCompare(String(a.number)),
};
const filtered = computed(() =>
  [...(quotes.value || [])].sort(SORTS[sortBy.value]).filter((q) => {
    const s = search.value.toLowerCase();
    const hit =
      !s ||
      q.number?.toLowerCase().includes(s) ||
      q.clientName?.toLowerCase().includes(s) ||
      q.projectName?.toLowerCase().includes(s) ||
      q.salesPerson?.toLowerCase().includes(s);
    return hit && (statusFilter.value === "All" || q.status === statusFilter.value);
  })
);

const money = useMoney();
const fmtN = (n: number, code = "NGN") => money.fmt(n, code);

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

const openNew = () => router.push("/platform/quotes/new");
const startNew = () => {
  const s = catalog.value?.values?.settings || {};
  editing.value = {
    quoteId: null, revisionId: null, rev: 0, status: "draft",
    meta: { projectId: "", clientName: "", clientPhone: "", clientEmail: "", salesPerson: "", notes: "" },
    items: [blankItem()],
    markupPct: s.defaultMarkup ?? 100,
    vatPct: s.vatRate ?? 7.5,
    currency: "NGN", fxRate: 1,
  };
};

const openEdit = (q: any) => router.push(`/platform/quotes/${q.id}/edit`);
const startEdit = async (id: string) => {
  editing.value = null;
  try {
    const full = await request(`/api/quotes/${id}`);
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
      currency: latest.currency || "NGN", fxRate: latest.fxRate || 1,
    };
  } catch (e: any) {
    notify(e.message, "error");
    router.replace("/platform/quotes");
  }
};

const openDetail = (id: string) => router.push(`/platform/quotes/${id}`);
const backToList = () => router.push({ path: "/platform/quotes", query: listQuery.value });

// prepare the editor whenever the URL asks for it
watch(
  () => [props.routeView, props.routeId, catalog.value] as const,
  ([v, id, cat], old) => {
    if (v === "new" && cat && !editing.value?.__new) { startNew(); editing.value.__new = true; }
    else if (v === "edit" && id && editing.value?.quoteId !== id) startEdit(id);
    else if (v !== "new" && v !== "edit") editing.value = null;
    // returning to the list refreshes it (the first load happens on mount)
    if (old && (v === "list" || !v) && old[0] !== v) load();
    // leaving the rate card: pick up any new glass, panels or charges
    else if (old && old[0] === "rates" && v !== "rates") loadCatalog().catch(() => {});
  },
  { immediate: true }
);

const del = async (q: any) => {
  if (!(await confirm({ title: `Delete ${q.number}?`, message: `All ${q.revisions?.length || 1} revision(s) for ${q.clientName || "this client"} are deleted. This cannot be undone.`, confirmLabel: "Delete quote", danger: true }))) return;
  try {
    await request(`/api/quotes/${q.id}`, { method: "DELETE" });
    notify(`${q.number} deleted`);
    await load();
  } catch (e: any) {
    notify(e.message, "error");
  }
};

const { saveBlob } = useApi();
const rowMenu = (q: any) => [
  { label: "Edit quote", icon: "edit", onClick: () => openEdit(q) },
  ...(isAdmin.value ? [{ label: "Delete quote", icon: "trash", danger: true, onClick: () => del(q) }] : []),
];
const fmtD = (ms: number) => new Date(ms).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });

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
    pipeline: qs.filter((q) => ["draft", "sent"].includes(q.status)).reduce((s, q) => s + ngnOf(q), 0),
    wonValue: won.reduce((s, q) => s + ngnOf(q), 0),
    wonCount: won.length,
  };
});

// child components emit these: after saving, show the quote that was saved
const saved = async (msg: string, id?: string) => {
  notify(msg);
  editing.value = null;
  if (id) router.replace(`/platform/quotes/${id}`);
  else backToList();
};
const cancelled = () => (props.routeId ? router.push(`/platform/quotes/${props.routeId}`) : backToList());
</script>

<template>
  <!-- LIST -->
  <div v-if="view === 'list'" class="wrap">
    <div class="phead">
      <h1 class="ptitle">Quotations</h1>
      <button class="btn-primary fab-m" @click="openNew"><UiIcon name="plus" :size="15" /> New quote</button>
    </div>

    <div class="stats">
      <div class="stat"><div class="stat-v">{{ stats.count }}</div><div class="stat-l">Quotes</div></div>
      <div class="stat"><div class="stat-v">{{ fmtN(stats.pipeline) }}</div><div class="stat-l">Open pipeline<span v-if="mixed"> (in ₦)</span></div></div>
      <div class="stat"><div class="stat-v">{{ fmtN(stats.wonValue) }}</div><div class="stat-l">Won value<span v-if="mixed"> (in ₦)</span></div></div>
      <div class="stat"><div class="stat-v">{{ stats.wonCount }}</div><div class="stat-l">Jobs won</div></div>
    </div>

    <div class="card">
      <div class="card-head">
        <label class="searchw">
          <UiIcon name="search" :size="14" class="sic" />
          <input v-model="search" class="inp search" placeholder="Search number, client, project or sales person" aria-label="Search quotes" />
        </label>
        <select v-model="statusFilter" class="inp" aria-label="Status">
          <option value="All">All statuses</option>
          <option value="draft">Draft</option><option value="sent">Sent</option><option value="won">Won</option><option value="lost">Lost</option>
        </select>
        <select v-model="sortBy" class="inp" aria-label="Sort">
          <option value="updated">Recently updated</option>
          <option value="total">Highest total</option>
          <option value="number">Newest number</option>
        </select>
        <button class="btn-export" :disabled="exporting || !quotes.length" @click="exportAll">
          <UiIcon name="download" :size="14" /> {{ exporting ? "Exporting…" : "Export" }}
        </button>
      </div>
      <div class="count">{{ filtered.length === quotes.length ? `${quotes.length} quotes` : `${filtered.length} of ${quotes.length} quotes` }}</div>

      <div v-if="loading && !quotes.length" class="skel-list" aria-busy="true" aria-label="Loading quotations">
        <div v-for="n in 4" :key="n" class="skel-row"><div class="skel" style="width: 14%" /><div class="skel" style="width: 26%" /><div class="skel" style="width: 18%" /><div class="skel" style="width: 12%" /></div>
      </div>
      <div v-else-if="!filtered.length" class="empty">
        <UiIcon name="file" :size="28" style="color: #64748b; margin-bottom: 8px" />
        <div>{{ quotes.length ? "No quotes match these filters." : "No quotations yet. Create your first quote to price windows, doors and facades." }}</div>
      </div>
      <template v-else>
        <!-- desktop table -->
        <div class="tscroll desk">
          <table class="tbl">
            <thead>
              <tr>
                <th>Number</th><th>Client</th><th>Project</th><th>Sales</th>
                <th>Status</th><th style="text-align: right">Total</th><th>Updated</th><th><span class="sr">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in filtered" :key="q.id" class="row" tabindex="0" @click="openDetail(q.id)" @keydown.enter="openDetail(q.id)">
                <td class="strong">{{ q.number }}</td>
                <td>{{ q.clientName || "—" }}</td>
                <td>{{ q.projectName || "—" }}</td>
                <td>{{ q.salesPerson || "—" }}</td>
                <td><span class="chip" :style="{ background: statusChip(q.status).bg, color: statusChip(q.status).fg }">{{ statusChip(q.status).label }}</span></td>
                <td style="text-align: right" class="strong">{{ fmtN(q.total, q.currency) }}</td>
                <td class="dim">{{ fmtD(q.updated) }}</td>
                <td @click.stop><UiMenu :items="rowMenu(q)" :label="`Actions for ${q.number}`" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <!-- mobile cards: status and total always visible -->
        <div class="mcards">
          <button v-for="q in filtered" :key="q.id" class="mcard" @click="openDetail(q.id)">
            <span class="mc-top">
              <span class="strong">{{ q.number }}</span>
              <span class="chip" :style="{ background: statusChip(q.status).bg, color: statusChip(q.status).fg }">{{ statusChip(q.status).label }}</span>
            </span>
            <span class="mc-client">{{ q.clientName || "No client name" }}</span>
            <span class="mc-bot">
              <span class="dim">{{ q.salesPerson || "—" }} · {{ fmtD(q.updated) }}</span>
              <span class="strong">{{ fmtN(q.total, q.currency) }}</span>
            </span>
          </button>
        </div>
      </template>
    </div>
  </div>

  <!-- EDITOR -->
  <QuoteEditor
    v-else-if="view === 'editor' && catalog && editing"
    :key="editing.quoteId || 'new'"
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
.stat-l { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .8px; color: #64748b; margin-top: 3px; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 14px 16px; border-bottom: 1px solid #f1f5f9; flex-wrap: wrap; }

.inp { padding: 8px 10px; border: 1px solid #dde4ec; border-radius: 8px; font-family: inherit; font-size: 12.5px; background: #fff; outline: none; }
.inp:focus { border-color: #93c5fd; }
.phead { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 10px; }
.ptitle { font-size: 20px; font-weight: 800; color: #0f172a; }
.searchw { position: relative; flex: 1; min-width: 220px; display: block; }
.sic { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #64748b; }
.searchw .inp { width: 100%; padding-left: 32px; }
.count { font-size: 12px; color: #64748b; padding: 8px 16px 0; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.mcards { display: none; }
.mcard { display: grid; gap: 4px; width: 100%; text-align: left; padding: 12px 16px; border: none; border-top: 1px solid #f1f5f9; background: #fff; font: inherit; color: inherit; cursor: pointer; }
.mc-top, .mc-bot { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.mc-client { font-size: 13px; color: #334155; }
.btn-primary { display: inline-flex; align-items: center; gap: 6px; background: var(--primary); color: #fff; border: none; border-radius: 8px; padding: 9px 16px; font-family: inherit; font-size: 12.5px; font-weight: 700; cursor: pointer; }
.btn-primary:hover { background: var(--primary-hover); }
.btn-export { display: inline-flex; align-items: center; gap: 6px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 14px; font-family: inherit; font-size: 12.5px; font-weight: 700; color: #475569; cursor: pointer; }
.btn-export:hover:not(:disabled) { border-color: #16a34a; color: #15803d; }
.btn-export:disabled { opacity: .5; cursor: default; }
.skel-list { padding: 8px 16px 14px; }
.skel-row { display: flex; gap: 24px; padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
.empty { padding: 46px 20px; text-align: center; color: #64748b; font-size: 13px; }
.tscroll { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th { text-align: left; padding: 10px 14px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .7px; color: #64748b; border-bottom: 1px solid #f1f5f9; white-space: nowrap; }
.tbl td { padding: 11px 14px; border-bottom: 1px solid #f8fafc; color: #334155; }
.row { cursor: pointer; }
.row:hover, .row:focus-visible { background: #f8fafc; }
.mono { font-family: ui-monospace, "Courier New", monospace; }
.strong { font-weight: 700; color: #0f172a; }
.dim { color: #64748b; font-size: 11.5px; }
.chip { border-radius: 20px; padding: 3px 10px; font-size: 10.5px; font-weight: 700; }
.btn-sm { padding: 5px 10px; border-radius: 6px; border: 1px solid #e2e8f0; background: #fff; color: #475569; font-family: inherit; font-size: 11px; font-weight: 600; cursor: pointer; margin-right: 5px; }
.btn-sm:hover { border-color: #cbd5e1; }
.btn-sm.danger:hover { border-color: #ef4444; color: #ef4444; }
@media (max-width: 860px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .wrap { padding: 14px 14px 90px; }
}
@media (max-width: 640px) {
  .desk { display: none; }
  .mcards { display: block; }
  .card-head .inp:not(.search) { flex: 1; }
  .fab-m { position: fixed; right: 16px; bottom: 18px; z-index: 30; border-radius: 999px; padding: 13px 18px; box-shadow: 0 8px 24px rgba(37,99,235,.35); }
}
</style>
