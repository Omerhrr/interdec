<script setup lang="ts">
// Shipments page - list + filters, detail w/ full lifecycle workflow
const props = defineProps<{ detail?: string | null; detailId?: string | null }>();
const emit = defineEmits<{ (e: "navigate", p: string, d?: string | null, id?: string | null): void }>();
const { shipments, vendors, shippers, projects, vendorName, shipperName, projectName } = useData();
const { user } = useAuth();
const { COMPANIES, STATUS_ORDER, STATUS_LABELS, STATUS_COLORS, PAYMENT_TERMS, SHIP_METHODS, CURRENCIES, fmtDate } = useConstants();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();

const search = ref("");
const companyFilter = ref("All");
const statusFilter = ref("All");
const showNew = ref(false);
const busy = ref(false);

const role = computed(() => user.value?.apps?.importflow?.role || "viewer");
const canEdit = computed(() => role.value === "admin" || role.value === "user");

const filtered = computed(() =>
  shipments.value
    .filter((s) => {
      const q = search.value.toLowerCase();
      return (
        (!q || s.ref?.toLowerCase().includes(q) || s.description?.toLowerCase().includes(q) || vendorName(s.vendorId).toLowerCase().includes(q)) &&
        (companyFilter.value === "All" || s.companyId === companyFilter.value) &&
        (statusFilter.value === "All" || s.status === statusFilter.value)
      );
    })
    .sort((a, b) => (b.dates?.created || 0) - (a.dates?.created || 0))
);

const shipment = computed(() => shipments.value.find((s) => s.id === props.detailId));

const stageIdx = (s: any) => STATUS_ORDER.indexOf(s?.status);

// ---------- actions ----------
const reload = async () => {
  // refresh just shipments for speed
  const data = await request<any[]>("/api/shipments");
  shipments.value = data;
};

