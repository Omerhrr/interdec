<script setup lang="ts">
// Shipping cost / Clearing step of a shipment (recorded while In Transit).
// Itemised charges in any currency, invoice reference, paid or not; clearing
// also has the clearing agent and its documents (PAAR, assessment, receipts…).
const props = defineProps<{ shipment: any; kind: "shipping" | "clearing"; canEdit: boolean; isAdmin: boolean; step: number }>();
const emit = defineEmits<{ (e: "changed"): void }>();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request, download, saveBlob } = useApi();
const { confirm } = useConfirm();
const { agents, fx, shipperName, agentName } = useData();
const { fmtDate, fileToBase64 } = useConstants();
const money = useMoney();
const navigate = inject<(p: string, d?: string | null, id?: string | null) => void>("navigate", () => {});

const isClearing = computed(() => props.kind === "clearing");
const title = computed(() => (isClearing.value ? "Clearing" : "Shipping cost"));
const cost = computed(() => (isClearing.value ? props.shipment.clearingCost : props.shipment.shippingCost) || null);
const recorded = computed(() => (Number(cost.value?.total) || 0) > 0 && (!isClearing.value || !!props.shipment.clearingAgentId));
const shipped = computed(() => ["in_transit", "completed"].includes(props.shipment.status));
const editable = computed(() => props.canEdit && (props.shipment.status === "in_transit" || props.isAdmin) && shipped.value);

const SUGGEST = {
  shipping: ["Ocean freight", "Air freight", "Bunker surcharge (BAF)", "Insurance", "Documentation fee", "Origin handling", "Courier"],
  clearing: ["Import duty", "VAT", "CISS", "ETLS", "Port charges", "Terminal charges", "Shipping line / D.O.", "Agent fee", "Transport to site", "Demurrage"],
};
const DEFAULT_LINES = { shipping: ["Ocean freight"], clearing: ["Import duty", "VAT", "Port charges", "Agent fee"] };
const currencies = computed(() => {
  const l = Object.keys(fx.value.rates || {});
  return ["NGN", "USD", ...l.filter((c) => !["NGN", "USD"].includes(c)).sort()].filter((c, i, a) => a.indexOf(c) === i);
});

// ---- editing ----
const editing = ref(false);
const form = ref<any>(null);
const err = ref("");
const saving = ref(false);
const rid = () => Math.random().toString(36).slice(2, 10);
const startEdit = () => {
  const c = cost.value;
  form.value = {
    agentId: props.shipment.clearingAgentId || "",
    currency: c?.currency || (isClearing.value ? "NGN" : props.shipment.currency || "USD"),
    lines: c?.lines?.length ? c.lines.map((l: any) => ({ ...l })) : DEFAULT_LINES[props.kind].map((label) => ({ id: rid(), label, amount: null })),
    invoiceRef: c?.invoiceRef || "", paid: !!c?.paid, paidOn: c?.paidOn || "", note: c?.note || "",
  };
  err.value = "";
  editing.value = true;
};
const total = computed(() => (form.value?.lines || []).reduce((a: number, l: any) => a + (Number(l.amount) || 0), 0));
const unused = computed(() => SUGGEST[props.kind].filter((s) => !form.value?.lines.some((l: any) => l.label === s)));
const addLine = (label = "") => {
  form.value.lines.push({ id: rid(), label, amount: null });
  nextTick(() => {
    const ins = document.querySelectorAll<HTMLInputElement>(`#cc-${props.kind} .ln-amt input`);
    ins[ins.length - 1]?.focus();
  });
};
const removeLine = (i: number) => form.value.lines.splice(i, 1);
watch(() => form.value?.paid, (p) => { if (p && !form.value.paidOn) form.value.paidOn = new Date().toISOString().slice(0, 10); });

const save = async () => {
  err.value = "";
  const lines = form.value.lines.filter((l: any) => (l.label || "").trim() || Number(l.amount));
  if (lines.some((l: any) => Number(l.amount) && !(l.label || "").trim())) { err.value = "Give every charge a name"; return; }
  if (lines.some((l: any) => Number(l.amount) < 0)) { err.value = "Amounts can't be negative"; return; }
  if (isClearing.value && !form.value.agentId) { err.value = "Choose the clearing agent"; return; }
  if (!(total.value > 0)) { err.value = "Enter at least one amount"; return; }
  saving.value = true;
  try {
    const body: any = {};
    const c = { currency: form.value.currency, lines: lines.map((l: any) => ({ id: l.id, label: l.label.trim(), amount: Number(l.amount) || 0 })),
      invoiceRef: form.value.invoiceRef, paid: form.value.paid, paidOn: form.value.paid ? form.value.paidOn : "", note: form.value.note };
    if (isClearing.value) { body.clearingAgentId = form.value.agentId; body.clearing = c; } else body.shipping = c;
    await request(`/api/shipments/${props.shipment.id}/costs`, { method: "PUT", body });
    notify(`${title.value} saved: ${money.fmt(total.value, form.value.currency)}`);
    editing.value = false;
    emit("changed");
  } catch (e: any) {
    err.value = e.message;
  } finally {
    saving.value = false;
  }
};
const cancel = () => { editing.value = false; };

