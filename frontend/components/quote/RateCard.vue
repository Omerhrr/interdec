<script setup lang="ts">
// Rate Card (admin) - edit pricing rates, settings and glass prices; stored as catalogue overrides
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();
const user = useAuth().user;
const isAdmin = computed(() => user.value?.platformRole === "admin");

const values = ref<any>({});
const rates = ref<any>({});
const settings = ref<any>({});
const basePrices = ref<any>({});
const saving = ref(false);
const loaded = ref(false);

const GLASS_LABELS: Record<string, string> = {
  single: "Single Annealed", tempered: "Tempered / Toughened",
  laminated: "Laminated", dgu: "Double Glaze (DGU)",
};

const load = async () => {
  try {
    const cat = await request("/api/quotes/catalog");
    values.value = cat.values || {};
  } catch (e: any) {
    notify(e.message, "error");
    values.value = {};
  }
  rates.value = JSON.parse(JSON.stringify(values.value.rates || {}));
  settings.value = JSON.parse(JSON.stringify(values.value.settings || {}));
  basePrices.value = JSON.parse(JSON.stringify(values.value.gc?.basePrices || {}));
  loaded.value = true;
};
onMounted(load);

const priceRows = computed(() => {
  const th = values.value.gc?.thicknesses || {};
  const rows: any[] = [];
  for (const [type, list] of Object.entries(th)) {
    (list as string[]).forEach((t) => {
      rows.push({ key: `${type}__${t}`, type, label: t });
    });
  }
  return rows;
});

const save = async () => {
  saving.value = true;
  try {
    await request("/api/quotes/catalog/rates", { method: "PUT", body: { value: rates.value } });
    await request("/api/quotes/catalog/settings", { method: "PUT", body: { value: settings.value } });
    const gc = JSON.parse(JSON.stringify(values.value.gc || {}));
    gc.basePrices = basePrices.value;
    await request("/api/quotes/catalog/gc", { method: "PUT", body: { value: gc } });
    notify("Rate card saved. New quotes price with the new rates immediately.");
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    saving.value = false;
  }
};

const fmtN = (n: number) => "₦" + Math.round(n || 0).toLocaleString("en-NG");
</script>

<template>
  <div class="wrap">
    <div v-if="!isAdmin" class="alert">Only platform admins can edit the rate card.</div>
    <template v-else>
      <div class="head">
        <div>
          <h1 class="title">Rate Card</h1>
          <div class="sub">Server-side pricing configuration. Changes apply to new calculations immediately; saved quotes keep their stored totals.</div>
        </div>
        <button class="btn primary" :disabled="saving" @click="save">{{ saving ? "Saving..." : "Save Rate Card" }}</button>
      </div>

      <div v-if="!loaded" class="empty">Loading rate card...</div>
      <template v-else>

      <div class="cols">
        <div class="card">
          <div class="card-t">Material &amp; Labour Rates (NGN)</div>
          <div class="grid2">
            <label class="f">EUROTEC brand rate (₦/kg)<input v-model.number="rates.brandRates.EUROTEC" type="number" min="0" class="inp" /></label>
            <label class="f">CORTIZO brand rate (₦/kg)<input v-model.number="rates.brandRates.CORTIZO" type="number" min="0" class="inp" /></label>
            <label class="f">Default brand rate (₦/kg)<input v-model.number="rates.brandRates.DEFAULT" type="number" min="0" class="inp" /></label>
            <label class="f">Gasket (₦/linear metre)<input v-model.number="rates.gasketRate" type="number" min="0" class="inp" /></label>
            <label class="f">Fabrication (₦/m²)<input v-model.number="rates.fabRate" type="number" min="0" class="inp" /></label>
            <label class="f">Installation (₦/m²)<input v-model.number="rates.installRate" type="number" min="0" class="inp" /></label>
            <label class="f">Sub-frame (₦/linear metre)<input v-model.number="rates.subframeRate" type="number" min="0" class="inp" /></label>
            <label class="f">Sealant (₦/linear metre)<input v-model.number="rates.sealantRate" type="number" min="0" class="inp" /></label>
          </div>
        </div>

        <div class="card">
          <div class="card-t">Commercial Settings</div>
          <div class="grid2">
            <label class="f">Default markup %<input v-model.number="settings.defaultMarkup" type="number" min="0" class="inp" /></label>
            <label class="f">Minimum markup % (floor)<input v-model.number="settings.minMarkup" type="number" min="0" class="inp" /></label>
            <label class="f">VAT %<input v-model.number="settings.vatRate" type="number" step="0.1" min="0" class="inp" /></label>
            <label class="f">Quote validity (days)<input v-model.number="settings.validity" type="number" min="1" class="inp" /></label>
          </div>
          <label class="f" style="margin-top: 10px">Payment terms
            <textarea v-model="settings.paymentTerms" class="inp" rows="3"></textarea>
          </label>
          <label class="f" style="margin-top: 10px">Terms &amp; conditions (printed on quotes)
            <textarea v-model="settings.tcs" class="inp" rows="6"></textarea>
          </label>
        </div>
      </div>

      <div class="card">
        <div class="card-t">Glass Base Prices (₦/m²)</div>
        <div class="grid3">
          <label v-for="r in priceRows" :key="r.key" class="f">
            {{ GLASS_LABELS[r.type] || r.type }} - {{ r.label }}
            <input v-model.number="basePrices[r.key]" type="number" min="0" class="inp" />
          </label>
        </div>
        <div class="hint" style="margin-top: 10px">
          Colour premiums (Clear ₦0, Grey ₦3,500, Low-E ₦8,000, Frosted ₦4,500) are added to the base price; DGU quotes sum the outer and inner premiums.
        </div>
      </div>
      </template>
      </template>
  </div>
</template>

<style scoped>
.wrap { padding: 22px; max-width: 1200px; margin: 0 auto; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.title { font-size: 19px; font-weight: 800; color: #0f172a; letter-spacing: -.4px; margin: 0; }
.sub { font-size: 12px; color: #64748b; margin-top: 4px; max-width: 560px; }
.btn { border-radius: 8px; padding: 9px 16px; font-family: inherit; font-size: 12.5px; font-weight: 700; cursor: pointer; border: 1px solid #e2e8f0; background: #fff; color: #475569; }
.btn.primary { background: linear-gradient(135deg, #f59e0b, #ea580c); border: none; color: #fff; }
.btn.primary:disabled { opacity: .6; cursor: wait; }
.alert { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; border-radius: 9px; padding: 12px 14px; font-size: 12.5px; font-weight: 600; }
.empty { padding: 46px 20px; text-align: center; color: #94a3b8; font-size: 13px; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.card-t { font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .8px; color: #0f172a; margin-bottom: 12px; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 12px; }
.grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px 12px; }
.f { font-size: 10.5px; font-weight: 700; color: #64748b; display: flex; flex-direction: column; gap: 4px; }
.inp { padding: 8px 10px; border: 1px solid #dde4ec; border-radius: 8px; font-family: inherit; font-size: 12.5px; background: #fff; outline: none; width: 100%; box-sizing: border-box; resize: vertical; }
.inp:focus { border-color: #f59e0b; }
.hint { font-size: 10.5px; color: #94a3b8; font-weight: 600; }
@media (max-width: 860px) {
  .cols, .grid3 { grid-template-columns: 1fr; }
  .wrap { padding: 14px; }
}
</style>
