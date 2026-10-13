<script setup lang="ts">
// Rate Card (admin): pricing rates, commercial settings, glass and mosquito-net prices.
// Collapsible sections, search, formatted inputs, field errors, and a sticky
// unsaved-changes bar so edits are never lost or saved by accident.
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();
const { confirm } = useConfirm();
const user = useAuth().user;
const isAdmin = computed(() => user.value?.platformRole === "admin");

const values = ref<any>({});
const rates = ref<any>({});
const settings = ref<any>({});
const basePrices = ref<Record<string, number>>({});
const mosqRates = ref<Record<string, number>>({});
const saving = ref(false);
const loaded = ref(false);
const query = ref("");
const tried = ref(false);
const original = ref("");

const GLASS_LABELS: Record<string, string> = {
  single: "Single annealed", tempered: "Tempered / toughened", laminated: "Laminated", dgu: "Double glazed (DGU)",
};

const snapshot = () => JSON.stringify({ r: rates.value, s: settings.value, g: basePrices.value, m: mosqRates.value });
const load = async () => {
  try {
    const cat = await request("/api/quotes/catalog");
    values.value = cat.values || {};
  } catch (e: any) {
    notify(e.message, "error");
    values.value = {};
  }
  rates.value = JSON.parse(JSON.stringify(values.value.rates || {}));
  rates.value.brandRates = rates.value.brandRates || { EUROTEC: 3400, CORTIZO: 3400, DEFAULT: 3400 };
  settings.value = JSON.parse(JSON.stringify(values.value.settings || {}));
  basePrices.value = JSON.parse(JSON.stringify(values.value.gc?.basePrices || {}));
  mosqRates.value = JSON.parse(JSON.stringify(values.value.mosqRates || {}));
  original.value = snapshot();
  tried.value = false;
  loaded.value = true;
};
onMounted(load);

// ---- what changed ----
const orig = computed(() => (original.value ? JSON.parse(original.value) : { r: {}, s: {}, g: {}, m: {} }));
const same = (a: any, b: any) => JSON.stringify(a) === JSON.stringify(b);
const changed = {
  rate: (k: string) => !same(rates.value[k], orig.value.r[k]),
  brand: (k: string) => !same(rates.value.brandRates?.[k], orig.value.r.brandRates?.[k]),
  setting: (k: string) => !same(settings.value[k], orig.value.s[k]),
  glass: (k: string) => !same(basePrices.value[k], orig.value.g[k]),
  mosq: (k: string) => !same(mosqRates.value[k], orig.value.m[k]),
};
const RATE_FIELDS = [
  { k: "gasketRate", label: "Gasket", unit: "/m" },
  { k: "fabRate", label: "Fabrication", unit: "/m²" },
  { k: "installRate", label: "Installation", unit: "/m²" },
  { k: "subframeRate", label: "Sub-frame", unit: "/m" },
  { k: "sealantRate", label: "Sealant", unit: "/m" },
];
const BRANDS = [
  { k: "EUROTEC", label: "EUROTEC profile" }, { k: "CORTIZO", label: "CORTIZO profile" }, { k: "DEFAULT", label: "Other profiles" },
];
const counts = computed(() => ({
  rates: BRANDS.filter((b) => changed.brand(b.k)).length + RATE_FIELDS.filter((f) => changed.rate(f.k)).length,
  settings: ["defaultMarkup", "minMarkup", "vatRate", "validity", "paymentTerms", "tcs"].filter((k) => changed.setting(k)).length,
  glass: Object.keys(basePrices.value).filter((k) => changed.glass(k)).length,
  mosq: Object.keys(mosqRates.value).filter((k) => changed.mosq(k)).length,
}));
const unsaved = computed(() => counts.value.rates + counts.value.settings + counts.value.glass + counts.value.mosq);

// ---- rows, grouped and searchable ----
const q = computed(() => query.value.trim().toLowerCase());
const hit = (label: string) => !q.value || label.toLowerCase().includes(q.value);
const glassGroups = computed(() => {
  const th = values.value.gc?.thicknesses || {};
  return Object.entries(th)
    .map(([type, list]) => ({
      type, label: GLASS_LABELS[type] || type,
      rows: (list as string[]).map((t) => ({ key: `${type}__${t}`, label: t })).filter((r) => hit(`${GLASS_LABELS[type] || type} ${r.label}`)),
    }))
    .filter((g) => g.rows.length);
});
const mosqGroups = computed(() => {
  const subs = values.value.subs || {};
  const groups: { label: string; rows: { id: string; label: string }[] }[] = [];
  for (const p of values.value.products || []) {
    const rows = (subs[p.id] || [])
      .filter((s: any) => s.id in mosqRates.value)
      .map((s: any) => ({ id: s.id, label: s.label }))
      .filter((r: any) => hit(`${p.label} ${r.label}`));
    if (rows.length) groups.push({ label: p.label.replace(" Aluminium", ""), rows });
  }
  return groups;
});
const showRates = computed(() => !q.value || [...BRANDS, ...RATE_FIELDS].some((f) => hit(f.label)));
const showSettings = computed(() => !q.value || hit("markup vat validity payment terms conditions"));