const uploadFile = async (kind: "vendorInvoice" | "packingList" | "shipperInvoice", files: File[]) => {
  if (!shipment.value || !files.length) return;
  busy.value = true;
  try {
    const { fileToBase64 } = useConstants();
    const f = files[0];
    const body: any = { [kind]: { name: f.name, size: f.size, type: f.type, data: await fileToBase64(f), uploaded: Date.now() } };
    await request(`/api/shipments/${shipment.value.id}`, { method: "PUT", body });
    notify(
      kind === "vendorInvoice" ? "Invoice uploaded, production started"
      : kind === "packingList" ? "Packing list uploaded"
      : "Shipper invoice uploaded"
    );
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
};

// ship goods form (under_production → select shipper/payTerms/etc, then Mark as Shipped)
const shipForm = ref<any>({});
const initShipForm = () => {
  shipForm.value = {
    shipperId: shipment.value?.shipperId || "",
    paymentTerms: shipment.value?.paymentTerms || "",
    shipMethod: shipment.value?.shipMethod || "",
    eta: shipment.value?.eta || "",
  };
};
watch(() => props.detailId, initShipForm, { immediate: true });

const assignShipper = async () => {
  if (!shipment.value) return;
  busy.value = true;
  try {
    await request(`/api/shipments/${shipment.value.id}`, {
      method: "PUT",
      body: {
        shipperId: shipForm.value.shipperId || null,
        paymentTerms: shipForm.value.paymentTerms || null,
        shipMethod: shipForm.value.shipMethod,
        eta: shipForm.value.eta,
      },
    });
    notify("Shipper assigned");
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
};

const markShipped = async () => {
  if (!shipment.value) return;
  busy.value = true;
  try {
    await request(`/api/shipments/${shipment.value.id}`, {
      method: "PUT",
      body: { shipperId: shipForm.value.shipperId || null, paymentTerms: shipForm.value.paymentTerms || null, shipMethod: shipForm.value.shipMethod, eta: shipForm.value.eta },
    });
    // then trigger shipped: backend moves when shipper assigned + packing ready; force via status update
    await request(`/api/shipments/${shipment.value.id}`, { method: "PUT", body: { status: "in_transit" } });
    notify("🚢 Marked as shipped");
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
};

const confirmGoods = async () => {
  if (!shipment.value) return;
  busy.value = true;
  try {
    await request(`/api/shipments/${shipment.value.id}`, { method: "PUT", body: { goodsConfirmed: true, status: "completed" } });
    notify("🎉 Cycle completed!");
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    busy.value = false;
  }
};

const saveProdDays = async () => {
  if (!shipment.value) return;
  try {
    await request(`/api/shipments/${shipment.value.id}`, { method: "PUT", body: { productionDays: prodDaysEdit.value } });
    notify("Production time updated");
    prodEditing.value = false;
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  }
};

const prodEditing = ref(false);
const prodDaysEdit = ref("");

const removeShipment = async () => {
  if (!shipment.value || !confirm("Delete this shipment? This cannot be undone.")) return;
  try {
    await request(`/api/shipments/${shipment.value.id}`, { method: "DELETE" });
    notify("Deleted");
    emit("navigate", "shipments", null, null);
    await reload();
  } catch (e: any) {
    notify(e.message, "error");
  }
};

const statusColor = (s: string) => (s === "Active" ? "#10b981" : s === "Completed" ? "#6366f1" : "#f59e0b");
</script>

<template>
  <!-- ==================== DETAIL ==================== -->
  <div v-if="detail === 'detail' && shipment" class="page">
    <button class="back-link" @click="emit('navigate', 'shipments', null, null)">← Shipments</button>

    <!-- Header card -->
    <div class="card" style="margin-bottom: 14px">
      <div style="display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap">
        <div style="min-width: 0">
          <div style="display: flex; align-items: center; gap: 7px; flex-wrap: wrap; margin-bottom: 6px">
            <span class="mono" style="font-size: 14px; font-weight: 700; color: #3b82f6">{{ shipment.ref }}</span>
            <UiCompanyChip :id="shipment.companyId" />
            <UiStatusChip :status="shipment.status" />
            <span
              v-if="shipment.paymentTerms"
              class="chip"
              :style="{ background: shipment.paymentTerms === 'Before Shipment' ? '#ffedd5' : '#ede9fe', color: shipment.paymentTerms === 'Before Shipment' ? '#f97316' : '#8b5cf6' }"
            >{{ shipment.paymentTerms }}</span>
            <span v-if="shipment.shipMethod" class="chip" style="background: #ecfeff; color: #0e7490">🚢 {{ shipment.shipMethod }}</span>
          </div>
          <h2 style="font-size: 17px; font-weight: 700; margin-bottom: 3px">{{ shipment.description }}</h2>
          <div style="font-size: 12.5px; color: #64748b; line-height: 22px">
            Vendor: <strong>{{ vendorName(shipment.vendorId) }}</strong>
            <template v-if="shipment.shipperId"> · Shipper: <strong>{{ shipperName(shipment.shipperId) }}</strong></template>
            <template v-if="shipment.eta"> · 📅 ETA: <strong class="mono" style="color: #0ea5e9">{{ shipment.eta }}</strong></template>
          </div>
          <div style="font-size: 12.5px; color: #64748b; margin-top: 2px; line-height: 22px">
            <template v-if="shipment.projectId">
              📋 Project:
              <strong style="cursor: pointer; color: #3b82f6" @click="emit('navigate', 'projects', 'detail', shipment.projectId)">{{ projectName(shipment.projectId) }}</strong>
            </template>
            <template v-else><span style="color: #f59e0b">📦</span> <strong>General Stock</strong></template>
            <template v-if="shipment.productionDays"> · ⏱ Production: <strong style="color: #7c3aed">{{ shipment.productionDays }}</strong></template>
          </div>
        </div>
        <div style="text-align: right; flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 8px">
          <div v-if="shipment.value > 0">
            <div class="mono" style="font-size: 20px; font-weight: 800">{{ shipment.currency }} {{ (shipment.value || 0).toLocaleString() }}</div>
            <div style="font-size: 10.5px; color: #94a3b8">Created {{ fmtDate(shipment.dates?.created) }}</div>
          </div>
          <button v-if="canEdit" class="btn btn-danger btn-sm" @click="removeShipment">🗑 Delete</button>
        </div>
      </div>
      <div style="margin-top: 14px; border-top: 1px solid #f8fafc; padding-top: 12px">
        <UiStatusTracker :status="shipment.status" />
      </div>
    </div>

    <!-- Workflow cards -->
    <div class="wf-grid">
      <!-- 1. Vendor Invoice -->
      <div class="card">
        <h3 class="wf-title">
          <span class="wf-dot" :style="{ background: shipment.vendorInvoice ? '#10b981' : '#3b82f6' }">{{ shipment.vendorInvoice ? "✓" : "1" }}</span>
          Vendor Invoice
        </h3>
        <template v-if="shipment.vendorInvoice">
          <UiFileChip :file="shipment.vendorInvoice" kind="vendorInvoice" :file-id="shipment.id" />
          <span style="font-size: 10.5px; color: #94a3b8; margin-left: 6px">Uploaded {{ fmtDate(shipment.dates?.invoiceUploaded) }}</span>
        </template>
        <UiUploadBox v-else-if="shipment.status === 'order_placed' && canEdit" label="Upload Vendor Invoice" @files="(f: File[]) => uploadFile('vendorInvoice', f)" />
        <div v-else style="color: #94a3b8; font-size: 12.5px">Waiting...</div>
      </div>

      <!-- 2. Production Time -->
      <div class="card">
        <h3 class="wf-title"><span class="wf-dot" style="background: #a78bfa">⏱</span> Production Time</h3>
        <template v-if="shipment.productionDays">
          <div style="display: flex; align-items: center; justify-content: space-between">
            <span class="mono" style="font-size: 16px; font-weight: 700; color: #7c3aed">{{ shipment.productionDays }}</span>
            <button v-if="canEdit" class="btn btn-ghost btn-sm" @click="prodEditing = true; prodDaysEdit = shipment.productionDays">✏️</button>
          </div>
          <div v-if="prodEditing" style="display: flex; gap: 8px; margin-top: 10px">
            <input v-model="prodDaysEdit" class="inp" placeholder="e.g. 30 days" style="flex: 1" />
            <button class="btn btn-accent btn-sm" @click="saveProdDays">Save</button>
          </div>
        </template>
        <template v-else-if="canEdit">
          <div style="display: flex; gap: 8px">
            <input v-model="prodDaysEdit" class="inp" placeholder="e.g. 30 days" style="flex: 1" @keydown.enter="saveProdDays" />
            <button class="btn btn-accent btn-sm" :disabled="!prodDaysEdit.trim()" @click="saveProdDays">Set</button>
          </div>
        </template>
        <div v-else style="color: #94a3b8; font-size: 12.5px">Not set</div>
      </div>

      <!-- 3. Packing List -->
      <div class="card">
        <h3 class="wf-title">
          <span class="wf-dot" :style="{ background: shipment.packingList ? '#10b981' : '#e2e8f0', color: shipment.packingList ? '#fff' : '#94a3b8' }">{{ shipment.packingList ? "✓" : "3" }}</span>
          Packing List
        </h3>
        <template v-if="shipment.packingList">
          <UiFileChip :file="shipment.packingList" kind="packingList" :file-id="shipment.id" />
          <span style="font-size: 10.5px; color: #94a3b8; margin-left: 6px">Uploaded {{ fmtDate(shipment.dates?.packingReady) }}</span>
        </template>
        <UiUploadBox v-else-if="shipment.status === 'under_production' && canEdit" label="Upload Packing List" @files="(f: File[]) => uploadFile('packingList', f)" />
        <div v-else style="color: #94a3b8; font-size: 12.5px">{{ stageIdx(shipment) < 1 ? "Upload vendor invoice first" : "Done" }}</div>
      </div>

      <!-- 4. Ship Goods -->
      <div class="card">
        <h3 class="wf-title">
          <span class="wf-dot" :style="{ background: stageIdx(shipment) >= 2 ? '#10b981' : '#e2e8f0', color: stageIdx(shipment) >= 2 ? '#fff' : '#94a3b8' }">{{ stageIdx(shipment) >= 2 ? "✓" : "4" }}</span>
          Ship Goods
        </h3>

        <template v-if="stageIdx(shipment) >= 2">
          <div style="font-size: 12.5px; font-weight: 600; color: #10b981">✓ Shipped {{ fmtDate(shipment.dates?.shipped) }}</div>
          <div style="font-size: 11.5px; color: #64748b; margin-top: 6px; line-height: 1.8">
            🚢 {{ shipperName(shipment.shipperId) }}<template v-if="shipment.shipMethod"> · {{ shipment.shipMethod }}</template><template v-if="shipment.eta"> · ETA {{ shipment.eta }}</template>
          </div>
        </template>
        <template v-else-if="canEdit">
          <div style="display: grid; gap: 10px">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">
              <div>
                <label class="lbl">Shipper *</label>
                <select v-model="shipForm.shipperId" class="inp">
                  <option value="" disabled>Select...</option>
                  <option v-for="s in shippers" :key="s.id" :value="s.id">{{ s.name }}</option>
                </select>
              </div>
              <div>
                <label class="lbl">Payment Terms *</label>
                <select v-model="shipForm.paymentTerms" class="inp">
                  <option value="" disabled>Select...</option>
                  <option v-for="t in PAYMENT_TERMS" :key="t" :value="t">{{ t }}</option>
                </select>
              </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">
              <div>
                <label class="lbl">Shipping Method *</label>
                <select v-model="shipForm.shipMethod" class="inp">
                  <option value="" disabled>Select...</option>
                  <option v-for="m in SHIP_METHODS" :key="m" :value="m">{{ m }}</option>
                </select>
              </div>
              <div>
                <label class="lbl">ETA (dd/mm/yy) *</label>
                <input v-model="shipForm.eta" class="inp mono" placeholder="15/04/26" />
              </div>
            </div>
            <button
              class="btn btn-accent btn-sm"
              :disabled="busy || !shipForm.shipperId || !shipForm.paymentTerms"
              @click="assignShipper"
            >💾 Save Shipper</button>
            <button
              class="btn btn-accent"
              :disabled="busy || !shipForm.shipperId"
              @click="markShipped"
            >🚢 Mark as Shipped</button>
          </div>
        </template>
        <div v-else style="color: #94a3b8; font-size: 12.5px">{{ shipment.shipperId ? "Done" : "Assign a shipper first" }}</div>
      </div>

      <!-- 5. Shipper Invoice -->
      <div class="card">
        <h3 class="wf-title">
          <span class="wf-dot" :style="{ background: shipment.shipperInvoice ? '#10b981' : '#e2e8f0', color: shipment.shipperInvoice ? '#fff' : '#94a3b8' }">{{ shipment.shipperInvoice ? "✓" : "5" }}</span>
          Shipper Invoice
        </h3>
        <template v-if="shipment.shipperInvoice">
          <UiFileChip :file="shipment.shipperInvoice" kind="shipperInvoice" :file-id="shipment.id" />
          <span style="font-size: 10.5px; color: #94a3b8; margin-left: 6px">{{ fmtDate(shipment.dates?.shipperInvoiced) }}</span>
        </template>
        <UiUploadBox v-else-if="shipment.status === 'in_transit' && canEdit" label="Upload Shipper Invoice" @files="(f: File[]) => uploadFile('shipperInvoice', f)" />
        <div v-else style="color: #94a3b8; font-size: 12.5px">{{ stageIdx(shipment) < 2 ? "Ship goods first" : "Done" }}</div>
      </div>

      <!-- 6. Confirm & Complete -->
      <div class="card" :style="{ background: shipment.status === 'completed' ? '#f0fdf4' : '#fff', border: shipment.status === 'completed' ? '2px solid #86efac' : '1px solid #f1f5f9' }">
        <h3 class="wf-title">
          <span class="wf-dot" :style="{ background: shipment.status === 'completed' ? '#10b981' : '#e2e8f0', color: shipment.status === 'completed' ? '#fff' : '#94a3b8' }">✓</span>
          Confirm &amp; Complete
        </h3>
        <div v-if="shipment.status === 'completed'" style="font-size: 13px; font-weight: 700; color: #10b981">
          ✅ Cycle completed on {{ fmtDate(shipment.dates?.closed) }}
        </div>
        <template v-else-if="shipment.status === 'in_transit' && shipment.shipperInvoice && canEdit">
          <p style="font-size: 12.5px; color: #64748b; margin-bottom: 10px">
            Goods received in good condition? Confirm to close this importation cycle.
          </p>
          <button class="btn btn-accent btn-lg" :disabled="busy" @click="confirmGoods">✅ Confirm Goods &amp; Complete</button>
        </template>
        <div v-else style="color: #94a3b8; font-size: 12.5px">{{ shipment.shipperInvoice ? "Done" : "Upload shipper invoice first" }}</div>
      </div>
    </div>

    <IfNewShipmentModal v-if="showNew" @close="showNew = false" @created="(id: string) => emit('navigate', 'shipments', 'detail', id)" />
  </div>

  <!-- ==================== LIST ==================== -->
  <div v-else class="page">
    <div class="head">
      <h2>Shipments</h2>
      <button v-if="canEdit" class="btn btn-accent" @click="showNew = true">＋ New Shipment</button>
    </div>

    <div class="filters">
      <div class="search-wrap">
        <span class="search-ic">🔍</span>
        <input v-model="search" class="inp" placeholder="Search ref, description, vendor..." style="padding-left: 30px" />
      </div>
      <select v-model="companyFilter" class="inp" style="width: auto">
        <option value="All">All Companies</option>
        <option v-for="c in COMPANIES" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <select v-model="statusFilter" class="inp" style="width: auto">
        <option value="All">All Statuses</option>
        <option v-for="s in STATUS_ORDER" :key="s" :value="s">{{ STATUS_LABELS[s] }}</option>
      </select>
    </div>

    <div class="s-list">
      <div
        v-for="s in filtered" :key="s.id"
        class="s-row"
        :style="{ border: `1.5px solid ${s.status === 'completed' ? '#d1fae5' : '#f1f5f9'}` }"
        @click="emit('navigate', 'shipments', 'detail', s.id)"
      >
        <div style="min-width: 0">
          <div style="display: flex; align-items: center; gap: 7px; flex-wrap: wrap; margin-bottom: 4px">
            <span class="mono" style="font-size: 12px; font-weight: 700; color: #3b82f6">{{ s.ref }}</span>
            <UiCompanyChip :id="s.companyId" />
            <span class="chip" style="background: #f1f5f9; color: #475569">{{ s.category }}</span>
          </div>
          <div style="font-size: 13.5px; font-weight: 600; margin-bottom: 3px">{{ s.description }}</div>
          <div style="font-size: 11.5px; color: #94a3b8">
            🏭 {{ vendorName(s.vendorId) }}
            <template v-if="s.shipperId"> · 🚢 {{ shipperName(s.shipperId) }}</template>
            <template v-if="s.projectId"> · 📋 {{ projectName(s.projectId) }}</template>
            <template v-else> · 📦 General Stock</template>
            <template v-if="s.eta"> · 📅 {{ s.eta }}</template>
          </div>
        </div>
        <div style="text-align: right; flex-shrink: 0">
          <UiStatusChip :status="s.status" />
          <div class="mono" style="font-size: 13.5px; font-weight: 700; margin-top: 5px">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</div>
          <div style="font-size: 10px; color: #cbd5e1; margin-top: 3px">{{ fmtDate(s.dates?.created) }}</div>
        </div>
      </div>
      <div v-if="!filtered.length" class="empty">No shipments match your filters</div>
    </div>

    <IfNewShipmentModal v-if="showNew" @close="showNew = false" @created="(id: string) => emit('navigate', 'shipments', 'detail', id)" />
  </div>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; animation: fadeIn .3s; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
h2 { font-size: 20px; font-weight: 800; }
.back-link {
  display: inline-flex; align-items: center; gap: 6px; background: none; border: none; cursor: pointer;
  color: #3b82f6; font-family: inherit; font-size: 12.5px; font-weight: 700; margin-bottom: 14px; padding: 0;
}
.filters { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.search-wrap { flex: 1; min-width: 200px; position: relative; }
.search-ic { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 12px; opacity: .55; }
.s-list { display: grid; gap: 10px; }
.s-row {
  background: #fff; border-radius: 11px; padding: 16px 20px; cursor: pointer;
  display: flex; justify-content: space-between; gap: 12px; transition: all .15s;
}
.s-row:hover { border-color: #c7d2fe; }
.wf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 860px) { .wf-grid { grid-template-columns: 1fr; } }
.wf-title { margin: 0 0 10px; font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 7px; }
.wf-dot {
  width: 22px; height: 22px; border-radius: 50%; color: #94a3b8;
  display: inline-flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700;
  flex-shrink: 0;
}
.empty { text-align: center; padding: 40px; color: #94a3b8; background: #fff; border-radius: 12px; border: 1px dashed #e2e8f0; }
</style>
