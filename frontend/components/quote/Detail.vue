<script setup lang="ts">
// Quote detail - BOM breakdown, revisions, status transitions, printable quote
const props = defineProps<{ quoteId: string; catalog: any }>();
const emit = defineEmits<{ (e: "back"): void; (e: "changed"): void; (e: "edit", q: any): void }>();

const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request, download } = useApi();
const user = useAuth().user;
const isAdmin = computed(() => user.value?.platformRole === "admin");

const quote = ref<any>(null);
const revs = ref<any[]>([]);
const revId = ref<string>("");
const loading = ref(true);

const load = async () => {
  loading.value = true;
  try {
    const q = await request(`/api/quotes/${props.quoteId}`);
    quote.value = q;
    revs.value = q.revisions || [];
    if (!revs.value.find((r) => r.id === revId.value)) {
      revId.value = (q.latest?.id) || (revs.value[0]?.id ?? "");
    }
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    loading.value = false;
  }
};
onMounted(load);

const rev = computed(() => revs.value.find((r) => r.id === revId.value) || null);

const setDraft = () => {
  // view the latest revision by default
  revId.value = quote.value?.latest?.id || revId.value;
};

const setStatus = async (status: string) => {
  if (!rev.value) return;
  try {
    await request(`/api/quotes/${props.quoteId}/revisions/${rev.value.id}/status`, {
      method: "POST", body: { status },
    });
    notify(`Rev.${rev.value.rev} marked ${status}`);
    await load();
    emit("changed");
    setDraft();
  } catch (e: any) {
    notify(e.message, "error");
  }
};

const fmtN = (n: number) => "₦" + Math.round(n || 0).toLocaleString("en-NG");
const fmtD = (ms: number) => new Date(ms).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });

const printQuote = () => window.print();