// quick "mark paid" without opening the editor
const markPaid = async () => {
  try {
    const c = cost.value;
    const body: any = {};
    body[props.kind] = { ...c, paid: true, paidOn: new Date().toISOString().slice(0, 10) };
    await request(`/api/shipments/${props.shipment.id}/costs`, { method: "PUT", body });
    notify(`${title.value} marked as paid`);
    emit("changed");
  } catch (e: any) {
    notify(e.message, "error");
  }
};

// ---- clearing documents ----
const uploading = ref(false);
const docs = computed(() => props.shipment.clearingCost?.docs || []);
const upload = async (files: File[]) => {
  uploading.value = true;
  try {
    for (const f of files) {
      if (f.size > 15 * 1024 * 1024) throw new Error(`${f.name} is larger than 15 MB`);
      await request(`/api/shipments/${props.shipment.id}/clearing-docs`, {
        method: "POST", body: { file: { name: f.name, size: f.size, type: f.type, data: await fileToBase64(f), uploaded: Date.now() } },
      });
    }
    notify(files.length > 1 ? `${files.length} documents uploaded` : "Document uploaded");
    emit("changed");
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    uploading.value = false;
  }
};
const getDoc = async (i: number) => {
  try {
    const { blob, filename } = await download(`/api/shipments/${props.shipment.id}/clearing-docs/${i}`);
    saveBlob(blob, filename || docs.value[i]?.name || "document");
  } catch (e: any) {
    notify(e.message, "error");
  }
};
const removeDoc = async (i: number) => {
  if (!(await confirm({ title: `Remove ${docs.value[i]?.name}?`, message: "The file is deleted from this shipment.", confirmLabel: "Remove", danger: true }))) return;
  try {
    await request(`/api/shipments/${props.shipment.id}/clearing-docs/${i}`, { method: "DELETE" });
    emit("changed");
  } catch (e: any) {
    notify(e.message, "error");
  }
};
const kb = (n: number) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
const fmtDay = (iso: string) => (iso ? new Date(iso + "T00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "");
</script>

<template>
  <div :id="`cc-${kind}`" class="card" :class="{ complete: recorded && cost?.paid }">
    <h2 class="wf-title">
      <span class="wf-dot" :class="{ done: recorded, now: !recorded && shipment.status === 'in_transit' }">
        <UiIcon v-if="recorded" name="check" :size="12" :stroke="3" /><template v-else>{{ step }}</template>
      </span>
      {{ title }}
      <button v-if="recorded && editable && !editing" class="lnk" @click="startEdit"><UiIcon name="edit" :size="12" /> Edit</button>
    </h2>

    <!-- not yet -->
    <div v-if="!shipped" class="wf-wait">Recorded once the goods are shipped</div>

    <!-- edit form -->
    <div v-else-if="editing" class="frm">
      <label v-if="isClearing" class="f">
        <span>Clearing agent</span>
        <select v-model="form.agentId" class="inp">
          <option value="" disabled>Choose agent…</option>
          <option v-for="a in [...agents].sort((x, y) => x.name.localeCompare(y.name))" :key="a.id" :value="a.id">{{ a.name }}</option>
        </select>
        <button v-if="!agents.length" type="button" class="lnk" @click="navigate('agents')">Add a clearing agent first</button>
      </label>
      <div class="row2">
        <label class="f"><span>Currency</span>
          <select v-model="form.currency" class="inp"><option v-for="c in currencies" :key="c" :value="c">{{ c }}</option></select>
        </label>
        <label class="f"><span>{{ isClearing ? "Agent invoice / ref" : "Shipper invoice no." }}</span>
          <input v-model="form.invoiceRef" class="inp" :placeholder="isClearing ? 'e.g. ACF-2026-117' : 'e.g. GFL-INV-5521'" maxlength="80" />
        </label>
      </div>

      <div class="lines" role="group" :aria-label="`${title} charges`">
        <div v-for="(l, i) in form.lines" :key="l.id" class="ln">
          <input v-model="l.label" class="inp" :list="`sg-${kind}`" placeholder="Charge" :aria-label="`Charge ${i + 1} name`" maxlength="80" />
          <UiNumberInput v-model="l.amount" class="ln-amt" :prefix="money.sym(form.currency).trim()" :decimals="2" :label="`Charge ${i + 1} amount`" />
          <button type="button" class="x" :aria-label="`Remove charge ${i + 1}`" @click="removeLine(i)"><UiIcon name="trash" :size="13" /></button>
        </div>
        <datalist :id="`sg-${kind}`"><option v-for="s in SUGGEST[kind]" :key="s" :value="s" /></datalist>
        <div class="add-row">
          <button type="button" class="addbtn" @click="addLine()"><UiIcon name="plus" :size="12" /> Add charge</button>
          <button v-for="s in unused.slice(0, 4)" :key="s" type="button" class="sug" @click="addLine(s)">+ {{ s }}</button>
        </div>
      </div>
      <div class="tot"><span>Total</span><strong>{{ money.fmt(total, form.currency) }}</strong></div>

      <div class="row2">
        <label class="chk"><input v-model="form.paid" type="checkbox" /> Paid</label>
        <label v-if="form.paid" class="f"><span>Paid on</span><input v-model="form.paidOn" type="date" class="inp" /></label>
      </div>
      <label class="f"><span>Note <span class="hint">optional</span></span><input v-model="form.note" class="inp" maxlength="500" /></label>
      <p v-if="err" class="fe" role="alert">{{ err }}</p>
      <div class="acts">
        <button class="btn btn-secondary btn-sm" :disabled="saving" @click="cancel">Cancel</button>
        <button class="btn btn-accent btn-sm" :disabled="saving" @click="save">{{ saving ? "Saving…" : `Save ${title.toLowerCase()}` }}</button>
      </div>
    </div>

    <!-- recorded -->
    <div v-else-if="recorded || cost?.lines?.length">
      <div v-if="isClearing" class="who"><UiIcon name="shield" :size="13" /> {{ agentName(shipment.clearingAgentId) }}</div>
      <div v-else-if="shipment.shipperId" class="who"><UiIcon name="ship" :size="13" /> {{ shipperName(shipment.shipperId) }}</div>
      <div class="amt">{{ money.fmt(cost.total, cost.currency) }}</div>
      <ul class="sum">
        <li v-for="l in cost.lines" :key="l.id"><span>{{ l.label }}</span><span>{{ money.fmt(l.amount, cost.currency) }}</span></li>
      </ul>
      <div class="meta">
        <span v-if="cost.paid" class="chip paid">Paid{{ cost.paidOn ? ` ${fmtDay(cost.paidOn)}` : "" }}</span>
        <span v-else class="chip unpaid">Not paid</span>
        <span v-if="cost.invoiceRef" class="ref">Ref {{ cost.invoiceRef }}</span>
        <button v-if="!cost.paid && editable" class="lnk" @click="markPaid">Mark as paid</button>
      </div>
      <p v-if="cost.note" class="wf-note">{{ cost.note }}</p>
    </div>

    <!-- nothing yet, in transit -->
    <template v-else>
      <p class="wf-wait" style="margin-bottom: 10px">
        {{ isClearing ? "Who is clearing the goods, and what did duty, VAT and port charges come to?" : "What did freight and related charges come to?" }}
      </p>
      <button v-if="editable" class="btn btn-accent btn-sm" @click="startEdit"><UiIcon name="plus" :size="13" /> Record {{ title.toLowerCase() }}</button>
      <div v-else class="wf-wait">Waiting for {{ title.toLowerCase() }}</div>
    </template>

    <!-- clearing documents -->
    <div v-if="isClearing && shipped && !editing && (docs.length || editable)" class="docs">
      <div class="lbl">Clearing documents</div>
      <ul v-if="docs.length">
        <li v-for="(d, i) in docs" :key="i">
          <button class="doc" @click="getDoc(i)"><UiIcon name="file" :size="14" /> <span>{{ d.label ? `${d.label}: ` : "" }}{{ d.name }}</span></button>
          <span class="dm">{{ kb(d.size || 0) }} · {{ fmtDate(d.uploaded) }}</span>
          <button v-if="editable" class="x" :aria-label="`Remove ${d.name}`" @click="removeDoc(i)"><UiIcon name="trash" :size="13" /></button>
        </li>
      </ul>
      <UiUploadBox v-if="editable" :label="uploading ? 'Uploading…' : 'Upload PAAR, assessment, duty receipt…'" multiple @files="upload" />
    </div>
  </div>
</template>

<style scoped>
.card.complete { background: #f0fdf4; border-color: #86efac; }
.wf-title { margin: 0 0 12px; font-size: 13.5px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
.wf-dot { width: 22px; height: 22px; border-radius: 50%; background: #f1f5f9; color: #64748b; display: inline-flex; align-items: center; justify-content: center; font-size: 10.5px; font-weight: 700; flex-shrink: 0; }
.wf-dot.now { background: var(--primary); color: #fff; }
.wf-dot.done { background: #10b981; color: #fff; }
.wf-note { font-size: 11.5px; color: #64748b; margin-top: 6px; }
.wf-wait { color: #64748b; font-size: 12.5px; }
.lnk { margin-left: auto; background: none; border: none; font: inherit; font-size: 12px; font-weight: 700; color: #2563eb; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; padding: 0; }
.meta .lnk { margin-left: 0; }
.frm { display: grid; gap: 10px; }
.f { display: flex; flex-direction: column; gap: 4px; font-size: 12px; font-weight: 700; color: #334155; }
.f .lnk { margin: 2px 0 0; align-self: flex-start; }
.hint { font-weight: 500; color: #64748b; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; align-items: end; }
.lines { display: grid; gap: 6px; }
.ln { display: grid; grid-template-columns: 1fr 150px 28px; gap: 6px; align-items: center; }
.x { background: none; border: none; color: #94a3b8; cursor: pointer; padding: 4px; border-radius: 6px; display: inline-flex; }
.x:hover { color: #b91c1c; background: #fef2f2; }
.add-row { display: flex; flex-wrap: wrap; gap: 6px; }
.addbtn { display: inline-flex; align-items: center; gap: 4px; font: inherit; font-size: 12px; font-weight: 700; color: #334155; background: #fff; border: 1.5px dashed #cbd5e1; border-radius: 7px; padding: 5px 10px; cursor: pointer; }
.addbtn:hover { border-color: #2563eb; color: #2563eb; }
.sug { font: inherit; font-size: 11.5px; font-weight: 600; color: #475569; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 20px; padding: 4px 9px; cursor: pointer; }
.sug:hover { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
.tot { display: flex; justify-content: space-between; align-items: baseline; padding: 8px 10px; background: #f8fafc; border-radius: 8px; font-size: 13px; }
.tot strong { font-size: 16px; }
.chk { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; color: #334155; min-height: 38px; cursor: pointer; }
.chk input { width: 16px; height: 16px; accent-color: #16a34a; }
.fe { font-size: 12px; color: #b91c1c; font-weight: 600; }
.acts { display: flex; justify-content: flex-end; gap: 8px; }
.who { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: #475569; font-weight: 600; margin-bottom: 4px; }
.amt { font-size: 20px; font-weight: 800; color: #0f172a; font-variant-numeric: tabular-nums; }
.sum { list-style: none; padding: 0; margin: 6px 0 8px; display: grid; gap: 3px; }
.sum li { display: flex; justify-content: space-between; gap: 10px; font-size: 12.5px; color: #475569; }
.sum li span:last-child { font-variant-numeric: tabular-nums; color: #0f172a; }
.meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.chip { font-size: 11px; font-weight: 800; border-radius: 20px; padding: 2px 9px; }
.chip.paid { background: #dcfce7; color: #166534; }
.chip.unpaid { background: #fef3c7; color: #92400e; }
.ref { font-size: 12px; color: #64748b; }
.docs { margin-top: 12px; padding-top: 10px; border-top: 1px solid #f1f5f9; display: grid; gap: 8px; }
.lbl { font-size: 12px; font-weight: 700; color: #334155; }
.docs ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 4px; }
.docs li { display: flex; align-items: center; gap: 8px; min-width: 0; }
.doc { display: inline-flex; align-items: center; gap: 6px; background: none; border: none; font: inherit; font-size: 12.5px; font-weight: 600; color: #1d4ed8; cursor: pointer; padding: 2px 0; min-width: 0; text-align: left; }
.doc span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dm { font-size: 11px; color: #64748b; white-space: nowrap; margin-left: auto; }
@media (max-width: 560px) { .row2 { grid-template-columns: 1fr; } .ln { grid-template-columns: 1fr 120px 28px; } }
</style>
