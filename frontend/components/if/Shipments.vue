<script setup lang="ts">
// Shipments: list (search, filters, sort, counts, paging) + detail with the 6-step workflow
const props = defineProps<{ detail?: string | null; detailId?: string | null }>();
const emit = defineEmits<{ (e: "navigate", p: string, d?: string | null, id?: string | null): void }>();
const { shipments, shippers, vendorName, shipperName, projectName, toUsd } = useData();
const { COMPANIES, STATUS_ORDER, STATUS_LABELS, PAYMENT_TERMS, SHIP_METHODS, fmtDate, fmtEta, etaToIso } = useConstants();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { confirm } = useConfirm();
const { request } = useApi();

// list filters live in the URL query: they survive opening a shipment, Back and refresh
const route = useRoute();
const router = useRouter();
const lastQuery = useState<Record<string, string>>("shipments_list_query", () => ({}));
const backToList = () => router.push({ path: "/platform/importflow/shipments", query: lastQuery.value });
const qp = (k: string, d: string) => (typeof route.query[k] === "string" ? (route.query[k] as string) : d);
const search = ref(qp("q", ""));
const companyFilter = ref(qp("company", "All"));
const statusFilter = ref(qp("status", "All"));
const sortBy = ref(qp("sort", "newest"));
watch([search, companyFilter, statusFilter, sortBy], () => {
  if (props.detail) return;
  const q: Record<string, string> = {};
  if (search.value) q.q = search.value;
  if (companyFilter.value !== "All") q.company = companyFilter.value;
  if (statusFilter.value !== "All") q.status = statusFilter.value;
  if (sortBy.value !== "newest") q.sort = sortBy.value;
  lastQuery.value = q;
  router.replace({ query: q });
});
// coming back to the list restores the filters from the URL
watch(() => props.detail, (d) => {
  if (d) return;
  search.value = qp("q", ""); companyFilter.value = qp("company", "All");
  statusFilter.value = qp("status", "All"); sortBy.value = qp("sort", "newest");
});
const PAGE = 50;
const limit = ref(PAGE);
const showNew = ref(false);
const busy = ref(false);

const { importflowRole: role } = useAuth();
const canEdit = computed(() => role.value === "admin" || role.value === "user");
const isAdmin = computed(() => role.value === "admin");

const SORTS: Record<string, (a: any, b: any) => number> = {
  newest: (a, b) => (b.dates?.created || 0) - (a.dates?.created || 0),
  oldest: (a, b) => (a.dates?.created || 0) - (b.dates?.created || 0),
  value: (a, b) => toUsd(b) - toUsd(a),
  eta: (a, b) => (etaToIso(a.eta) || "9999").localeCompare(etaToIso(b.eta) || "9999"),
};

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  return shipments.value
    .filter((s) =>
      (!q || s.ref?.toLowerCase().includes(q) || s.description?.toLowerCase().includes(q) || vendorName(s.vendorId).toLowerCase().includes(q)) &&
      (companyFilter.value === "All" || s.companyId === companyFilter.value) &&
      (statusFilter.value === "All" || s.status === statusFilter.value)
    )
    .sort(SORTS[sortBy.value] || SORTS.newest);
});
const visible = computed(() => filtered.value.slice(0, limit.value));
watch([search, companyFilter, statusFilter, sortBy], () => (limit.value = PAGE));
const filtersOn = computed(() => !!search.value || companyFilter.value !== "All" || statusFilter.value !== "All");
const clearFilters = () => { search.value = ""; companyFilter.value = "All"; statusFilter.value = "All"; };

const shipment = computed(() => shipments.value.find((s) => s.id === props.detailId));
const stageIdx = (s: any) => STATUS_ORDER.indexOf(s?.status);

// ---------- actions ----------
const reload = async () => {
  shipments.value = await request<any[]>("/api/shipments");
};
const put = (body: any) => request(`/api/shipments/${shipment.value!.id}`, { method: "PUT", body });

