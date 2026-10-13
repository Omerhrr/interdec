<script setup lang="ts">
// Quote detail. Client view (selling prices only) is the default, so the screen is
// safe to share with a client; the internal cost/margin tab is for quote admins.
const props = defineProps<{ quoteId: string; catalog: any }>();
const emit = defineEmits<{ (e: "back"): void; (e: "changed"): void; (e: "edit", q: any): void }>();

const notify = inject<(m: string, t?: string, o?: any) => void>("notify")!;
const { request, download, saveBlob } = useApi();
const user = useAuth().user;
const isAdmin = computed(() => user.value?.platformRole === "admin");
const isQuoteAdmin = computed(() => {
  const a = user.value?.apps || {};
  return isAdmin.value || a.quotes?.role === "admin" || (!a.quotes?.access && a.facade?.role === "admin");
});

const quote = ref<any>(null);
const revs = ref<any[]>([]);
const revId = ref<string>("");
const loading = ref(true);
const tab = ref<"client" | "internal">("client");

const load = async () => {
  loading.value = true;
  try {
    const q = await request(`/api/quotes/${props.quoteId}`);
    quote.value = q;
    revs.value = q.revisions || [];
    if (!revs.value.find((r) => r.id === revId.value)) revId.value = q.latest?.id || revs.value[0]?.id || "";
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    loading.value = false;
  }
};
onMounted(load);

const rev = computed(() => revs.value.find((r) => r.id === revId.value) || null);
const isLatest = computed(() => !!rev.value && rev.value.id === quote.value?.latest?.id);

// Selling prices: each line's cost x (1 + markup). Sub-total is the stored figure.
const sell = (it: any) => Math.round((Number(it?.bom?.total) || 0) * (1 + (Number(rev.value?.markupPct) || 0) / 100));
const unit = (it: any) => Math.round(sell(it) / Math.max(1, Number(it?.qty) || 1));
const sumBom = (key: string): number =>
  (rev.value?.items || []).reduce((t: number, it: any) => t + (Number(it?.bom?.[key]) || 0), 0);
const marginPct = computed(() => (rev.value?.sub ? Math.round(((rev.value.mkAmt || 0) / rev.value.sub) * 1000) / 10 : 0));

// ---- status: one menu, reason required for Won/Lost, 10s undo ----
const outcomeOpen = ref(false);
const outcome = ref<"won" | "lost">("won");
const outcomeNote = ref("");
const outcomeErr = ref("");
const saving = ref(false);

const postStatus = (status: string, note = "") =>
  request(`/api/quotes/${props.quoteId}/revisions/${rev.value!.id}/status`, { method: "POST", body: { status, note } });

const setStatus = async (status: string, note = "") => {
  if (!rev.value) return;
  const prev = rev.value.status;
  const prevNote = rev.value.statusNote || "";
  const label = { draft: "draft", sent: "sent", won: "won", lost: "lost" }[status];
  try {
    await postStatus(status, note);
    await load();
    emit("changed");
    notify(`${quote.value.number} marked ${label}`, "success", {
      action: {
        label: "Undo",
        fn: async () => {
          try {
            await postStatus(prev, prevNote);
            await load();
            emit("changed");
            notify(`Change undone. ${quote.value.number} is ${prev} again.`);
          } catch (e: any) {
            notify(e.message, "error");
          }
        },
      },
    });
  } catch (e: any) {
    notify(e.message, "error");
  }
};
const openOutcome = (o: "won" | "lost") => {
  outcome.value = o;
  outcomeNote.value = "";
  outcomeErr.value = "";
  outcomeOpen.value = true;
};
const saveOutcome = async () => {
  if (!outcomeNote.value.trim()) {
    outcomeErr.value = outcome.value === "won" ? "Add the PO number or a short note" : "Add the reason it was lost";
    return;
  }
  saving.value = true;
  await setStatus(outcome.value, outcomeNote.value.trim());
  saving.value = false;
  outcomeOpen.value = false;
};
const statusMenu = computed(() => {
  const s = rev.value?.status;
  const items: any[] = [];
  if (s === "sent") {
    items.push({ label: "Mark won…", icon: "trophy", onClick: () => openOutcome("won") });
    items.push({ label: "Mark lost…", icon: "x", onClick: () => openOutcome("lost") });
    items.push({ label: "Back to draft", icon: "undo", onClick: () => setStatus("draft") });
  }
  if (s === "won" || s === "lost") items.push({ label: "Reopen as draft", icon: "undo", onClick: () => setStatus("draft") });
  return items;
});

