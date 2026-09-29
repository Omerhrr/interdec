<script setup lang="ts">
// Shippers page — CRUD (mirrors vendors structure, w/o catalogs)
const { shippers } = useData();
const { COUNTRY_FLAGS, fmtDate } = useConstants();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();

const SHIPPER_TYPES = ["Ocean Freight", "Air Freight", "Multimodal", "Land Transport", "Courier", "Other"];

const search = ref("");
const showForm = ref(false);
const editing = ref<any>(null);
const form = ref<any>({});
const err = ref("");
const saving = ref(false);

const filtered = computed(() =>
  shippers.value.filter((s) => {
    const q = search.value.toLowerCase();
    return !q || s.name?.toLowerCase().includes(q) || s.contact?.toLowerCase().includes(q) || s.country?.toLowerCase().includes(q);
  })
);

const openNew = () => {
  editing.value = null;
  form.value = { name: "", contact: "", email: "", phone: "", country: "", category: "", notes: "" };
  err.value = "";
  showForm.value = true;
};
const openEdit = (s: any) => {
  editing.value = s;
  form.value = { ...s };
  err.value = "";
  showForm.value = true;
};

const save = async () => {
  if (!form.value.name?.trim()) {
    err.value = "Company name is required";
    return;
  }
  saving.value = true;
  try {
    if (editing.value) {
      await request(`/api/shippers/${editing.value.id}`, { method: "PUT", body: form.value });
      notify("Shipper updated");
    } else {
      await request("/api/shippers", { method: "POST", body: form.value });
      notify("Shipper added");
    }
    showForm.value = false;
    await useData().loadAll();
  } catch (e: any) {
    err.value = e.message;
  } finally {
    saving.value = false;
  }
};

const remove = async (s: any) => {
  if (!confirm(`Delete shipper "${s.name}"? This cannot be undone.`)) return;
  try {
    await request(`/api/shippers/${s.id}`, { method: "DELETE" });
    notify("Deleted");
    await useData().loadAll();
  } catch (e: any) {
    notify(e.message, "error");
  }
};
</script>

<template>
  <div class="page">
    <div class="head">
      <div>
        <h2>Shippers</h2>
        <p style="font-size: 12px; color: #94a3b8; margin-top: 3px">Freight forwarders &amp; carriers</p>
      </div>
      <button class="btn btn-accent" @click="openNew">＋ New Shipper</button>
    </div>

    <div class="filters">
      <div class="search-wrap">
        <span class="search-ic">🔍</span>
        <input v-model="search" class="inp" placeholder="Search shippers..." style="padding-left: 30px" />
      </div>
    </div>

    <div class="list">
      <div v-for="s in filtered" :key="s.id" class="ship-card">
        <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap">
          <div style="min-width: 0">
            <div class="s-top">
              <h3 class="s-name">{{ s.name }}</h3>
              <span class="chip" style="background: #f0f9ff; color: #0369a1">{{ s.category || "—" }}</span>
              <span class="chip" style="background: #f8fafc; color: #475569">{{ COUNTRY_FLAGS[s.country] || "🌍" }} {{ s.country || "—" }}</span>
            </div>
            <div class="s-meta">👤 {{ s.contact || "—" }} · ✉️ {{ s.email || "—" }} · 📞 {{ s.phone || "—" }}</div>
            <p v-if="s.notes" class="s-notes">"{{ s.notes }}"</p>
            <div style="font-size: 10px; color: #cbd5e1; margin-top: 6px">Added {{ fmtDate(s.created) }}</div>
          </div>
          <div class="s-actions">
            <button class="btn btn-secondary btn-sm" @click="openEdit(s)">✏️ Edit</button>
            <button class="btn btn-danger btn-sm" @click="remove(s)">Delete</button>
          </div>
        </div>
      </div>
      <div v-if="!filtered.length" class="empty">No shippers found</div>
    </div>

    <UiAppModal :open="showForm" :title="editing ? 'Edit Shipper' : 'New Shipper'" :width="520" @close="showForm = false">
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
        <div style="grid-column: span 2">
          <label class="lbl">Company Name *</label>
          <input v-model="form.name" class="inp" placeholder="Global Freight Logistics" />
        </div>
        <div><label class="lbl">Contact</label><input v-model="form.contact" class="inp" placeholder="Ahmed Hassan" /></div>
        <div><label class="lbl">Email</label><input v-model="form.email" class="inp" type="email" /></div>
        <div><label class="lbl">Phone</label><input v-model="form.phone" class="inp" placeholder="+971 4" /></div>
        <div><label class="lbl">Country</label><input v-model="form.country" class="inp" placeholder="UAE" /></div>
        <div style="grid-column: span 2">
          <label class="lbl">Type</label>
          <select v-model="form.category" class="inp">
            <option value="" disabled>Select type...</option>
            <option v-for="t in SHIPPER_TYPES" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div style="grid-column: span 2">
          <label class="lbl">Notes</label>
          <textarea v-model="form.notes" class="inp" rows="2" style="resize: vertical"></textarea>
        </div>
      </div>
      <div v-if="err" style="margin-top: 10px; padding: 8px 12px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 7px; font-size: 12px; color: #dc2626; font-weight: 600">{{ err }}</div>
      <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px">
        <button class="btn btn-secondary" @click="showForm = false">Cancel</button>
        <button class="btn btn-accent" :disabled="saving" @click="save">{{ saving ? "Saving…" : editing ? "Save Changes" : "Add Shipper" }}</button>
      </div>
    </UiAppModal>
  </div>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; animation: fadeIn .3s; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
h2 { font-size: 20px; font-weight: 800; }
.filters { display: flex; gap: 10px; margin-bottom: 16px; }
.search-wrap { flex: 1; min-width: 180px; position: relative; }
.search-ic { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 12px; opacity: .55; }
.list { display: grid; gap: 12px; }
.ship-card { background: #fff; border-radius: 12px; padding: 18px 22px; border: 1px solid #f1f5f9; transition: all .15s; }
.ship-card:hover { border-color: #a5f3fc; }
.s-top { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; flex-wrap: wrap; }
.s-name { font-size: 15px; font-weight: 700; margin: 0; }
.s-meta { font-size: 12px; color: #64748b; line-height: 1.7; }
.s-notes { font-size: 11.5px; color: #94a3b8; font-style: italic; margin-top: 4px; }
.s-actions { display: flex; gap: 6px; align-items: flex-start; flex-shrink: 0; }
.empty { text-align: center; padding: 40px; color: #94a3b8; background: #fff; border-radius: 12px; border: 1px dashed #e2e8f0; }
</style>
