<script setup lang="ts">
// Quote editor - client meta, item builder with live server-side pricing, markup/VAT
const props = defineProps<{ editing: any; catalog: any; projects: any[] }>();
const emit = defineEmits<{ (e: "saved", msg: string): void; (e: "cancel"): void }>();

const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();

const form = ref<any>(JSON.parse(JSON.stringify(props.editing)));
const totals = ref<any>(null);
const pricing = ref(false);
const saving = ref(false);
const err = ref("");

const values = computed(() => props.catalog?.values || {});
const settings = computed(() => values.value.settings || {});
const minMarkup = computed(() => Number(settings.value.minMarkup ?? 70));

const isLm = (it: any) => {
  const p = (values.value.products || []).find((x: any) => x.id === it.product);
  return !!(p && p.isLm);
};
const isAcp = (it: any) => it.product === "acp";
const subsFor = (pid: string) => (values.value.subs || {})[pid] || [];
const subEligible = (st: string, list: string[]) => list.includes(st);
const glassTypes = computed(() => values.value.gc?.types || []);
const thicknesses = (tid: string) => (values.value.gc?.thicknesses || {})[tid] || [];
const colours = computed(() => values.value.gc?.colours || []);
const acpPanels = computed(() => values.value.acpPanels || []);
const isDgu = (tid: string) => {
  const t = glassTypes.value.find((x: any) => x.id === tid);
  return !!(t && t.isDGU);
};

const prodLabel = (pid: string) => (values.value.products || []).find((p: any) => p.id === pid)?.label || pid;
const subLabel = (stid: string) => {
  for (const pid of Object.keys(values.value.subs || {})) {
    const s = (values.value.subs[pid] || []).find((x: any) => x.id === stid);
    if (s) return s.label;
  }
  return stid;
};

const onProductChange = (it: any) => {
  const subs = subsFor(it.product);
  it.subTypeId = subs.length ? subs[0].id : "";
  if (!isAcp(it) && !isLm(it)) { /* keep glass */ }
  if (it.product === "acp") { it.glassTypeId = ""; }
};

const clampMarkup = () => {
  const v = Number(form.value.markupPct);
  if (!isNaN(v)) form.value.markupPct = Math.max(v, minMarkup.value);
};

// live pricing: recalc on any spec change (debounced)
let timer: any = null;
const recalc = () => {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    pricing.value = true;
    try {
      totals.value = await request("/api/quotes/calculate", {
        method: "POST",
        body: { items: form.value.items, markupPct: form.value.markupPct, vatPct: form.value.vatPct },
      });
    } catch (e: any) {
      /* transient - keep last good totals */
    } finally {
      pricing.value = false;
    }
  }, 350);
};

watch(() => JSON.stringify(form.value.items) + form.value.markupPct + form.value.vatPct, recalc);
onMounted(recalc);

const fmtN = (n: number) => "₦" + Math.round(n || 0).toLocaleString("en-NG");

const validate = (): string => {
  if (!form.value.meta.clientName?.trim()) return "Client name is required";
  if (!form.value.items.length) return "Add at least one item";
  for (const [i, it] of form.value.items.entries()) {
    const n = i + 1;
    if (isLm(it)) {
      if (!it.length || Number(it.length) <= 0) return `Item ${n}: length in metres is required`;
      if (!it.height || Number(it.height) <= 0) return `Item ${n}: height in mm is required`;
    } else {
      if (!it.width || Number(it.width) <= 0) return `Item ${n}: width in mm is required`;
      if (!it.height || Number(it.height) <= 0) return `Item ${n}: height in mm is required`;
    }
    if (Number(it.qty) < 1) return `Item ${n}: quantity must be at least 1`;
    if (isAcp(it)) {
      if (!it.acpPanelId && it.ovGlassRate == null) return `Item ${n}: choose an ACP panel`;
    } else if (!it.glassTypeId || !it.glassThickness) {
      return `Item ${n}: complete the glass specification`;
    }
  }
  return "";
};