const exporting = ref(false);
const exportExcel = async () => {
  if (!rev.value) return;
  exporting.value = true;
  try {
    const { blob, filename } = await download(`/api/quotes/${props.quoteId}/export?rev_id=${rev.value.id}`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || `${quote.value?.number || "quote"}-Rev${rev.value.rev}.xlsx`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
    notify("Excel exported");
  } catch (e: any) {
    notify(e.message || "Export failed", "error");
  } finally {
    exporting.value = false;
  }
};

const settings = computed(() => props.catalog?.values?.settings || {});
const validityTo = computed(() => {
  if (!rev.value?.created) return "-";
  const d = new Date(rev.value.created);
  d.setDate(d.getDate() + Number(rev.value.validityDays || 14));
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
});

const chip: any = {
  draft: { bg: "#F3F4F6", fg: "#4B5563", label: "Draft" },
  sent: { bg: "#DBEAFE", fg: "#1D4ED8", label: "Sent" },
  won: { bg: "#DCFCE7", fg: "#15803D", label: "Won" },
  lost: { bg: "#FEE2E2", fg: "#B91C1C", label: "Lost" },
};
</script>

<template>
  <div class="wrap">
    <div v-if="loading" class="empty">Loading quote...</div>
    <template v-else-if="quote">
      <div class="head">
        <div>
          <button class="back" @click="emit('back')">← Quotations</button>
          <h1 class="title">
            {{ quote.number }}
            <span class="chip" :style="{ background: chip[quote.status]?.bg, color: chip[quote.status]?.fg }">
              {{ chip[quote.status]?.label }}
            </span>
          </h1>
          <div class="sub">
            {{ quote.clientName || "N/A" }}<template v-if="quote.projectName"> · {{ quote.projectName }}</template>
            · Sales: {{ quote.salesPerson || "N/A" }} · Created {{ fmtD(quote.created) }}
          </div>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap">
          <button class="btn excel" :disabled="exporting" @click="exportExcel">{{ exporting ? "Exporting..." : "⬇ Excel" }}</button>
          <button class="btn" @click="printQuote">Print</button>
          <button class="btn" @click="emit('edit', quote)">Edit</button>
          <button v-if="rev && rev.status === 'draft'" class="btn primary" @click="setStatus('sent')">Mark as Sent</button>
          <template v-if="rev && rev.status === 'sent'">
            <button class="btn won" @click="setStatus('won')">Mark Won</button>
            <button class="btn lost" @click="setStatus('lost')">Mark Lost</button>
          </template>
          <button v-if="rev && (rev.status === 'won' || rev.status === 'lost')" class="btn" @click="setStatus('draft')">
            Reopen as Draft
          </button>
        </div>
      </div>

      <!-- Revision picker -->
      <div class="card slim">
        <div class="revbar">
          <span class="revlab">Revisions:</span>
          <button
            v-for="r in revs" :key="r.id"
            class="revbtn" :class="{ active: r.id === revId }"
            @click="revId = r.id"
          >
            Rev.{{ r.rev }}
            <span class="dot" :style="{ background: chip[r.status]?.dot || '#9CA3AF' }" />
          </button>
        </div>
      </div>

      <!-- Items + BOM -->
      <div class="card">
        <div class="card-t">Bill of Quantities - Rev.{{ rev?.rev }}</div>
        <div class="tscroll">
          <table class="tbl">
            <thead>
              <tr>
                <th>#</th><th>Description</th><th>Glass</th><th>Size (mm)</th><th>Qty</th>
                <th>Area</th><th style="text-align: right">Line Total</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(it, i) in rev?.items || []" :key="it.id">
                <td>{{ i + 1 }}</td>
                <td>
                  <div class="strong">{{ it.desc || it.product }}</div>
                  <div class="tags">
                    <span v-if="it.hasSubframe" class="tag">+ Sub-Frame</span>
                    <span v-if="it.hasMosq" class="tag green">+ Mosquito Net</span>
                    <span v-if="it.note" class="tag grey">{{ it.note }}</span>
                  </div>
                </td>
                <td>{{ it.glassLabel || "N/A" }}</td>
                <td class="mono">
                  {{ it.product === "balustrade" ? `${it.length}m × ${it.height}` : `${it.width} × ${it.height}` }}
                </td>
                <td>{{ it.qty }}</td>
                <td>{{ it.bom?.area }} m²</td>
                <td style="text-align: right" class="strong">{{ fmtN(it.bom?.total) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="cols">
        <div class="card">
          <div class="card-t">Cost Breakdown - Rev.{{ rev?.rev }}</div>
          <div class="bomgrid">
            <div class="brow"><span>Aluminium profile</span><strong>{{ fmtN(rev?.items?.reduce((s, i) => s + (i.bom?.profileCost || 0), 0)) }}</strong></div>
            <div class="brow"><span>Glass</span><strong>{{ fmtN(rev?.items?.reduce((s, i) => s + (i.bom?.glassCost || 0), 0)) }}</strong></div>
            <div class="brow"><span>Gaskets</span><strong>{{ fmtN(rev?.items?.reduce((s, i) => s + (i.bom?.gasketCost || 0), 0)) }}</strong></div>
            <div class="brow"><span>Hardware</span><strong>{{ fmtN(rev?.items?.reduce((s, i) => s + (i.bom?.hwCost || 0), 0)) }}</strong></div>
            <div class="brow"><span>Fabrication</span><strong>{{ fmtN(rev?.items?.reduce((s, i) => s + (i.bom?.fabCost || 0), 0)) }}</strong></div>
            <div class="brow"><span>Installation</span><strong>{{ fmtN(rev?.items?.reduce((s, i) => s + (i.bom?.instCost || 0), 0)) }}</strong></div>
            <div class="brow"><span>Mosquito nets</span><strong>{{ fmtN(rev?.items?.reduce((s, i) => s + (i.bom?.mosqCost || 0), 0)) }}</strong></div>
            <div class="brow"><span>Sub-frames</span><strong>{{ fmtN(rev?.items?.reduce((s, i) => s + (i.bom?.subframeCost || 0), 0)) }}</strong></div>
            <div class="brow"><span>Sealant</span><strong>{{ fmtN(rev?.items?.reduce((s, i) => s + (i.bom?.sealantCost || 0), 0)) }}</strong></div>
            <div class="brow tot"><span>Total cost</span><strong>{{ fmtN(rev?.cost) }}</strong></div>
          </div>
          <div v-if="isAdmin && quote.notes" class="notes">
            <div class="card-t" style="margin-top: 14px">Internal Notes</div>
            <div class="notes-b">{{ quote.notes }}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-t">Summary</div>
          <div class="brow"><span>Markup ({{ rev?.markupPct }}%)</span><strong>{{ fmtN(rev?.mkAmt) }}</strong></div>
          <div class="brow"><span>Subtotal</span><strong>{{ fmtN(rev?.sub) }}</strong></div>
          <div class="brow"><span>VAT ({{ rev?.vatPct }}%)</span><strong>{{ fmtN(rev?.vatAmt) }}</strong></div>
          <div v-if="(rev?.logisticsCost || 0) > 0" class="brow">
            <span>Transport &amp; Logistics{{ rev?.logisticsLocation ? ` to ${rev.logisticsLocation}` : "" }}</span>
            <strong>{{ fmtN(rev?.logisticsCost) }}</strong>
          </div>
          <div class="brow grand"><span>Grand Total</span><strong>{{ fmtN(rev?.total) }}</strong></div>
          <div class="pay">
            <div class="pay-t">Payment Terms</div>
            <div class="pay-b">{{ rev?.paymentTerms || settings.paymentTerms }}</div>
            <div class="pay-t" style="margin-top: 8px">Valid Until</div>
            <div class="pay-b">{{ validityTo }} ({{ rev?.validityDays }} days)</div>
          </div>
        </div>
      </div>
    </template>

    <!-- PRINT-ONLY QUOTE DOCUMENT -->
    <div v-if="quote && rev" class="pz">
      <div class="pz-head">
        <div>
          <div class="pz-brand">INTERDEC FACADE</div>
          <div class="pz-brandsub">Aluminium &amp; Glass Systems</div>
        </div>
        <div style="text-align: right">
          <div class="pz-q">QUOTATION</div>
          <div class="pz-no">{{ quote.number }} · Rev.{{ rev.rev }}</div>
          <div class="pz-date">{{ fmtD(rev.created) }}</div>
        </div>
      </div>
      <div class="pz-meta">
        <div>
          <div class="pz-l">PREPARED FOR</div>
          <div class="pz-v strong">{{ quote.clientName || "N/A" }}</div>
          <div class="pz-v">{{ quote.clientPhone }}</div>
          <div class="pz-v">{{ quote.clientEmail }}</div>
        </div>
        <div>
          <div class="pz-l">SALES PERSON</div>
          <div class="pz-v strong">{{ quote.salesPerson || "N/A" }}</div>
          <div class="pz-l" style="margin-top: 8px">VALID UNTIL</div>
          <div class="pz-v">{{ validityTo }}</div>
        </div>
      </div>
      <table class="pztbl">
        <thead>
          <tr><th style="width: 26px">#</th><th>Description</th><th>Size (mm)</th><th>Qty</th><th style="text-align: right">Amount (NGN)</th></tr>
        </thead>
        <tbody>
          <tr v-for="(it, i) in rev.items" :key="it.id">
            <td>{{ i + 1 }}</td>
            <td>
              <strong>{{ it.desc }}</strong>
              <div class="pz-glass">{{ it.glassLabel }}</div>
              <div class="pz-tags">
                <template v-if="it.hasSubframe">, Sub-Frame</template><template v-if="it.hasMosq">, Mosquito Net</template>
              </div>
            </td>
            <td>{{ it.product === "balustrade" ? `${it.length}m × ${it.height}` : `${it.width} × ${it.height}` }}</td>
            <td>{{ it.qty }}</td>
            <td style="text-align: right">{{ Math.round(it.bom?.total || 0).toLocaleString("en-NG") }}</td>
          </tr>
        </tbody>
      </table>
      <div class="pz-tot">
        <div class="pz-tr"><span>Total Cost</span><span>{{ fmtN(rev.cost) }}</span></div>
        <div class="pz-tr"><span>Markup ({{ rev.markupPct }}%)</span><span>{{ fmtN(rev.mkAmt) }}</span></div>
        <div class="pz-tr"><span>Subtotal</span><span>{{ fmtN(rev.sub) }}</span></div>
        <div class="pz-tr"><span>VAT ({{ rev.vatPct }}%)</span><span>{{ fmtN(rev.vatAmt) }}</span></div>
        <div v-if="(rev.logisticsCost || 0) > 0" class="pz-tr">
          <span>Transport &amp; Logistics{{ rev.logisticsLocation ? ` to ${rev.logisticsLocation}` : "" }}</span>
          <span>{{ fmtN(rev.logisticsCost) }}</span>
        </div>
        <div class="pz-tr grand"><span>GRAND TOTAL (NGN)</span><span>{{ fmtN(rev.total) }}</span></div>
      </div>
      <div class="pz-terms">
        <div class="pz-l">PAYMENT TERMS</div>
        <div class="pz-v">{{ rev.paymentTerms || settings.paymentTerms }}</div>
        <div class="pz-l" style="margin-top: 10px">TERMS &amp; CONDITIONS</div>
        <div class="pz-v pre">{{ settings.tcs }}</div>
      </div>
      <div class="pz-foot">Thank you for the opportunity to quote. This quotation is valid for {{ rev.validityDays }} days from the date of issue.</div>
    </div>
  </div>
</template>

<style scoped>
.wrap { padding: 22px; max-width: 1200px; margin: 0 auto; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.back { border: none; background: none; color: #94a3b8; font-family: inherit; font-size: 11.5px; font-weight: 700; cursor: pointer; padding: 0; margin-bottom: 6px; }
.back:hover { color: #b45309; }
.title { font-size: 19px; font-weight: 800; color: #0f172a; letter-spacing: -.4px; margin: 0; display: flex; align-items: center; gap: 10px; }
.sub { font-size: 12px; color: #64748b; margin-top: 4px; }
.btn { border-radius: 8px; padding: 9px 15px; font-family: inherit; font-size: 12px; font-weight: 700; cursor: pointer; border: 1px solid #e2e8f0; background: #fff; color: #475569; }
.btn:hover { border-color: #f59e0b; color: #b45309; }
.btn.primary { background: linear-gradient(135deg, #f59e0b, #ea580c); border: none; color: #fff; }
.btn.primary:hover { filter: brightness(1.05); color: #fff; }
.btn.won { background: #16a34a; border: none; color: #fff; }
.btn.lost { background: #ef4444; border: none; color: #fff; }
.btn.excel:hover:not(:disabled) { border-color: #16a34a; color: #15803d; }
.btn:disabled { opacity: .55; cursor: default; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.card.slim { padding: 10px 16px; }
.card-t { font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .8px; color: #0f172a; margin-bottom: 12px; }
.revbar { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.revlab { font-size: 11px; font-weight: 700; color: #94a3b8; }
.revbtn { display: inline-flex; align-items: center; gap: 6px; border: 1px solid #e2e8f0; background: #fff; border-radius: 20px; padding: 4px 12px; font-family: inherit; font-size: 11.5px; font-weight: 700; color: #475569; cursor: pointer; }
.revbtn.active { border-color: #f59e0b; background: #fffbeb; color: #b45309; }
.dot { width: 7px; height: 7px; border-radius: 50%; }
.tscroll { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th { text-align: left; padding: 9px 12px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .7px; color: #94a3b8; border-bottom: 1px solid #f1f5f9; white-space: nowrap; }
.tbl td { padding: 11px 12px; border-bottom: 1px solid #f8fafc; color: #334155; vertical-align: top; }
.mono { font-family: ui-monospace, "Courier New", monospace; white-space: nowrap; }
.strong { font-weight: 700; color: #0f172a; }
.tags { display: flex; gap: 5px; margin-top: 4px; flex-wrap: wrap; }
.tag { font-size: 9.5px; font-weight: 700; border-radius: 20px; padding: 1px 8px; background: #f1f5f9; color: #64748b; }
.tag.green { background: #f0fdf4; color: #15803d; }
.tag.grey { background: #fffbeb; color: #b45309; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
.brow { display: flex; justify-content: space-between; font-size: 12.5px; color: #64748b; padding: 5px 0; font-weight: 600; }
.brow strong { color: #0f172a; }
.brow.tot { border-top: 1px solid #f1f5f9; margin-top: 5px; padding-top: 9px; color: #0f172a; }
.brow.grand { border-top: 2px solid #0f172a; margin-top: 6px; padding-top: 9px; font-size: 13.5px; color: #0f172a; }
.brow.grand strong { color: #b45309; font-size: 16px; }
.pay { background: #fffbeb; border: 1px solid #fde68a; border-radius: 9px; padding: 10px 12px; margin-top: 12px; }
.pay-t { font-size: 9.5px; font-weight: 800; text-transform: uppercase; letter-spacing: .7px; color: #b45309; }
.pay-b { font-size: 10.5px; color: #78716c; margin-top: 2px; line-height: 1.45; }
.notes-b { font-size: 11.5px; color: #64748b; line-height: 1.5; }
.empty { padding: 46px 20px; text-align: center; color: #94a3b8; font-size: 13px; }

/* ---- print document (screen: hidden) ---- */
.pz { display: none; }

@media print {
  body > *:not(:has(.pz)) { display: none !important; }
  :root { --pz-pad: 0; }
  .wrap { padding: 0 !important; max-width: none !important; }
  .wrap > *:not(.pz) { display: none !important; }
  .pz { display: block !important; color: #111827; font-size: 11px; }
  .pz-head { display: flex; justify-content: space-between; border-bottom: 2.5px solid #111827; padding-bottom: 10px; margin-bottom: 14px; }
  .pz-brand { font-size: 19px; font-weight: 800; letter-spacing: 2.5px; }
  .pz-brandsub { font-size: 9px; letter-spacing: 1.6px; color: #4b5563; margin-top: 2px; }
  .pz-q { font-size: 15px; font-weight: 800; letter-spacing: 1.4px; }
  .pz-no { font-size: 10.5px; font-weight: 700; margin-top: 3px; }
  .pz-date { font-size: 9.5px; color: #4b5563; }
  .pz-meta { display: flex; justify-content: space-between; gap: 20px; margin-bottom: 14px; }
  .pz-l { font-size: 8px; font-weight: 800; letter-spacing: 1px; color: #6b7280; }
  .pz-v { font-size: 10.5px; color: #374151; line-height: 1.5; }
  .pz-v.strong { font-size: 12px; color: #111827; }
  .pz-v.pre { white-space: pre-line; }
  .pztbl { width: 100%; border-collapse: collapse; font-size: 10px; margin-bottom: 12px; }
  .pztbl th { border-bottom: 1.5px solid #111827; text-align: left; padding: 5px 6px; font-size: 8.5px; letter-spacing: .6px; text-transform: uppercase; }
  .pztbl td { border-bottom: 1px solid #e5e7eb; padding: 6px; vertical-align: top; }
  .pz-glass { font-size: 8.5px; color: #6b7280; margin-top: 1px; }
  .pz-tags { font-size: 8.5px; color: #6b7280; }
  .pz-tot { margin-left: auto; width: 240px; margin-bottom: 14px; }
  .pz-tr { display: flex; justify-content: space-between; font-size: 10px; padding: 2.5px 0; color: #374151; }
  .pz-tr.grand { border-top: 1.5px solid #111827; margin-top: 4px; padding-top: 6px; font-weight: 800; font-size: 11.5px; color: #111827; }
  .pz-terms { border-top: 1px solid #e5e7eb; padding-top: 10px; }
  .pz-foot { margin-top: 14px; font-size: 8.5px; color: #6b7280; text-align: center; border-top: 1px solid #e5e7eb; padding-top: 8px; }
}
@media (max-width: 860px) {
  .cols { grid-template-columns: 1fr; }
  .wrap { padding: 14px; }
}
</style>