const uploadFile = async (kind: "vendorInvoice" | "packingList" | "shipperInvoice", files: File[]) => {
  if (!shipment.value || !files.length) return;
  busy.value = true;
  try {
    const { fileToBase64 } = useConstants();
    const f = files[0];
    if (f.size > 15 * 1024 * 1024) throw new Error(`${f.name} is larger than 15 MB`);
    await put({ [kind]: { name: f.name, size: f.size, type: f.type, data: await fileToBase64(f), uploaded: Date.now() } });
    notify(kind === "vendorInvoice" ? "Invoice uploaded. Production started." : kind === "packingList" ? "Packing list uploaded" : "Shipper invoice uploaded");
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
};

// Ship goods: one form, one primary action (saves details and ships)
const shipForm = ref<any>({});
const prodDays = ref<number | null>(null);
const prodEditing = ref(false);
const initShipForm = () => {
  shipForm.value = {
    shipperId: shipment.value?.shipperId || "",
    paymentTerms: shipment.value?.paymentTerms || "",
    shipMethod: shipment.value?.shipMethod || "",
    eta: etaToIso(shipment.value?.eta),
  };
  prodDays.value = parseInt(shipment.value?.productionDays || "", 10) || null;
};
watch(() => props.detailId, initShipForm, { immediate: true });
watch(shipment, (s, prev) => { if (s && !prev) initShipForm(); });

const shipMissing = computed(() => {
  const m: string[] = [];
  if (!shipment.value?.packingList) m.push("packing list");
  if (!shipForm.value.shipperId) m.push("shipper");
  if (!shipForm.value.paymentTerms) m.push("payment terms");
  if (!shipForm.value.shipMethod) m.push("shipping method");
  if (!shipForm.value.eta) m.push("ETA");
  return m;
});
const shipDetails = () => ({
  shipperId: shipForm.value.shipperId || null,
  paymentTerms: shipForm.value.paymentTerms || null,
  shipMethod: shipForm.value.shipMethod,
  eta: shipForm.value.eta,
});
const markShipped = async () => {
  if (!shipment.value || shipMissing.value.length) return;
  busy.value = true;
  try {
    await put({ ...shipDetails(), status: "in_transit" });
    notify(`${shipment.value.ref} marked as shipped`);
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
};
// details can still be saved early (e.g. shipper chosen before the packing list arrives)
const saveShipDetails = async () => {
  busy.value = true;
  try {
    await put(shipDetails());
    notify("Shipping details saved");
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
};

const confirmGoods = async () => {
  if (!shipment.value || !(await confirm({ title: `Close ${shipment.value.ref}?`, message: "Confirm the goods arrived in good condition. This completes the importation cycle.", confirmLabel: "Confirm goods received" }))) return;
  busy.value = true;
  try {
    await put({ goodsConfirmed: true });
    notify(`${shipment.value.ref} completed`);
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
};

// Production time: a number of days (stored as "N days" for compatibility)
// (prodDays / prodEditing are declared with the ship form above: initShipForm uses them)
const saveProdDays = async () => {
  if (!shipment.value || !(Number(prodDays.value) > 0)) return;
  try {
    await put({ productionDays: `${Math.round(Number(prodDays.value))} days` });
    notify("Production time updated");
    prodEditing.value = false;
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  }
};

const removeShipment = async () => {
  if (!shipment.value || !(await confirm({ title: `Delete ${shipment.value.ref}?`, message: "The shipment and its uploaded invoices and packing list are deleted. This cannot be undone.", confirmLabel: "Delete shipment", danger: true }))) return;
  try {
    await request(`/api/shipments/${shipment.value.id}`, { method: "DELETE" });
    notify("Shipment deleted");
    emit("navigate", "shipments", null, null);
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  }
};
const menuItems = computed(() => [{ label: "Delete shipment", icon: "trash", danger: true, onClick: removeShipment }]);
</script>

<template>
  <!-- ==================== DETAIL ==================== -->
  <div v-if="detail === 'detail' && shipment" class="page">
    <button class="back-link" @click="backToList"><UiIcon name="back" :size="14" /> Shipments</button>

    <div class="card" style="margin-bottom: 14px">
      <div class="d-head">
        <div style="min-width: 0">
          <div class="d-chips">
            <span class="mono d-ref">{{ shipment.ref }}</span>
            <UiCompanyChip :id="shipment.companyId" />
            <UiStatusChip :status="shipment.status" />
            <span v-if="shipment.paymentTerms" class="chip" style="background: #f1f5f9; color: #334155">{{ shipment.paymentTerms }}</span>
            <span v-if="shipment.shipMethod" class="chip" style="background: #f1f5f9; color: #334155">{{ shipment.shipMethod }}</span>
          </div>
          <h1 class="d-title">{{ shipment.description }}</h1>
          <div class="d-meta">
            <span class="mi"><UiIcon name="factory" :size="13" /> {{ vendorName(shipment.vendorId) }}</span>
            <span v-if="shipment.shipperId" class="mi"><UiIcon name="ship" :size="13" /> {{ shipperName(shipment.shipperId) }}</span>
            <span v-if="shipment.eta" class="mi"><UiIcon name="calendar" :size="13" /> ETA {{ fmtEta(shipment.eta) }}</span>
            <button v-if="shipment.projectId" class="mi link" @click="emit('navigate', 'projects', 'detail', shipment.projectId)">
              <UiIcon name="clipboard" :size="13" /> {{ projectName(shipment.projectId) }}
            </button>
            <span v-else class="mi"><UiIcon name="package" :size="13" /> General stock</span>
          </div>
        </div>
        <div class="d-right">
          <div v-if="shipment.value > 0" class="d-val num">{{ shipment.currency }} {{ (shipment.value || 0).toLocaleString() }}</div>
          <div class="d-created">Created {{ fmtDate(shipment.dates?.created) }}</div>
          <UiMenu v-if="canEdit" :items="menuItems" style="margin-top: 8px" />
        </div>
      </div>
      <div style="margin-top: 14px; border-top: 1px solid #f1f5f9; padding-top: 12px">
        <UiStatusTracker :status="shipment.status" />
      </div>
    </div>

    <div class="wf-grid">
      <!-- 1. Vendor Invoice -->
      <div class="card">
        <h2 class="wf-title"><span class="wf-dot" :class="{ done: shipment.vendorInvoice, now: !shipment.vendorInvoice }">
          <UiIcon v-if="shipment.vendorInvoice" name="check" :size="12" :stroke="3" /><template v-else>1</template></span>Vendor invoice</h2>
        <template v-if="shipment.vendorInvoice">
          <UiFileChip :file="shipment.vendorInvoice" kind="vendorInvoice" :file-id="shipment.id" />
          <div class="wf-note">Uploaded {{ fmtDate(shipment.dates?.invoiceUploaded) }}</div>
        </template>
        <UiUploadBox v-else-if="canEdit" label="Upload vendor invoice" @files="(f: File[]) => uploadFile('vendorInvoice', f)" />
        <div v-else class="wf-wait">Waiting for the vendor invoice</div>
      </div>

      <!-- 2. Production Time -->
      <div class="card">
        <h2 class="wf-title"><span class="wf-dot" :class="{ done: shipment.productionDays }"><UiIcon name="clock" :size="12" /></span>Production time</h2>
        <div v-if="shipment.productionDays && !prodEditing" class="prod">
          <span class="prod-v num">{{ shipment.productionDays }}</span>
          <button v-if="canEdit" class="btn btn-ghost btn-sm" aria-label="Edit production time" @click="prodEditing = true"><UiIcon name="edit" :size="14" /></button>
        </div>
        <form v-else-if="canEdit" class="prod-form" @submit.prevent="saveProdDays">
          <div class="suffix">
            <input v-model.number="prodDays" type="number" min="1" step="1" class="inp num" placeholder="30" aria-label="Production time in days" />
            <span>days</span>
          </div>
          <button class="btn btn-accent btn-sm" :disabled="!(Number(prodDays) > 0)">Save</button>
          <button v-if="prodEditing" type="button" class="btn btn-ghost btn-sm" @click="prodEditing = false">Cancel</button>
        </form>
        <div v-else class="wf-wait">Not set</div>
      </div>

      <!-- 3. Packing List -->
      <div class="card">
        <h2 class="wf-title"><span class="wf-dot" :class="{ done: shipment.packingList, now: !shipment.packingList && stageIdx(shipment) === 1 }">
          <UiIcon v-if="shipment.packingList" name="check" :size="12" :stroke="3" /><template v-else>3</template></span>Packing list</h2>
        <template v-if="shipment.packingList">
          <UiFileChip :file="shipment.packingList" kind="packingList" :file-id="shipment.id" />
          <div class="wf-note">Uploaded {{ fmtDate(shipment.dates?.packingReady) }}</div>
        </template>
        <UiUploadBox v-else-if="stageIdx(shipment) >= 1 && canEdit" label="Upload packing list" @files="(f: File[]) => uploadFile('packingList', f)" />
        <div v-else class="wf-wait">Upload the vendor invoice first</div>
      </div>

      <!-- 4. Ship Goods -->
      <div class="card">
        <h2 class="wf-title"><span class="wf-dot" :class="{ done: stageIdx(shipment) >= 2, now: stageIdx(shipment) === 1 }">
          <UiIcon v-if="stageIdx(shipment) >= 2" name="check" :size="12" :stroke="3" /><template v-else>4</template></span>Ship goods</h2>
        <template v-if="stageIdx(shipment) >= 2">
          <div class="wf-ok">Shipped {{ fmtDate(shipment.dates?.shipped) }}</div>
          <div class="d-meta" style="margin-top: 6px">
            <span class="mi"><UiIcon name="ship" :size="13" /> {{ shipperName(shipment.shipperId) }}</span>
            <span v-if="shipment.shipMethod" class="mi">{{ shipment.shipMethod }}</span>
            <span v-if="shipment.eta" class="mi"><UiIcon name="calendar" :size="13" /> ETA {{ fmtEta(shipment.eta) }}</span>
          </div>
        </template>
        <form v-else-if="canEdit" class="ship-form" @submit.prevent="markShipped">
          <div class="g2">
            <label><span class="lbl">Shipper</span>
              <select v-model="shipForm.shipperId" class="inp">
                <option value="" disabled>Select…</option>
                <option v-for="s in shippers" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select>
            </label>
            <label><span class="lbl">Payment terms</span>
              <select v-model="shipForm.paymentTerms" class="inp">
                <option value="" disabled>Select…</option>
                <option v-for="t in PAYMENT_TERMS" :key="t" :value="t">{{ t }}</option>
              </select>
            </label>
            <label><span class="lbl">Shipping method</span>
              <select v-model="shipForm.shipMethod" class="inp">
                <option value="" disabled>Select…</option>
                <option v-for="m in SHIP_METHODS" :key="m" :value="m">{{ m }}</option>
              </select>
            </label>
            <label><span class="lbl">ETA</span>
              <input v-model="shipForm.eta" type="date" class="inp" />
            </label>
          </div>
          <button class="btn btn-accent" :disabled="busy || shipMissing.length > 0">
            <UiIcon name="ship" :size="15" /> Mark as shipped
          </button>
          <div class="ship-foot">
            <span v-if="shipMissing.length" class="wf-note">Still needed: {{ shipMissing.join(", ") }}</span>
            <button type="button" class="link" :disabled="busy" @click="saveShipDetails">Save details without shipping</button>
          </div>
        </form>
        <div v-else class="wf-wait">{{ shipment.shipperId ? "Shipper assigned" : "Waiting for a shipper" }}</div>
      </div>

      <!-- 5. Shipper Invoice -->
      <div class="card">
        <h2 class="wf-title"><span class="wf-dot" :class="{ done: shipment.shipperInvoice, now: !shipment.shipperInvoice && stageIdx(shipment) === 2 }">
          <UiIcon v-if="shipment.shipperInvoice" name="check" :size="12" :stroke="3" /><template v-else>5</template></span>Shipper invoice</h2>
        <template v-if="shipment.shipperInvoice">
          <UiFileChip :file="shipment.shipperInvoice" kind="shipperInvoice" :file-id="shipment.id" />
          <div class="wf-note">Uploaded {{ fmtDate(shipment.dates?.shipperInvoiced) }}</div>
        </template>
        <UiUploadBox v-else-if="stageIdx(shipment) >= 2 && canEdit" label="Upload shipper invoice" @files="(f: File[]) => uploadFile('shipperInvoice', f)" />
        <div v-else class="wf-wait">Ship the goods first</div>
      </div>

      <!-- 6. Confirm & Complete -->
      <div class="card" :class="{ complete: shipment.status === 'completed' }">
        <h2 class="wf-title"><span class="wf-dot" :class="{ done: shipment.status === 'completed' }"><UiIcon name="check" :size="12" :stroke="3" /></span>Confirm and complete</h2>
        <div v-if="shipment.status === 'completed'" class="wf-ok">Cycle completed {{ fmtDate(shipment.dates?.closed) }}</div>
        <template v-else-if="shipment.status === 'in_transit' && shipment.shipperInvoice && canEdit">
          <p class="wf-note" style="margin: 0 0 10px">Goods received in good condition? Confirming closes this importation cycle.</p>
          <button class="btn btn-accent" :disabled="busy" @click="confirmGoods"><UiIcon name="check" :size="15" /> Confirm goods received</button>
        </template>
        <div v-else class="wf-wait">Upload the shipper invoice first</div>
      </div>
    </div>
  </div>

  <!-- ==================== LIST ==================== -->
  <div v-else class="page">
    <div class="head">
      <h1 class="ph">Shipments</h1>
      <button v-if="canEdit" class="btn btn-accent fab-m" @click="showNew = true"><UiIcon name="plus" :size="15" /> New Shipment</button>
    </div>

    <div class="filters">
      <label class="search-wrap">
        <span class="search-ic"><UiIcon name="search" :size="14" /></span>
        <input v-model="search" class="inp" placeholder="Search by ref, description or vendor" style="padding-left: 32px" aria-label="Search shipments" />
      </label>
      <select v-model="companyFilter" class="inp sel" aria-label="Company">
        <option value="All">All companies</option>
        <option v-for="c in COMPANIES" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <select v-model="statusFilter" class="inp sel" aria-label="Status">
        <option value="All">All statuses</option>
        <option v-for="s in STATUS_ORDER" :key="s" :value="s">{{ STATUS_LABELS[s] }}</option>
      </select>
      <select v-model="sortBy" class="inp sel" aria-label="Sort">
        <option value="newest">Newest first</option>
        <option value="oldest">Oldest first</option>
        <option value="value">Highest value</option>
        <option value="eta">Soonest ETA</option>
      </select>
    </div>
    <div class="count">
      {{ filtered.length === shipments.length ? `${shipments.length} shipments` : `${filtered.length} of ${shipments.length} shipments` }}
      <button v-if="filtersOn" class="link" @click="clearFilters">Clear filters</button>
    </div>

    <div class="s-list">
      <button v-for="s in visible" :key="s.id" class="s-row" :class="{ done: s.status === 'completed' }" @click="emit('navigate', 'shipments', 'detail', s.id)">
        <span style="min-width: 0; text-align: left">
          <span class="s-top">
            <span class="mono s-ref">{{ s.ref }}</span>
            <UiCompanyChip :id="s.companyId" />
            <span class="chip" style="background: #f1f5f9; color: #475569">{{ s.category }}</span>
          </span>
          <span class="s-desc">{{ s.description }}</span>
          <span class="d-meta">
            <span class="mi"><UiIcon name="factory" :size="12" /> {{ vendorName(s.vendorId) }}</span>
            <span v-if="s.shipperId" class="mi"><UiIcon name="ship" :size="12" /> {{ shipperName(s.shipperId) }}</span>
            <span class="mi"><UiIcon :name="s.projectId ? 'clipboard' : 'package'" :size="12" /> {{ s.projectId ? projectName(s.projectId) : "General stock" }}</span>
            <span v-if="s.eta" class="mi"><UiIcon name="calendar" :size="12" /> ETA {{ fmtEta(s.eta) }}</span>
          </span>
        </span>
        <span class="s-right">
          <UiStatusChip :status="s.status" />
          <span class="s-val num">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</span>
          <span class="s-date">{{ fmtDate(s.dates?.created) }}</span>
        </span>
      </button>
      <div v-if="!filtered.length" class="empty">
        No shipments match these filters. <button v-if="filtersOn" class="link" @click="clearFilters">Clear filters</button>
      </div>
      <button v-if="filtered.length > limit" class="btn btn-secondary more" @click="limit += PAGE">
        Show {{ Math.min(PAGE, filtered.length - limit) }} more
      </button>
    </div>
  </div>

  <IfNewShipmentModal v-if="showNew" @close="showNew = false" @created="(id: string) => emit('navigate', 'shipments', 'detail', id)" />
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; animation: fadeIn .3s; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.ph { font-size: 20px; font-weight: 800; }
.back-link, .link {
  display: inline-flex; align-items: center; gap: 6px; background: none; border: none; cursor: pointer;
  color: var(--primary); font: inherit; font-size: 12.5px; font-weight: 700; padding: 0;
}
.back-link { margin-bottom: 14px; }
.link:hover { text-decoration: underline; }
.link:disabled { opacity: .5; cursor: default; }
.filters { display: flex; gap: 10px; flex-wrap: wrap; }
.search-wrap { flex: 1; min-width: 220px; position: relative; display: block; }
.search-ic { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #64748b; display: flex; }
.sel { width: auto; }
.count { display: flex; gap: 10px; align-items: center; font-size: 12px; color: #64748b; margin: 10px 0 12px; }
.s-list { display: grid; gap: 10px; }
.s-row {
  background: #fff; border-radius: 11px; padding: 14px 18px; cursor: pointer; width: 100%; border: 1px solid #eef2f6;
  display: flex; justify-content: space-between; gap: 12px; transition: border-color .15s; font: inherit; color: inherit;
}
.s-row:hover { border-color: #bfdbfe; }
.s-row.done { background: #fbfefc; }
.s-top { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; margin-bottom: 4px; }
.s-ref, .d-ref { font-size: 12px; font-weight: 700; color: #1d4ed8; }
.s-desc { display: block; font-size: 13.5px; font-weight: 600; margin-bottom: 4px; }
.d-meta { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; color: #64748b; }
.mi { display: inline-flex; align-items: center; gap: 4px; }
.mi.link { font-size: 12px; }
.s-right { text-align: right; flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.s-val { font-size: 13.5px; font-weight: 700; }
.s-date { font-size: 11px; color: #64748b; }
.more { justify-self: center; margin-top: 4px; }
.empty { text-align: center; padding: 40px; color: #64748b; background: #fff; border-radius: 12px; border: 1px dashed #e2e8f0; font-size: 13px; }
.d-head { display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap; }
.d-chips { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; margin-bottom: 6px; }
.d-ref { font-size: 14px; }
.d-title { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
.d-right { text-align: right; flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; }
.d-val { font-size: 20px; font-weight: 800; }
.d-created { font-size: 11px; color: #64748b; }
.wf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 860px) { .wf-grid { grid-template-columns: 1fr; } }
.card.complete { background: #f0fdf4; border-color: #86efac; }
.wf-title { margin: 0 0 12px; font-size: 13.5px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
.wf-dot {
  width: 22px; height: 22px; border-radius: 50%; background: #f1f5f9; color: #64748b;
  display: inline-flex; align-items: center; justify-content: center; font-size: 10.5px; font-weight: 700; flex-shrink: 0;
}
.wf-dot.now { background: var(--primary); color: #fff; }
.wf-dot.done { background: #10b981; color: #fff; }
.wf-note { font-size: 11.5px; color: #64748b; margin-top: 6px; }
.wf-wait { color: #64748b; font-size: 12.5px; }
.wf-ok { font-size: 13px; font-weight: 700; color: #047857; }
.prod { display: flex; align-items: center; justify-content: space-between; }
.prod-v { font-size: 17px; font-weight: 700; color: #6d28d9; }
.prod-form { display: flex; gap: 8px; align-items: center; }
.suffix { position: relative; flex: 1; }
.suffix span { position: absolute; right: 11px; top: 50%; transform: translateY(-50%); font-size: 12px; color: #64748b; pointer-events: none; }
.suffix .inp { padding-right: 46px; }
.ship-form { display: grid; gap: 12px; }
.g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.ship-foot { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.ship-foot .wf-note { margin: 0; }
@media (max-width: 640px) {
  .page { padding: 16px 14px 90px; }
  .sel { flex: 1; min-width: 0; }
  .s-row { flex-direction: column; }
  .s-right { flex-direction: row; justify-content: space-between; align-items: center; text-align: left; }
  .g2 { grid-template-columns: 1fr; }
  .fab-m { position: fixed; right: 16px; bottom: 18px; z-index: 30; border-radius: 999px; padding: 13px 18px; box-shadow: 0 8px 24px rgba(37,99,235,.35); }
}
</style>