const save = async () => {
  err.value = validate();
  if (err.value) return;
  saving.value = true;
  try {
    const meta = { ...form.value.meta, projectId: form.value.meta.projectId || null };
    if (!form.value.quoteId) {
      const q = await request("/api/quotes", {
        method: "POST",
        body: { ...meta, items: form.value.items, markupPct: form.value.markupPct, vatPct: form.value.vatPct },
      });
      emit("saved", `Quote ${q.number} created`);
    } else if (form.value.status === "draft" && form.value.revisionId) {
      await request(`/api/quotes/${form.value.quoteId}`, { method: "PUT", body: meta });
      await request(`/api/quotes/${form.value.quoteId}/revisions/${form.value.revisionId}`, {
        method: "PUT",
        body: { items: form.value.items, markupPct: form.value.markupPct, vatPct: form.value.vatPct },
      });
      emit("saved", `Quote ${form.value.number} saved`);
    } else {
      // latest revision already sent/won/lost: save changes as a new revision
      const r = await request(`/api/quotes/${form.value.quoteId}/revisions`, {
        method: "POST",
        body: { items: form.value.items, markupPct: form.value.markupPct, vatPct: form.value.vatPct, note: "Priced revision after update" },
      });
      await request(`/api/quotes/${form.value.quoteId}`, { method: "PUT", body: meta });
      emit("saved", `New Rev.${r.rev} created for ${form.value.number}`);
    }
  } catch (e: any) {
    err.value = e.message;
  } finally {
    saving.value = false;
  }
};

const addItem = () =>
  form.value.items.push({
    id: Math.random().toString(36).slice(2, 10),
    product: "et_window", subTypeId: "etw_fixed",
    width: null, height: null, length: null, qty: 1,
    glassTypeId: "", glassThickness: "", glassColour: "",
    glassDguOuter: "", glassDguInner: "", acpPanelId: "", ovGlassRate: null,
    hasMosq: false, hasSubframe: false, elements: [], note: "",
  });
const removeItem = (i: number) => form.value.items.splice(i, 1);

const bomOf = (it: any) => totals.value?.items?.find((x: any) => x.id === it.id)?.bom || null;
</script>

