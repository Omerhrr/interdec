<script setup lang="ts">
// New shipment. Vendor first (people think "order from X"); the category comes from the vendor.
const props = defineProps<{ presetProjectId?: string | null }>();
const emit = defineEmits<{ (e: "close"): void; (e: "created", id: string): void }>();
const { projects, vendors, loadAll } = useData();
const { COMPANIES, CATEGORIES, CURRENCIES } = useConstants();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();

const form = ref<any>({
  companyId: "", projectId: props.presetProjectId ?? undefined, vendorId: "", category: "",
  description: "", productionDays: null as number | null, value: null as number | null, currency: "USD",
});
const err = ref("");
const { snap, dirty } = useDirty(() => form.value);
onMounted(snap);
const tried = ref(false);
const saving = ref(false);

const activeProjects = computed(() => projects.value.filter((p) => p.status === "Active"));
const sortedVendors = computed(() => [...vendors.value].sort((a, b) => a.name.localeCompare(b.name)));
// picking a vendor fills the category; it can still be changed for one-off orders
watch(() => form.value.vendorId, (id) => {
  const v = vendors.value.find((x) => x.id === id);
  if (v?.category) form.value.category = v.category;
});

const missing = computed(() => {
  const m: string[] = [];
  if (!form.value.companyId) m.push("company");
  if (form.value.projectId === undefined) m.push("project");
  if (!form.value.vendorId) m.push("vendor");
  if (!form.value.category) m.push("category");
  if (!form.value.description?.trim()) m.push("description");
  return m;
});
const bad = (k: string) => tried.value && missing.value.includes(k);

const save = async () => {
  tried.value = true;
  err.value = "";
  if (missing.value.length) {
    err.value = `Still needed: ${missing.value.join(", ")}`;
    return;
  }
  if (form.value.value != null && Number(form.value.value) < 0) {
    err.value = "Value cannot be negative";
    return;
  }
  saving.value = true;
  try {
    const created = await request<any>("/api/shipments", {
      method: "POST",
      body: {
        companyId: form.value.companyId,
        projectId: form.value.projectId || null,
        category: form.value.category,
        vendorId: form.value.vendorId,
        description: form.value.description,
        productionDays: Number(form.value.productionDays) > 0 ? `${Math.round(Number(form.value.productionDays))} days` : "",
        value: Number(form.value.value) || 0,
        currency: form.value.currency || "USD",
      },
    });
    await loadAll();
    notify(`Shipment ${created.ref} created`);
    emit("created", created.id);
    emit("close");
  } catch (e: any) {
    err.value = e.message;
  } finally {
    saving.value = false;
  }
};
</script>

<template>
  <UiAppModal open title="New shipment" :width="460" :dirty="dirty && !saving" @close="emit('close')">
    <form class="f" novalidate @submit.prevent="save">
      <fieldset>
        <legend class="lbl" :class="{ bad: bad('company') }">Company</legend>
        <div class="cos">
          <button
            v-for="c in COMPANIES" :key="c.id" type="button" class="co-btn" :aria-pressed="form.companyId === c.id"
            :style="form.companyId === c.id ? { borderColor: c.color, background: c.color + '10' } : {}"
            @click="form.companyId = c.id"
          >
            <img :src="c.logo" alt="" style="height: 26px; object-fit: contain" />
            <span :style="{ color: form.companyId === c.id ? c.text : '#334155' }">{{ c.name }}</span>
          </button>
        </div>
      </fieldset>

      <label>
        <span class="lbl" :class="{ bad: bad('project') }">Project</span>
        <select v-model="form.projectId" class="inp">
          <option :value="undefined" disabled>Select project…</option>
          <option :value="null">General stock (no project)</option>
          <option v-for="p in activeProjects" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </label>

      <div class="g2">
        <label>
          <span class="lbl" :class="{ bad: bad('vendor') }">Vendor</span>
          <select v-model="form.vendorId" class="inp">
            <option value="" disabled>Select vendor…</option>
            <option v-for="v in sortedVendors" :key="v.id" :value="v.id">{{ v.name }}</option>
          </select>
        </label>
        <label>
          <span class="lbl" :class="{ bad: bad('category') }">Category</span>
          <select v-model="form.category" class="inp">
            <option value="" disabled>Select…</option>
            <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
      </div>

      <label>
        <span class="lbl" :class="{ bad: bad('description') }">Description</span>
        <input v-model="form.description" class="inp" placeholder="e.g. Glass panels, batch 1" />
      </label>

      <div class="g3">
        <label>
          <span class="lbl">Production time</span>
          <span class="suffix">
            <input v-model.number="form.productionDays" class="inp num" type="number" min="1" step="1" placeholder="30" />
            <span>days</span>
          </span>
        </label>
        <label>
          <span class="lbl">Value</span>
          <input v-model.number="form.value" class="inp num" type="number" min="0" placeholder="25,000" />
        </label>
        <label>
          <span class="lbl">Currency</span>
          <select v-model="form.currency" class="inp">
            <option v-for="c in CURRENCIES" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
      </div>
      <p class="hint">All fields except production time and value are required.</p>

      <div v-if="err" class="err" role="alert">{{ err }}</div>

      <div class="actions">
        <button type="button" class="btn btn-secondary" @click="emit('close')">Cancel</button>
        <button class="btn btn-accent" :disabled="saving">{{ saving ? "Creating…" : "Create shipment" }}</button>
      </div>
    </form>
  </UiAppModal>
</template>

<style scoped>
.f { display: grid; gap: 14px; }
fieldset { border: none; padding: 0; }
label { display: block; }
.lbl.bad { color: #dc2626; }
.cos { display: flex; gap: 8px; }
.co-btn {
  flex: 1; padding: 12px 8px; border-radius: 9px; cursor: pointer; font: inherit; border: 2px solid #e2e8f0; background: #fff;
  display: flex; flex-direction: column; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 700; transition: all .15s;
}
.g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.g3 { display: grid; grid-template-columns: 1.1fr 1fr .8fr; gap: 10px; }
.suffix { position: relative; display: block; }
.suffix span { position: absolute; right: 11px; top: 50%; transform: translateY(-50%); font-size: 12px; color: #64748b; pointer-events: none; }
.suffix .inp { padding-right: 46px; }
.hint { font-size: 11.5px; color: #64748b; margin-top: -6px; }
.err { padding: 8px 12px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 7px; font-size: 12.5px; color: #b91c1c; font-weight: 600; }
.actions { display: flex; gap: 8px; justify-content: flex-end; }
@media (max-width: 520px) { .g2, .g3 { grid-template-columns: 1fr; } }
</style>