// ---- field-level validation ----
const bad = (v: any) => v === null || v === undefined || v === "" || isNaN(Number(v)) || Number(v) < 0;
const errors = computed(() => {
  const e: Record<string, string> = {};
  const s = settings.value;
  if (bad(s.minMarkup)) e.minMarkup = "Enter a number of 0 or more";
  if (bad(s.defaultMarkup)) e.defaultMarkup = "Enter a number of 0 or more";
  else if (Number(s.defaultMarkup) < Number(s.minMarkup)) e.defaultMarkup = `Must be at least the ${s.minMarkup}% minimum`;
  if (bad(s.vatRate)) e.vatRate = "Enter a number of 0 or more";
  if (!(Number(s.validity) >= 1)) e.validity = "At least 1 day";
  for (const b of BRANDS) if (bad(rates.value.brandRates?.[b.k])) e[`b_${b.k}`] = "Required";
  for (const f of RATE_FIELDS) if (bad(rates.value[f.k])) e[f.k] = "Required";
  for (const [k, v] of Object.entries(basePrices.value)) if (bad(v)) e[`g_${k}`] = "Required";
  for (const [k, v] of Object.entries(mosqRates.value)) if (bad(v)) e[`m_${k}`] = "Required";
  return e;
});
const err = (k: string) => (tried.value || unsaved.value) && errors.value[k];

const save = async () => {
  tried.value = true;
  const n = Object.keys(errors.value).length;
  if (n) {
    notify(`Fix ${n} field${n === 1 ? "" : "s"} marked in red before saving`, "error");
    await nextTick();
    document.querySelector<HTMLElement>(".rc [aria-invalid=true]")?.focus();
    return;
  }
  saving.value = true;
  try {
    await request("/api/quotes/catalog/rates", { method: "PUT", body: { value: rates.value } });
    await request("/api/quotes/catalog/settings", { method: "PUT", body: { value: settings.value } });
    const gc = JSON.parse(JSON.stringify(values.value.gc || {}));
    gc.basePrices = basePrices.value;
    await request("/api/quotes/catalog/gc", { method: "PUT", body: { value: gc } });
    await request("/api/quotes/catalog/mosqRates", { method: "PUT", body: { value: mosqRates.value } });
    await load();
    notify("Rate card saved. New quotes use these rates now; saved quotes keep their prices.");
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    saving.value = false;
  }
};
const discard = async () => {
  if (await confirm({ title: `Discard ${unsaved.value} change${unsaved.value === 1 ? "" : "s"}?`, message: "The rate card goes back to the saved values.", confirmLabel: "Discard", danger: true })) load();
};

// leaving with unsaved edits asks first (sidebar, Back, closing the tab)
const router = useRouter();
const offGuard = router.beforeEach(async () =>
  !unsaved.value || saving.value || (await confirm({ title: "Leave without saving?", message: `${unsaved.value} rate change(s) haven't been saved.`, confirmLabel: "Leave without saving", cancelLabel: "Keep editing", danger: true }))
);
const onUnload = (e: BeforeUnloadEvent) => { if (unsaved.value) { e.preventDefault(); e.returnValue = ""; } };
onMounted(() => window.addEventListener("beforeunload", onUnload));
onUnmounted(() => { offGuard(); window.removeEventListener("beforeunload", onUnload); });
</script>

