<script setup lang="ts">
// New Shipment modal - mirrors the original creation form
const emit = defineEmits<{ (e: "close"): void; (e: "created", id: string): void }>();
const { projects, vendors } = useData();
const { COMPANIES, CATEGORIES, CURRENCIES } = useConstants();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();

const form = ref<any>({
  companyId: "", projectId: undefined, category: "", vendorId: "",
  description: "", productionDays: "", value: "", currency: "USD", _err: "",
});
const saving = ref(false);

const activeProjects = computed(() => projects.value.filter((p) => p.status === "Active"));
const catVendors = computed(() => vendors.value.filter((v) => v.category === form.value.category));

const save = async () => {
  const missing: string[] = [];
  if (!form.value.companyId) missing.push("Company");
  if (form.value.projectId === undefined) missing.push("Project");
  if (!form.value.category) missing.push("Category");
  if (!form.value.vendorId) missing.push("Vendor");
  if (!form.value.description?.trim()) missing.push("Description");
  if (missing.length) {
    form.value._err = `Required: ${missing.join(", ")}`;
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
        productionDays: form.value.productionDays || "",
        value: Number(form.value.value) || 0,
        currency: form.value.currency || "USD",
      },
    });
    notify("Shipment created");
    emit("close");
    emit("created", created.id);
  } catch (e: any) {
    form.value._err = e.message;
  } finally {
    saving.value = false;
  }
};
</script>

<template>
  <UiAppModal open title="New Shipment" :width="440" @close="emit('close')">
    <p style="font-size: 12px; color: #94a3b8; margin: -8px 0 14px">
      Create a new importation cycle. Select the company, project (or General Stock), and vendor.
    </p>
    <div style="display: grid; gap: 12px">
      <!-- Company -->
      <div>
        <label class="lbl" :style="form._err && !form.companyId ? { color: '#ef4444' } : {}">Company *</label>
        <div style="display: flex; gap: 8px">
          <button
            v-for="c in COMPANIES" :key="c.id" type="button"
            class="co-btn"
            :style="{
              border: `2px solid ${form.companyId === c.id ? c.color : '#e2e8f0'}`,
              background: form.companyId === c.id ? c.color + '0c' : '#fff',
              color: form.companyId === c.id ? c.color : '#475569',
            }"
            @click="form.companyId = c.id; form._err = ''"
          >
            <img :src="c.logo" :alt="c.name" style="height: 24px; object-fit: contain" />
            <span>{{ c.name }}</span>
          </button>
        </div>
      </div>

      <!-- Project -->
      <div>
        <label class="lbl" :style="form._err && form.projectId === undefined ? { color: '#ef4444' } : {}">Project *</label>
        <div style="display: grid; grid-template-columns: 1fr auto; gap: 8px">
          <select v-model="form.projectId" class="inp" @change="form._err = ''">
            <option :value="undefined" disabled>Select project...</option>
            <option :value="null">📦 General Stock</option>
            <option v-for="p in activeProjects" :key="p.id" :value="p.id">📋 {{ p.name }}</option>
          </select>
        </div>
      </div>

      <!-- Category -->
      <div>
        <label class="lbl" :style="form._err && !form.category ? { color: '#ef4444' } : {}">Category *</label>
        <select v-model="form.category" class="inp" @change="form.vendorId = ''; form._err = ''">
          <option value="" disabled>Select category...</option>
          <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>

      <!-- Vendor -->
      <div>
        <label class="lbl" :style="form._err && !form.vendorId ? { color: '#ef4444' } : {}">Vendor *</label>
        <select v-model="form.vendorId" class="inp" :disabled="!form.category"
          :style="!form.category ? { background: '#f8fafc', color: '#94a3b8' } : {}" @change="form._err = ''">
          <option value="" disabled>{{ form.category ? "Select vendor..." : "Select a category first..." }}</option>
          <option v-for="v in catVendors" :key="v.id" :value="v.id">{{ v.name }}</option>
        </select>
      </div>

      <!-- Description -->
      <div>
        <label class="lbl" :style="form._err && !form.description?.trim() ? { color: '#ef4444' } : {}">Description *</label>
        <input v-model="form.description" class="inp" placeholder="Glass Panels, Batch 1" @input="form._err = ''" />
      </div>

      <!-- Production time -->
      <div>
        <label class="lbl">Production Time (days)</label>
        <input v-model="form.productionDays" class="inp" placeholder="e.g. 30 days" />
      </div>

      <!-- Value + Currency -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px">
        <div>
          <label class="lbl">Shipment Value</label>
          <input v-model="form.value" class="inp mono" type="number" placeholder="25000" />
        </div>
        <div>
          <label class="lbl">Currency</label>
          <select v-model="form.currency" class="inp">
            <option v-for="c in CURRENCIES" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
      </div>
    </div>

    <div v-if="form._err" class="err">{{ form._err }}</div>

    <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px">
      <button class="btn btn-secondary" @click="emit('close')">Cancel</button>
      <button class="btn btn-accent" :disabled="saving" @click="save">{{ saving ? "Creating…" : "Create Shipment" }}</button>
    </div>
  </UiAppModal>
</template>

<style scoped>
.co-btn {
  flex: 1; padding: 12px 10px; border-radius: 9px; cursor: pointer; font-family: inherit;
  text-align: center; transition: all .15s; display: flex; flex-direction: column;
  align-items: center; gap: 4px; font-size: 12px; font-weight: 700;
}
.err {
  margin-top: 10px; padding: 8px 12px; background: #fef2f2; border: 1px solid #fecaca;
  border-radius: 7px; font-size: 12px; color: #dc2626; font-weight: 600;
}
</style>
