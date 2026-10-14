<script setup lang="ts">
// What has been paid to the vendor for this order (deposit / balance), in the
// shipment's currency, and what is still owed.
const props = defineProps<{ shipment: any; canEdit: boolean; isAdmin: boolean }>();
const emit = defineEmits<{ (e: "changed"): void }>();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();
const { confirm } = useConfirm();
const money = useMoney();

const s = computed(() => props.shipment);
const cur = computed(() => s.value.currency || "USD");
const value = computed(() => Number(s.value.value) || 0);
const paidPct = computed(() => (value.value ? Math.min(100, (Number(s.value.vendorPaid) / value.value) * 100) : 0));
const editable = computed(() => props.canEdit && (s.value.status !== "completed" || props.isAdmin));
const fmt = (n: number) => money.fmt(n, cur.value);
const fmtDay = (iso: string) => (iso ? new Date(iso + "T00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "");
const KINDS = ["Deposit", "Balance", "Full payment", "Other"];

const adding = ref(false);
const form = ref<any>({});
const err = ref("");
const saving = ref(false);
const startAdd = () => {
  const bal = Number(s.value.vendorBalance) || 0;
  const first = !(s.value.vendorPayments || []).length;
  form.value = { kind: first ? (s.value.paymentTerms === "Before Shipment" ? "Full payment" : "Deposit") : "Balance", amount: first ? null : bal, date: new Date().toISOString().slice(0, 10), ref: "", note: "" };
  err.value = "";
  adding.value = true;
};
watch(() => form.value.kind, (k) => { if (adding.value && (k === "Balance" || k === "Full payment")) form.value.amount = Number(s.value.vendorBalance) || 0; });
const save = async () => {
  err.value = "";
  if (!(Number(form.value.amount) > 0)) { err.value = "Enter the amount paid"; return; }
  saving.value = true;
  try {
    await request(`/api/shipments/${s.value.id}/vendor-payments`, { method: "POST", body: form.value });
    notify(`Payment of ${fmt(form.value.amount)} recorded`);
    adding.value = false;
    emit("changed");
  } catch (e: any) {
    err.value = e.message;
  } finally {
    saving.value = false;
  }
};
const remove = async (p: any) => {
  if (!(await confirm({ title: `Remove ${fmt(p.amount)} payment?`, message: `${p.kind} on ${fmtDay(p.date)}${p.ref ? ` (ref ${p.ref})` : ""} will be deleted.`, confirmLabel: "Remove", danger: true }))) return;
  try {
    await request(`/api/shipments/${s.value.id}/vendor-payments/${p.id}`, { method: "DELETE" });
    emit("changed");
  } catch (e: any) {
    notify(e.message, "error");
  }
};
const STATUS: Record<string, { t: string; c: string }> = {
  paid: { t: "Fully paid", c: "paid" }, part: { t: "Part paid", c: "part" }, unpaid: { t: "Not paid", c: "unpaid" }, "n/a": { t: "No order value", c: "na" },
};
</script>

<template>
  <div class="card vp" :class="{ complete: s.vendorPayStatus === 'paid' }">
    <h2 class="wf-title">
      <span class="wf-dot" :class="{ done: s.vendorPayStatus === 'paid' }"><UiIcon name="coins" :size="12" /></span>
      Vendor payments
      <span v-if="s.paymentTerms" class="terms">{{ s.paymentTerms }}</span>
    </h2>

    <template v-if="value">
      <div class="nums">
        <div><span class="k">Paid</span><strong>{{ fmt(s.vendorPaid) }}</strong></div>
        <div><span class="k">Still owed</span><strong :class="{ owed: s.vendorBalance > 0 }">{{ fmt(s.vendorBalance) }}</strong></div>
        <span class="chip" :class="STATUS[s.vendorPayStatus]?.c">{{ STATUS[s.vendorPayStatus]?.t }}</span>
      </div>
      <div class="bar" role="img" :aria-label="`${Math.round(paidPct)}% of ${fmt(value)} paid`"><span :style="{ width: paidPct + '%' }" /></div>
      <p v-if="s.vendorPaymentDue" class="due" role="status">
        <UiIcon name="alert" :size="13" />
        {{ s.paymentTerms === "Before Shipment" ? "Terms are Before Shipment: the vendor should be paid in full before the goods ship." : "Goods have shipped: the balance is now due." }}
      </p>

      <ul v-if="s.vendorPayments?.length" class="list">
        <li v-for="p in s.vendorPayments" :key="p.id">
          <span class="d">{{ fmtDay(p.date) }}</span>
          <span class="kd">{{ p.kind }}<small v-if="p.ref"> · {{ p.ref }}</small></span>
          <span class="a">{{ fmt(p.amount) }}</span>
          <button v-if="editable" class="x" :aria-label="`Remove payment of ${fmt(p.amount)}`" @click="remove(p)"><UiIcon name="trash" :size="13" /></button>
        </li>
      </ul>

      <div v-if="adding" class="frm">
        <div class="g2">
          <label class="f"><span>Payment</span><select v-model="form.kind" class="inp"><option v-for="k in KINDS" :key="k">{{ k }}</option></select></label>
          <label class="f"><span>Amount ({{ cur }})</span><UiNumberInput v-model="form.amount" :prefix="money.sym(cur).trim()" :decimals="2" label="Amount paid" /></label>
          <label class="f"><span>Date</span><input v-model="form.date" type="date" class="inp" /></label>
          <label class="f"><span>Reference</span><input v-model="form.ref" class="inp" maxlength="80" placeholder="e.g. TT / transfer no." /></label>
        </div>
        <p v-if="err" class="fe" role="alert">{{ err }}</p>
        <div class="acts">
          <button class="btn btn-secondary btn-sm" :disabled="saving" @click="adding = false">Cancel</button>
          <button class="btn btn-accent btn-sm" :disabled="saving" @click="save">{{ saving ? "Saving…" : "Record payment" }}</button>
        </div>
      </div>
      <button v-else-if="editable && s.vendorBalance > 0" class="btn btn-secondary btn-sm add" @click="startAdd"><UiIcon name="plus" :size="13" /> Record payment</button>
    </template>
    <p v-else class="wf-wait">Set the order value on this shipment to track vendor payments.</p>
  </div>
</template>

<style scoped>
.card.complete { background: #f0fdf4; border-color: #86efac; }
.wf-title { margin: 0 0 12px; font-size: 13.5px; font-weight: 700; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.wf-dot { width: 22px; height: 22px; border-radius: 50%; background: #f1f5f9; color: #64748b; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.wf-dot.done { background: #10b981; color: #fff; }
.wf-wait { color: #64748b; font-size: 12.5px; }
.terms { margin-left: auto; font-size: 11px; font-weight: 700; color: #475569; background: #f1f5f9; border-radius: 20px; padding: 2px 9px; }
.nums { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.nums > div { display: flex; flex-direction: column; }
.k { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: .5px; }
.nums strong { font-size: 17px; font-weight: 800; color: #0f172a; font-variant-numeric: tabular-nums; }
.nums strong.owed { color: #b45309; }
.chip { margin-left: auto; font-size: 11px; font-weight: 800; border-radius: 20px; padding: 2px 9px; }
.chip.paid { background: #dcfce7; color: #166534; }
.chip.part { background: #fef3c7; color: #92400e; }
.chip.unpaid { background: #fee2e2; color: #b91c1c; }
.chip.na { background: #f1f5f9; color: #475569; }
.bar { height: 6px; background: #e2e8f0; border-radius: 6px; overflow: hidden; margin: 10px 0 8px; }
.bar span { display: block; height: 100%; background: #10b981; }
.due { display: flex; gap: 6px; align-items: flex-start; font-size: 12px; font-weight: 600; color: #92400e; background: #fffbeb; border-radius: 8px; padding: 7px 10px; margin-bottom: 8px; }
.list { list-style: none; padding: 0; margin: 0 0 10px; display: grid; gap: 4px; }
.list li { display: grid; grid-template-columns: 92px 1fr auto 26px; gap: 8px; align-items: center; font-size: 12.5px; color: #475569; }
.list .a { font-weight: 700; color: #0f172a; font-variant-numeric: tabular-nums; }
.list small { color: #94a3b8; }
.x { background: none; border: none; color: #94a3b8; cursor: pointer; padding: 3px; border-radius: 6px; display: inline-flex; }
.x:hover { color: #b91c1c; background: #fef2f2; }
.frm { display: grid; gap: 8px; border-top: 1px solid #f1f5f9; padding-top: 10px; }
.g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.f { display: flex; flex-direction: column; gap: 4px; font-size: 12px; font-weight: 700; color: #334155; }
.fe { font-size: 12px; color: #b91c1c; font-weight: 600; }
.acts { display: flex; justify-content: flex-end; gap: 8px; }
.add { margin-top: 2px; }
@media (max-width: 480px) { .g2 { grid-template-columns: 1fr; } .list li { grid-template-columns: 80px 1fr auto 26px; } }
</style>