const fmtN = (n: number) => "₦" + Math.round(n || 0).toLocaleString("en-NG");
const fmtD = (ms: number) => new Date(ms).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
const size = (it: any) => (it.product === "balustrade" ? `${it.length} m × ${it.height}` : `${it.width} × ${it.height}`);

const printQuote = () => window.print();
const exporting = ref(false);
const exportExcel = async (internal = false) => {
  if (!rev.value) return;
  exporting.value = true;
  try {
    const { blob, filename } = await download(`/api/quotes/${props.quoteId}/export?rev_id=${rev.value.id}${internal ? "&internal=true" : ""}`);
    saveBlob(blob, filename || `${quote.value?.number || "quote"}-Rev${rev.value.rev}.xlsx`);
    notify(internal ? "Internal workbook exported (includes costs)" : "Client workbook exported");
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
  draft: { bg: "#F1F5F9", fg: "#334155", dot: "#94a3b8", label: "Draft" },
  sent: { bg: "#DBEAFE", fg: "#1D4ED8", dot: "#3b82f6", label: "Sent" },
  won: { bg: "#DCFCE7", fg: "#166534", dot: "#16a34a", label: "Won" },
  lost: { bg: "#FEE2E2", fg: "#991B1B", dot: "#dc2626", label: "Lost" },
};
</script>

<template>
  <div class="wrap">
    <div v-if="loading && !quote" class="empty">Loading quote…</div>
    <template v-else-if="quote">
      <div class="head">
        <div>
          <button class="back" @click="emit('back')"><UiIcon name="back" :size="13" /> Quotations</button>
          <h1 class="title">
            {{ quote.number }}
            <span class="chip" :style="{ background: chip[quote.status]?.bg, color: chip[quote.status]?.fg }">{{ chip[quote.status]?.label }}</span>
          </h1>
          <div class="sub">
            {{ quote.clientName || "No client name" }}<template v-if="quote.projectName"> · {{ quote.projectName }}</template>
            · {{ quote.salesPerson || "No sales person" }} · Created {{ fmtD(quote.created) }}
          </div>
        </div>
        <div class="actions">
          <button class="btn" :disabled="exporting" title="Client workbook: selling prices only" @click="exportExcel(false)"><UiIcon name="download" :size="14" /> {{ exporting ? "Exporting…" : "Excel" }}</button>
          <button class="btn" @click="printQuote"><UiIcon name="print" :size="14" /> Print</button>
          <button class="btn" @click="emit('edit', quote)"><UiIcon name="edit" :size="14" /> Edit</button>
          <button v-if="isLatest && rev?.status === 'draft'" class="btn primary" @click="setStatus('sent')"><UiIcon name="send" :size="14" /> Mark as sent</button>
          <UiMenu v-if="isLatest && statusMenu.length" :items="statusMenu" label="Change status">
            <span style="display: inline-flex; align-items: center; gap: 6px">Update status <UiIcon name="more" :size="14" /></span>
          </UiMenu>
        </div>
      </div>

      <div v-if="rev && (rev.status === 'won' || rev.status === 'lost') && rev.statusNote" class="outcome" :class="rev.status">
        <UiIcon :name="rev.status === 'won' ? 'trophy' : 'x'" :size="16" />
        <span><strong>{{ rev.status === "won" ? "Won" : "Lost" }}:</strong> {{ rev.statusNote }}</span>
      </div>

      <!-- Revision picker: only when there's a choice to make -->
      <div v-if="revs.length > 1" class="card slim">
        <div class="revbar">
          <span class="revlab">Revisions</span>
          <button v-for="r in revs" :key="r.id" class="revbtn" :class="{ active: r.id === revId }" @click="revId = r.id">
            Rev.{{ r.rev }} <span class="dot" :style="{ background: chip[r.status]?.dot }" />
          </button>
          <span v-if="!isLatest" class="revlab" style="margin-left: auto">Viewing an older revision (read-only history)</span>
        </div>
      </div>

      <div class="tabs" role="tablist">
        <button class="tab" :class="{ on: tab === 'client' }" role="tab" :aria-selected="tab === 'client'" @click="tab = 'client'">
          <UiIcon name="eye" :size="14" /> Client view
        </button>
        <button v-if="isQuoteAdmin" class="tab" :class="{ on: tab === 'internal' }" role="tab" :aria-selected="tab === 'internal'" @click="tab = 'internal'">
          <UiIcon name="lock" :size="14" /> Internal costs
        </button>
        <span class="tab-hint">{{ tab === "client" ? "Safe to share: selling prices only" : "Internal: do not share with the client" }}</span>
      </div>

      <!-- CLIENT VIEW -->
      <template v-if="tab === 'client'">
        <div class="card">
          <div class="card-t">Items · Rev.{{ rev?.rev }}</div>
          <div class="tscroll">
            <table class="tbl">
              <thead>
                <tr><th>#</th><th>Description</th><th>Glass</th><th>Size (mm)</th><th class="r">Qty</th><th class="r">Unit price</th><th class="r">Amount</th></tr>
              </thead>
              <tbody>
                <tr v-for="(it, i) in rev?.items || []" :key="it.id">
                  <td>{{ i + 1 }}</td>
                  <td>
                    <div class="strong">{{ it.desc || it.product }}</div>
                    <div class="tags">
                      <span v-if="it.position" class="tag">{{ it.position }}</span>
                      <span v-if="it.hasSubframe" class="tag">Sub-frame</span>
                      <span v-if="it.hasMosq" class="tag green">Mosquito net</span>
                    </div>
                  </td>
                  <td>{{ it.glassLabel || "N/A" }}</td>
                  <td class="mono">{{ size(it) }}</td>
                  <td class="r">{{ it.qty }}</td>
                  <td class="r">{{ fmtN(unit(it)) }}</td>
                  <td class="r strong">{{ fmtN(sell(it)) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="cols">
          <div class="card">
            <div class="card-t">Terms</div>
            <div class="pay" style="margin-top: 0">
              <div class="pay-t">Payment terms</div>
              <div class="pay-b">{{ rev?.paymentTerms || settings.paymentTerms }}</div>
              <div class="pay-t" style="margin-top: 10px">Valid until</div>
              <div class="pay-b">{{ validityTo }} ({{ rev?.validityDays }} days)</div>
            </div>
          </div>
          <div class="card">
            <div class="card-t">Total</div>
            <div class="brow"><span>Sub-total (excl. VAT)</span><strong>{{ fmtN(rev?.sub) }}</strong></div>
            <div class="brow"><span>VAT ({{ rev?.vatPct }}%)</span><strong>{{ fmtN(rev?.vatAmt) }}</strong></div>
            <div v-if="(rev?.logisticsCost || 0) > 0" class="brow">
              <span>Transport &amp; logistics{{ rev?.logisticsLocation ? ` to ${rev.logisticsLocation}` : "" }}</span>
              <strong>{{ fmtN(rev?.logisticsCost) }}</strong>
            </div>
            <div class="brow grand"><span>Grand total</span><strong>{{ fmtN(rev?.total) }}</strong></div>
          </div>
        </div>
      </template>

      <!-- INTERNAL VIEW -->
      <template v-else>
        <div class="card">
          <div class="card-t" style="display: flex; justify-content: space-between; align-items: center">
            <span>Bill of quantities (cost) · Rev.{{ rev?.rev }}</span>
            <button class="btn" :disabled="exporting" style="text-transform: none; letter-spacing: 0" @click="exportExcel(true)">
              <UiIcon name="download" :size="14" /> Internal Excel
            </button>
          </div>
          <div class="tscroll">
            <table class="tbl">
              <thead>
                <tr><th>#</th><th>Description</th><th>Size (mm)</th><th class="r">Qty</th><th class="r">Area</th><th class="r">Cost</th><th class="r">Selling</th></tr>
              </thead>
              <tbody>
                <tr v-for="(it, i) in rev?.items || []" :key="it.id">
                  <td>{{ i + 1 }}</td>
                  <td>
                    <div class="strong">{{ it.desc || it.product }}</div>
                    <div v-if="it.note" class="tags"><span class="tag grey">{{ it.note }}</span></div>
                  </td>
                  <td class="mono">{{ size(it) }}</td>
                  <td class="r">{{ it.qty }}</td>
                  <td class="r">{{ it.bom?.area }} m²</td>
                  <td class="r">{{ fmtN(it.bom?.total) }}</td>
                  <td class="r strong">{{ fmtN(sell(it)) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="cols">
          <div class="card">
            <div class="card-t">Cost breakdown</div>
            <div class="brow"><span>Aluminium profile</span><strong>{{ fmtN(sumBom('profileCost')) }}</strong></div>
            <div class="brow"><span>Glass / panels</span><strong>{{ fmtN(sumBom('glassCost')) }}</strong></div>
            <div class="brow"><span>Gaskets</span><strong>{{ fmtN(sumBom('gasketCost')) }}</strong></div>
            <div class="brow"><span>Hardware</span><strong>{{ fmtN(sumBom('hwCost')) }}</strong></div>
            <div class="brow"><span>Fabrication</span><strong>{{ fmtN(sumBom('fabCost')) }}</strong></div>
            <div class="brow"><span>Installation</span><strong>{{ fmtN(sumBom('instCost')) }}</strong></div>
            <div v-if="sumBom('mosqCost')" class="brow"><span>Mosquito nets</span><strong>{{ fmtN(sumBom('mosqCost')) }}</strong></div>
            <div v-if="sumBom('subframeCost')" class="brow"><span>Sub-frames</span><strong>{{ fmtN(sumBom('subframeCost')) }}</strong></div>
            <div v-if="sumBom('sealantCost')" class="brow"><span>Sealant</span><strong>{{ fmtN(sumBom('sealantCost')) }}</strong></div>
            <div class="brow tot"><span>Total cost</span><strong>{{ fmtN(rev?.cost) }}</strong></div>
            <div v-if="quote.notes" class="notes">
              <div class="card-t" style="margin-top: 14px">Internal notes</div>
              <div class="notes-b">{{ quote.notes }}</div>
            </div>
          </div>
          <div class="card">
            <div class="card-t">Margin</div>
            <div class="brow"><span>Total cost</span><strong>{{ fmtN(rev?.cost) }}</strong></div>
            <div class="brow"><span>Markup ({{ rev?.markupPct }}%)</span><strong>{{ fmtN(rev?.mkAmt) }}</strong></div>
            <div class="brow tot"><span>Sub-total (selling)</span><strong>{{ fmtN(rev?.sub) }}</strong></div>
            <div class="margin">
              <div><span>Gross profit</span><strong>{{ fmtN(rev?.mkAmt) }}</strong></div>
              <div><span>Gross margin</span><strong>{{ marginPct }}%</strong></div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- Won / Lost dialog -->
    <UiAppModal :open="outcomeOpen" :title="`Record outcome for ${quote?.number}`" :width="440" :dirty="!!outcomeNote.trim() && !saving" @close="outcomeOpen = false">
      <form class="modal-f" @submit.prevent="saveOutcome">
        <div class="choice" role="radiogroup" aria-label="Outcome">
          <label class="opt won" :class="{ on: outcome === 'won' }"><input v-model="outcome" type="radio" value="won" /> Won</label>
          <label class="opt lost" :class="{ on: outcome === 'lost' }"><input v-model="outcome" type="radio" value="lost" /> Lost</label>
        </div>
        <label>
          <span class="lbl2">{{ outcome === "won" ? "PO number or note" : "Why was it lost?" }}</span>
          <input v-model="outcomeNote" class="inp" :placeholder="outcome === 'won' ? 'e.g. PO-4471, signed 8 Oct' : 'e.g. Lost on price to competitor'" maxlength="500" />
        </label>
        <div v-if="outcomeErr" class="err2" role="alert">{{ outcomeErr }}</div>
        <div class="m-actions">
          <button type="button" class="btn" @click="outcomeOpen = false">Cancel</button>
          <button class="btn primary" :disabled="saving">{{ saving ? "Saving…" : `Mark ${outcome}` }}</button>
        </div>
      </form>
    </UiAppModal>

    <!-- PRINT-ONLY CLIENT DOCUMENT: selling prices only (cost and markup never print) -->
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
          <tr><th style="width: 26px">#</th><th>Description</th><th>Size (mm)</th><th>Qty</th><th style="text-align: right">Unit (NGN)</th><th style="text-align: right">Amount (NGN)</th></tr>
        </thead>
        <tbody>
          <tr v-for="(it, i) in rev.items" :key="it.id">
            <td>{{ i + 1 }}</td>
            <td>
              <strong>{{ it.desc }}</strong><template v-if="it.position"> · {{ it.position }}</template>
              <div class="pz-glass">{{ it.glassLabel }}</div>
              <div class="pz-tags">
                <template v-if="it.hasSubframe">Sub-frame </template><template v-if="it.hasMosq">Mosquito net</template>
              </div>
            </td>
            <td>{{ size(it) }}</td>
            <td>{{ it.qty }}</td>
            <td style="text-align: right">{{ unit(it).toLocaleString("en-NG") }}</td>
            <td style="text-align: right">{{ sell(it).toLocaleString("en-NG") }}</td>
          </tr>
        </tbody>
      </table>
      <div class="pz-tot">
        <div class="pz-tr"><span>Sub-total (excl. VAT)</span><span>{{ fmtN(rev.sub) }}</span></div>
        <div class="pz-tr"><span>VAT ({{ rev.vatPct }}%)</span><span>{{ fmtN(rev.vatAmt) }}</span></div>
        <div v-if="(rev.logisticsCost || 0) > 0" class="pz-tr">
          <span>Transport &amp; logistics{{ rev.logisticsLocation ? ` to ${rev.logisticsLocation}` : "" }}</span>
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
.back { display: inline-flex; align-items: center; gap: 5px; border: none; background: none; color: var(--primary); font-family: inherit; font-size: 12px; font-weight: 700; cursor: pointer; padding: 0; margin-bottom: 6px; }
.back:hover { text-decoration: underline; }
.title { font-size: 19px; font-weight: 800; color: #0f172a; letter-spacing: -.4px; margin: 0; display: flex; align-items: center; gap: 10px; }
.sub { font-size: 12px; color: #64748b; margin-top: 4px; }
.btn { display: inline-flex; align-items: center; gap: 6px; border-radius: 8px; padding: 8px 14px; font-family: inherit; font-size: 12.5px; font-weight: 700; cursor: pointer; border: 1.5px solid #e2e8f0; background: #fff; color: #334155; }
.btn:hover { border-color: #cbd5e1; background: #f8fafc; }
.btn.primary { background: var(--primary); border-color: var(--primary); color: #fff; }
.btn.primary:hover { background: var(--primary-hover); }
.btn:disabled { opacity: .55; cursor: default; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid #e2e8f0; margin-bottom: 16px; }
.tab { border: none; background: none; font: inherit; font-size: 13px; font-weight: 700; color: #64748b; padding: 9px 12px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; display: inline-flex; gap: 6px; align-items: center; }
.tab.on { color: #0f172a; border-bottom-color: var(--primary); }
.tab-hint { font-size: 11px; color: #64748b; margin-left: auto; align-self: center; }
.outcome { display: flex; gap: 10px; align-items: flex-start; border-radius: 10px; padding: 12px 14px; margin-bottom: 16px; font-size: 12.5px; }
.outcome.won { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
.outcome.lost { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
.margin { background: #f8fafc; border-radius: 9px; padding: 10px 12px; margin-top: 12px; display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.margin div span { display: block; font-size: 10.5px; color: #64748b; font-weight: 600; }
.margin div strong { font-size: 15px; color: #0f172a; }
.r { text-align: right; }
.modal-f { display: grid; gap: 14px; }
.choice { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.opt { display: flex; align-items: center; gap: 8px; padding: 12px; border: 2px solid #e2e8f0; border-radius: 10px; cursor: pointer; font-weight: 700; font-size: 13px; }
.opt input { accent-color: var(--primary); }
.opt.on.won { border-color: #16a34a; background: #f0fdf4; }
.opt.on.lost { border-color: #dc2626; background: #fef2f2; }
.m-actions { display: flex; justify-content: flex-end; gap: 8px; }
.lbl2 { display: block; font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 6px; }
.err2 { font-size: 12px; color: #b91c1c; font-weight: 600; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.card.slim { padding: 10px 16px; }
.card-t { font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .8px; color: #0f172a; margin-bottom: 12px; }
.revbar { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.revlab { font-size: 11px; font-weight: 700; color: #64748b; }
.revbtn { display: inline-flex; align-items: center; gap: 6px; border: 1px solid #e2e8f0; background: #fff; border-radius: 20px; padding: 4px 12px; font-family: inherit; font-size: 11.5px; font-weight: 700; color: #475569; cursor: pointer; }
.revbtn.active { border-color: var(--primary); background: var(--primary-soft); color: #1d4ed8; }
.dot { width: 7px; height: 7px; border-radius: 50%; }
.tscroll { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th { text-align: left; padding: 9px 12px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .7px; color: #64748b; border-bottom: 1px solid #f1f5f9; white-space: nowrap; }
.tbl td { padding: 11px 12px; border-bottom: 1px solid #f1f5f9; color: #334155; vertical-align: top; }
.mono { white-space: nowrap; }
.strong { font-weight: 700; color: #0f172a; }
.tags { display: flex; gap: 5px; margin-top: 4px; flex-wrap: wrap; }
.tag { font-size: 10.5px; font-weight: 700; border-radius: 20px; padding: 1px 8px; background: #f1f5f9; color: #475569; }
.tag.green { background: #f0fdf4; color: #15803d; }
.tag.grey { background: #fffbeb; color: #b45309; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
.brow { display: flex; justify-content: space-between; font-size: 12.5px; color: #64748b; padding: 5px 0; font-weight: 600; }
.brow strong { color: #0f172a; }
.brow.tot { border-top: 1px solid #f1f5f9; margin-top: 5px; padding-top: 9px; color: #0f172a; }
.brow.grand { border-top: 2px solid #0f172a; margin-top: 6px; padding-top: 9px; font-size: 13.5px; color: #0f172a; }
.brow.grand strong { color: #0f172a; font-size: 17px; }
.pay { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 9px; padding: 10px 12px; margin-top: 12px; }
.pay-t { font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .7px; color: #475569; }
.pay-b { font-size: 12px; color: #475569; margin-top: 2px; line-height: 1.45; }
.notes-b { font-size: 11.5px; color: #64748b; line-height: 1.5; }
.empty { padding: 46px 20px; text-align: center; color: #64748b; font-size: 13px; }

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