<template>
  <div class="wrap rc">
    <div v-if="!isAdmin" class="alert" role="alert">Only platform admins can edit the rate card.</div>
    <template v-else>
      <div class="head">
        <div>
          <h1 class="title">Rate Card</h1>
          <p class="sub">Prices used for every new quote. Saved quotes keep the prices they were created with.</p>
        </div>
        <label class="search">
          <UiIcon name="search" :size="14" class="s-ic" />
          <input v-model="query" class="inp" placeholder="Find a rate, e.g. laminated or sliding" aria-label="Find a rate" />
        </label>
      </div>

      <div v-if="!loaded" class="skel-wrap" aria-busy="true" aria-label="Loading rate card">
        <div v-for="n in 3" :key="n" class="skel-card"><div class="skel" style="width: 30%" /><div class="skel" /><div class="skel" /><div class="skel" style="width: 70%" /></div>
      </div>
      <template v-else>
        <details v-show="showRates" class="sec" open>
          <summary>
            <span class="sec-t">Materials and labour</span>
            <span v-if="counts.rates" class="badge">{{ counts.rates }} changed</span>
          </summary>
          <div class="grid3">
            <label v-for="b in BRANDS" v-show="hit(b.label)" :key="b.k" class="f" :class="{ ch: changed.brand(b.k) }">
              <span>{{ b.label }}</span>
              <UiNumberInput v-model="rates.brandRates[b.k]" prefix="₦" suffix="/kg" :invalid="!!err(`b_${b.k}`)" />
              <span v-if="err(`b_${b.k}`)" class="fe">{{ err(`b_${b.k}`) }}</span>
            </label>
            <label v-for="f in RATE_FIELDS" v-show="hit(f.label)" :key="f.k" class="f" :class="{ ch: changed.rate(f.k) }">
              <span>{{ f.label }}</span>
              <UiNumberInput v-model="rates[f.k]" prefix="₦" :suffix="f.unit" :invalid="!!err(f.k)" />
              <span v-if="err(f.k)" class="fe">{{ err(f.k) }}</span>
            </label>
          </div>
        </details>

        <details v-show="showSettings" class="sec" open>
          <summary>
            <span class="sec-t">Markup, VAT and terms</span>
            <span v-if="counts.settings" class="badge">{{ counts.settings }} changed</span>
          </summary>
          <div class="grid4">
            <label class="f" :class="{ ch: changed.setting('defaultMarkup') }">
              <span>Default markup</span>
              <UiNumberInput v-model="settings.defaultMarkup" suffix="%" :invalid="!!err('defaultMarkup')" />
              <span v-if="err('defaultMarkup')" class="fe">{{ err("defaultMarkup") }}</span>
            </label>
            <label class="f" :class="{ ch: changed.setting('minMarkup') }">
              <span>Minimum markup</span>
              <UiNumberInput v-model="settings.minMarkup" suffix="%" :invalid="!!err('minMarkup')" />
              <span v-if="err('minMarkup')" class="fe">{{ err("minMarkup") }}</span>
              <span v-else class="hint">Quotes can't go below this</span>
            </label>
            <label class="f" :class="{ ch: changed.setting('vatRate') }">
              <span>VAT</span>
              <UiNumberInput v-model="settings.vatRate" suffix="%" :decimals="2" :invalid="!!err('vatRate')" />
              <span v-if="err('vatRate')" class="fe">{{ err("vatRate") }}</span>
            </label>
            <label class="f" :class="{ ch: changed.setting('validity') }">
              <span>Quote validity</span>
              <UiNumberInput v-model="settings.validity" suffix="days" :decimals="0" :invalid="!!err('validity')" />
              <span v-if="err('validity')" class="fe">{{ err("validity") }}</span>
            </label>
          </div>
          <div class="grid2" style="margin-top: 12px">
            <label class="f" :class="{ ch: changed.setting('paymentTerms') }">
              <span>Payment terms</span>
              <textarea v-model="settings.paymentTerms" class="inp" rows="3"></textarea>
            </label>
            <label class="f" :class="{ ch: changed.setting('tcs') }">
              <span>Terms and conditions <span class="hint">(printed on quotes, one per line)</span></span>
              <textarea v-model="settings.tcs" class="inp" rows="5"></textarea>
            </label>
          </div>
        </details>

        <details v-show="glassGroups.length" class="sec" :open="!!q || undefined">
          <summary>
            <span class="sec-t">Glass prices</span>
            <span class="cnt">{{ Object.keys(basePrices).length }} prices</span>
            <span v-if="counts.glass" class="badge">{{ counts.glass }} changed</span>
          </summary>
          <p class="hint" style="margin: -2px 0 12px">Per m², before colour premiums (Grey +₦3,500, Low-E +₦8,000, Frosted +₦4,500). DGU adds both panes' premiums.</p>
          <fieldset v-for="g in glassGroups" :key="g.type" class="grp">
            <legend>{{ g.label }}</legend>
            <div class="grid4">
              <label v-for="r in g.rows" :key="r.key" class="f" :class="{ ch: changed.glass(r.key) }">
                <span>{{ r.label }}</span>
                <UiNumberInput v-model="basePrices[r.key]" prefix="₦" suffix="/m²" :invalid="!!err(`g_${r.key}`)" />
              </label>
            </div>
          </fieldset>
        </details>

        <details v-show="mosqGroups.length" class="sec" :open="!!q || undefined">
          <summary>
            <span class="sec-t">Mosquito nets</span>
            <span class="cnt">{{ Object.keys(mosqRates).length }} prices</span>
            <span v-if="counts.mosq" class="badge">{{ counts.mosq }} changed</span>
          </summary>
          <p class="hint" style="margin: -2px 0 12px">Per m² of the item when "Mosquito net" is ticked. Sliding types are charged on half the area. ₦0 means free.</p>
          <fieldset v-for="g in mosqGroups" :key="g.label" class="grp">
            <legend>{{ g.label }}</legend>
            <div class="grid4">
              <label v-for="r in g.rows" :key="r.id" class="f" :class="{ ch: changed.mosq(r.id) }">
                <span>{{ r.label }}</span>
                <UiNumberInput v-model="mosqRates[r.id]" prefix="₦" suffix="/m²" :invalid="!!err(`m_${r.id}`)" />
              </label>
            </div>
          </fieldset>
        </details>

        <p v-if="q && !showRates && !showSettings && !glassGroups.length && !mosqGroups.length" class="empty">No rates match "{{ query }}"</p>
      </template>

      <!-- sticky save bar: only when something changed -->
      <div v-if="unsaved" class="savebar" role="region" aria-label="Unsaved changes">
        <span><strong>{{ unsaved }}</strong> unsaved change{{ unsaved === 1 ? "" : "s" }}</span>
        <div style="display: flex; gap: 8px">
          <button class="btn btn-secondary" :disabled="saving" @click="discard">Discard</button>
          <button class="btn btn-accent" :disabled="saving" @click="save">{{ saving ? "Saving…" : "Save rate card" }}</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.wrap { padding: 22px 22px 110px; max-width: 1200px; margin: 0 auto; }