<template>
  <div class="wrap">
    <div class="head">
      <div>
        <button class="back" @click="emit('cancel')">← Quotations</button>
        <h1 class="title">
          {{ form.quoteId ? `Edit ${form.number}` : "New Quotation" }}
          <span v-if="form.quoteId" class="revtag">Rev.{{ form.rev }} · {{ form.status }}</span>
        </h1>
      </div>
      <div style="display: flex; gap: 8px">
        <button class="btn ghost" @click="emit('cancel')">Cancel</button>
        <button class="btn primary" :disabled="saving || pricing" @click="save">
          {{ saving ? "Saving..." : form.quoteId ? "Save Changes" : "Create Quote" }}
        </button>
      </div>
    </div>

    <div v-if="err" class="alert">{{ err }}</div>

    <div class="cols">
      <!-- LEFT: meta + items -->
      <div class="col-l">
        <div class="card">
          <div class="card-t">Quote Details</div>
          <div class="grid2">
            <label class="f">Client Name *<input v-model="form.meta.clientName" class="inp" placeholder="e.g. Lekki Towers Ltd" /></label>
            <label class="f">Link to Project
              <select v-model="form.meta.projectId" class="inp">
                <option value="">No project link</option>
                <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </label>
            <label class="f">Client Phone<input v-model="form.meta.clientPhone" class="inp" placeholder="+234 ..." /></label>
            <label class="f">Client Email<input v-model="form.meta.clientEmail" class="inp" placeholder="name@company.com" /></label>
            <label class="f">Sales Person<input v-model="form.meta.salesPerson" class="inp" placeholder="e.g. Chidi Okafor" /></label>
            <label class="f">Internal Notes<input v-model="form.meta.notes" class="inp" placeholder="Not shown on the printed quote" /></label>
          </div>
        </div>

        <div class="card">
          <div class="card-t">Items <span class="hint">dimensions in mm{{ " " }}(balustrades: length in metres)</span></div>

          <div v-for="(it, i) in form.items" :key="it.id" class="item">
            <div class="item-head">
              <span class="item-n">Item {{ i + 1 }}</span>
              <span v-if="bomOf(it)" class="item-cost">{{ fmtN(bomOf(it).total) }}</span>
              <button v-if="form.items.length > 1" class="x" title="Remove item" @click="removeItem(i)">✕</button>
            </div>

            <div class="grid3">
              <label class="f">Product
                <select v-model="it.product" class="inp" @change="onProductChange(it)">
                  <option v-for="p in values.products" :key="p.id" :value="p.id">{{ p.label }}</option>
                </select>
              </label>
              <label class="f">Type
                <select v-model="it.subTypeId" class="inp">
                  <option v-for="s in subsFor(it.product)" :key="s.id" :value="s.id">{{ s.label }}</option>
                </select>
              </label>
              <label class="f">Quantity
                <input v-model.number="it.qty" type="number" min="1" class="inp" />
              </label>

              <template v-if="isLm(it)">
                <label class="f">Length (m)<input v-model.number="it.length" type="number" step="0.1" min="0" class="inp" placeholder="e.g. 5" /></label>
                <label class="f">Height (mm)<input v-model.number="it.height" type="number" min="0" class="inp" placeholder="e.g. 1200" /></label>
              </template>
              <template v-else>
                <label class="f">Width (mm)<input v-model.number="it.width" type="number" min="0" class="inp" placeholder="e.g. 1200" /></label>
                <label class="f">Height (mm)<input v-model.number="it.height" type="number" min="0" class="inp" placeholder="e.g. 1500" /></label>
              </template>

              <template v-if="isAcp(it)">
                <label class="f">ACP Panel
                  <select v-model="it.acpPanelId" class="inp">
                    <option value="">Select panel</option>
                    <option v-for="p in acpPanels" :key="p.id" :value="p.id">{{ p.name }}</option>
                  </select>
                </label>
                <label class="f">Custom rate/m² override<input v-model.number="it.ovGlassRate" type="number" min="0" class="inp" placeholder="Optional" /></label>
              </template>
              <template v-else>
                <label class="f">Glass Type
                  <select v-model="it.glassTypeId" class="inp">
                    <option value="">Select glass</option>
                    <option v-for="g in glassTypes" :key="g.id" :value="g.id">{{ g.label }}</option>
                  </select>
                </label>
                <label class="f">Thickness
                  <select v-model="it.glassThickness" class="inp" :disabled="!it.glassTypeId">
                    <option value="">Select</option>
                    <option v-for="t in thicknesses(it.glassTypeId)" :key="t" :value="t">{{ t }}</option>
                  </select>
                </label>
                <label v-if="isDgu(it.glassTypeId)" class="f">Outer Colour
                  <select v-model="it.glassDguOuter" class="inp">
                    <option value="">Select</option>
                    <option v-for="c in colours" :key="c.id" :value="c.id">{{ c.label }}</option>
                  </select>
                </label>
                <label v-if="isDgu(it.glassTypeId)" class="f">Inner Colour
                  <select v-model="it.glassDguInner" class="inp">
                    <option value="">Select</option>
                    <option v-for="c in colours" :key="c.id" :value="c.id">{{ c.label }}</option>
                  </select>
                </label>
                <label v-else class="f">Glass Colour
                  <select v-model="it.glassColour" class="inp">
                    <option value="">Select</option>
                    <option v-for="c in colours" :key="c.id" :value="c.id">{{ c.label }}</option>
                  </select>
                </label>
              </template>

              <label class="f">Item Note<input v-model="it.note" class="inp" placeholder="Optional, shown on BOM" /></label>
            </div>

            <div class="toggles">
              <label
                v-if="subEligible(it.subTypeId, values.settings ? [] : []) || true"
                class="tgl"
                :class="{ off: !['etw_single','etw_double','etw_s2','etw_s3','etw_s4','ctw_single','ctw_double','ctw_s2','ctw_s3','ctw_s4','etd_s2','etd_s3','etd_s4','ctd_s2','ctd_s3','ctd_s4'].includes(it.subTypeId) }"
              >
                <input v-model="it.hasMosq" type="checkbox" :disabled="!['etw_single','etw_double','etw_s2','etw_s3','etw_s4','ctw_single','ctw_double','ctw_s2','ctw_s3','ctw_s4','etd_s2','etd_s3','etd_s4','ctd_s2','ctd_s3','ctd_s4'].includes(it.subTypeId)" />
                Mosquito Net
              </label>
              <label
                class="tgl"
                :class="{ off: !['etw_fixed','etw_single','etw_double','etw_s2','etw_s3','etw_s4','ctw_fixed','ctw_single','ctw_double','ctw_s2','ctw_s3','ctw_s4','etd_single','etd_double','etd_s2','etd_s3','etd_s4','ctd_single','ctd_double','ctd_s2','ctd_s3','ctd_s4','etcw_g','ctcw_g','ctm_s2','ctm_s3','ctm_s4'].includes(it.subTypeId) }"
              >
                <input v-model="it.hasSubframe" type="checkbox" :disabled="!['etw_fixed','etw_single','etw_double','etw_s2','etw_s3','etw_s4','ctw_fixed','ctw_single','ctw_double','ctw_s2','ctw_s3','ctw_s4','etd_single','etd_double','etd_s2','etd_s3','etd_s4','ctd_single','ctd_double','ctd_s2','ctd_s3','ctd_s4','etcw_g','ctcw_g','ctm_s2','ctm_s3','ctm_s4'].includes(it.subTypeId)" />
                Sub-Frame
              </label>
            </div>

            <div v-if="bomOf(it)" class="bomline">
              <span>{{ bomOf(it).area }} m²</span>
              <span>Profile {{ fmtN(bomOf(it).profileCost) }}</span>
              <span>Glass {{ fmtN(bomOf(it).glassCost) }}</span>
              <span>Gasket {{ fmtN(bomOf(it).gasketCost) }}</span>
              <span>Hardware {{ fmtN(bomOf(it).hwCost) }}</span>
              <span>Fab {{ fmtN(bomOf(it).fabCost) }}</span>
              <span>Install {{ fmtN(bomOf(it).instCost) }}</span>
              <span v-if="bomOf(it).mosqCost">Net {{ fmtN(bomOf(it).mosqCost) }}</span>
              <span v-if="bomOf(it).subframeCost">Sub-frame {{ fmtN(bomOf(it).subframeCost) }}</span>
              <span v-if="bomOf(it).sealantCost">Sealant {{ fmtN(bomOf(it).sealantCost) }}</span>
            </div>
          </div>

          <button class="btn add" @click="addItem">+ Add Item</button>
        </div>
      </div>

      <!-- RIGHT: live totals -->
      <div class="col-r">
        <div class="card sticky">
          <div class="card-t">Pricing</div>
          <div class="grid2">
            <label class="f">Markup %<input v-model.number="form.markupPct" type="number" class="inp" :min="minMarkup" @blur="clampMarkup" /></label>
            <label class="f">VAT %<input v-model.number="form.vatPct" type="number" step="0.1" class="inp" /></label>
          </div>
          <div class="hint" style="margin: -4px 0 10px">Minimum markup {{ minMarkup }}% is enforced on save.</div>

          <div class="tot">
            <div class="trow"><span>Cost (BOM)</span><strong>{{ fmtN(totals?.cost) }}</strong></div>
            <div class="trow"><span>Markup ({{ form.markupPct }}%)</span><strong>{{ fmtN(totals?.mkAmt) }}</strong></div>
            <div class="trow"><span>Subtotal</span><strong>{{ fmtN(totals?.sub) }}</strong></div>
            <div class="trow"><span>VAT ({{ form.vatPct }}%)</span><strong>{{ fmtN(totals?.vat) }}</strong></div>
            <div class="trow grand"><span>Grand Total</span><strong>{{ fmtN(totals?.total) }}</strong></div>
          </div>

          <div class="pay">
            <div class="pay-t">Payment Terms</div>
            <div class="pay-b">{{ settings.paymentTerms }}</div>
            <div class="pay-t" style="margin-top: 8px">Validity</div>
            <div class="pay-b">{{ settings.validity }} days</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wrap { padding: 22px; max-width: 1200px; margin: 0 auto; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.back { border: none; background: none; color: #94a3b8; font-family: inherit; font-size: 11.5px; font-weight: 700; cursor: pointer; padding: 0; margin-bottom: 6px; }
.back:hover { color: #b45309; }
.title { font-size: 19px; font-weight: 800; color: #0f172a; letter-spacing: -.4px; margin: 0; }
.revtag { font-size: 10.5px; font-weight: 700; color: #b45309; background: #fffbeb; border: 1px solid #fde68a; border-radius: 20px; padding: 2px 9px; margin-left: 8px; vertical-align: 2px; text-transform: uppercase; }
.btn { border-radius: 8px; padding: 9px 16px; font-family: inherit; font-size: 12.5px; font-weight: 700; cursor: pointer; border: 1px solid #e2e8f0; background: #fff; color: #475569; }
.btn.primary { background: linear-gradient(135deg, #f59e0b, #ea580c); border: none; color: #fff; }
.btn.primary:disabled { opacity: .6; cursor: wait; }
.btn.ghost:hover { border-color: #94a3b8; }
.btn.add { width: 100%; margin-top: 10px; border-style: dashed; color: #b45309; }
.btn.add:hover { border-color: #f59e0b; background: #fffbeb; }
.alert { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; border-radius: 9px; padding: 10px 13px; font-size: 12.5px; font-weight: 600; margin-bottom: 14px; }
.cols { display: grid; grid-template-columns: 1fr 300px; gap: 16px; align-items: start; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.sticky { position: sticky; top: 16px; }
.card-t { font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .8px; color: #0f172a; margin-bottom: 12px; }
.hint { font-size: 10.5px; color: #94a3b8; font-weight: 600; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 12px; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px 12px; }
.f { font-size: 10.5px; font-weight: 700; color: #64748b; display: flex; flex-direction: column; gap: 4px; }
.inp { padding: 8px 10px; border: 1px solid #dde4ec; border-radius: 8px; font-family: inherit; font-size: 12.5px; background: #fff; outline: none; width: 100%; box-sizing: border-box; }
.inp:focus { border-color: #f59e0b; }
.item { border: 1px solid #f1f5f9; border-radius: 10px; padding: 12px; margin-bottom: 10px; background: #fcfcfd; }
.item-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.item-n { font-size: 11px; font-weight: 800; color: #b45309; text-transform: uppercase; letter-spacing: .6px; }
.item-cost { font-size: 12.5px; font-weight: 800; color: #0f172a; margin-left: auto; }
.x { border: none; background: none; color: #cbd5e1; cursor: pointer; font-size: 13px; }
.x:hover { color: #ef4444; }
.toggles { display: flex; gap: 8px; margin-top: 10px; }
.tgl { display: flex; align-items: center; gap: 6px; background: #f0fdf4; border: 1px solid #bbf7d0; color: #15803d; border-radius: 8px; padding: 5px 10px; font-size: 11px; font-weight: 700; cursor: pointer; }
.tgl.off { background: #f8fafc; border-color: #e2e8f0; color: #cbd5e1; }
.bomline { display: flex; flex-wrap: wrap; gap: 5px 12px; margin-top: 10px; padding-top: 9px; border-top: 1px dashed #e2e8f0; font-size: 10.5px; color: #64748b; font-weight: 600; }
.tot { border-top: 1px solid #f1f5f9; padding-top: 10px; }
.trow { display: flex; justify-content: space-between; font-size: 12px; color: #64748b; padding: 4px 0; font-weight: 600; }
.trow strong { color: #0f172a; }
.trow.grand { border-top: 2px solid #0f172a; margin-top: 6px; padding-top: 9px; font-size: 13.5px; color: #0f172a; }
.trow.grand strong { color: #b45309; font-size: 16px; }
.pay { background: #fffbeb; border: 1px solid #fde68a; border-radius: 9px; padding: 10px 12px; margin-top: 12px; }
.pay-t { font-size: 9.5px; font-weight: 800; text-transform: uppercase; letter-spacing: .7px; color: #b45309; }
.pay-b { font-size: 10.5px; color: #78716c; margin-top: 2px; line-height: 1.45; }
@media (max-width: 980px) {
  .cols { grid-template-columns: 1fr; }
  .grid3 { grid-template-columns: 1fr 1fr; }
  .sticky { position: static; }
}
@media (max-width: 640px) {
  .grid2, .grid3 { grid-template-columns: 1fr; }
  .wrap { padding: 14px; }
}
</style>