.head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.title { font-size: 20px; font-weight: 800; color: #0f172a; }
.sub { font-size: 12.5px; color: #475569; margin-top: 4px; max-width: 560px; }
.search { position: relative; width: 320px; max-width: 100%; display: block; }
.s-ic { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #64748b; }
.search .inp { padding-left: 32px; }
.alert { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; border-radius: 9px; padding: 12px 14px; font-size: 12.5px; font-weight: 600; }
.sec { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0 16px; margin-bottom: 12px; }
.sec[open] { padding-bottom: 16px; }
.sec summary { display: flex; align-items: center; gap: 10px; padding: 14px 0; cursor: pointer; list-style: none; min-height: 44px; }
.sec summary::-webkit-details-marker { display: none; }
.sec summary::before { content: "›"; color: #64748b; font-size: 18px; transition: transform .15s; display: inline-block; width: 12px; }
.sec[open] summary::before { transform: rotate(90deg); }
.sec-t { font-size: 13px; font-weight: 800; color: #0f172a; text-transform: uppercase; letter-spacing: .6px; }
.cnt { font-size: 12px; color: #64748b; font-weight: 600; }
.badge { font-size: 11px; font-weight: 800; color: #92400e; background: #fef3c7; border-radius: 20px; padding: 2px 9px; }
.grp { border: none; padding: 0; margin: 0 0 14px; }
.grp legend { font-size: 12px; font-weight: 800; color: #334155; margin-bottom: 8px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.grid3 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px 12px; }
.f { font-size: 12px; font-weight: 700; color: #334155; display: flex; flex-direction: column; gap: 5px; position: relative; }
.f.ch > span:first-child::after { content: " • edited"; color: #b45309; font-weight: 700; }
.f.ch :deep(.inp) { background: #fffbeb; border-color: #f59e0b; }
.fe { font-size: 11.5px; color: #b91c1c; font-weight: 600; }
.hint { font-size: 11.5px; color: #64748b; font-weight: 500; }
.inp { width: 100%; resize: vertical; }
.empty { text-align: center; color: #64748b; padding: 30px; }
.savebar {
  position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); z-index: 40; width: min(640px, calc(100% - 32px));
  display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px 10px 18px;
  background: #0f172a; color: #fff; border-radius: 12px; box-shadow: 0 16px 40px rgba(15,23,42,.3); font-size: 13.5px;
}
.savebar .btn-secondary { background: transparent; color: #fff; border-color: #475569; }
.skel-wrap { display: grid; gap: 12px; }
.skel-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; display: grid; gap: 10px; }
@media (max-width: 960px) { .grid3, .grid4 { grid-template-columns: 1fr 1fr; } }
@media (max-width: 560px) { .grid2, .grid3, .grid4 { grid-template-columns: 1fr; } .search { width: 100%; } }
</style>
