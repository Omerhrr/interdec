<script setup lang="ts">
// Vendors page - CRUD + PDF catalogue upload (also powers Catalogues view-only mode)
const props = defineProps<{ readonly?: boolean; catalogues?: boolean }>();
const { vendors } = useData();
const { CATEGORIES, COUNTRY_FLAGS, fmtSize, fmtDate } = useConstants();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();

const search = ref("");
const catFilter = ref("All");
const showForm = ref(false);
const editing = ref<any>(null);
const form = ref<any>({});
const err = ref("");
const saving = ref(false);

// catalog modal
const catalogVendor = ref<any>(null);
const catalogUploading = ref(false);
// pdf viewer
const pdfUrl = ref<string | null>(null);
const pdfName = ref("");

const filtered = computed(() =>
  vendors.value.filter((v) => {
    const q = search.value.toLowerCase();
    return (
      (!q || v.name?.toLowerCase().includes(q) || v.contact?.toLowerCase().includes(q) || v.country?.toLowerCase().includes(q)) &&
      (catFilter.value === "All" || v.category === catFilter.value)
    );
  })
);

const openNew = () => {
  editing.value = null;
  form.value = { name: "", contact: "", email: "", phone: "", country: "", category: "", address: "", notes: "" };
  err.value = "";
  showForm.value = true;
};
const openEdit = (v: any) => {
  editing.value = v;
  form.value = { ...v };
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
      await request(`/api/vendors/${editing.value.id}`, { method: "PUT", body: form.value });
      notify("Vendor updated");
    } else {
      await request("/api/vendors", { method: "POST", body: form.value });
      notify("Vendor added");
    }
    showForm.value = false;
    await useData().loadAll();
  } catch (e: any) {
    err.value = e.message;
  } finally {
    saving.value = false;
  }
};

const remove = async (v: any) => {
  if (!confirm(`Delete vendor "${v.name}"? This cannot be undone.`)) return;
  try {
    await request(`/api/vendors/${v.id}`, { method: "DELETE" });
    notify("Deleted");
    await useData().loadAll();
  } catch (e: any) {
    notify(e.message, "error");
  }
};

// ---- Catalogues ----
const openCatalogs = (v: any) => {
  catalogVendor.value = v;
};
const uploadCatalogs = async (files: File[]) => {
  catalogUploading.value = true;
  try {
    const { fileToBase64 } = useConstants();
    const payload = [];
    for (const f of files) {
      payload.push({ name: f.name, size: f.size, type: f.type, data: await fileToBase64(f), uploaded: Date.now() });
    }
    await request(`/api/vendors/${catalogVendor.value.id}/catalogs`, { method: "POST", body: payload });
    notify("Catalog uploaded");
    await useData().loadAll();
    catalogVendor.value = vendors.value.find((x) => x.id === catalogVendor.value.id) || catalogVendor.value;
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    catalogUploading.value = false;
  }
};
const deleteCatalog = async (i: number) => {
  if (!confirm("Remove this catalog?")) return;
  await request(`/api/vendors/${catalogVendor.value.id}/catalogs/${i}`, { method: "DELETE" });
  notify("Removed");
  await useData().loadAll();
  catalogVendor.value = vendors.value.find((x) => x.id === catalogVendor.value.id) || catalogVendor.value;
};
const viewCatalog = async (i: number) => {
  try {
    const res = await request<Blob>(`/api/vendors/${catalogVendor.value.id}/catalogs/${i}/download`, { responseType: "blob" });
    pdfUrl.value = URL.createObjectURL(res);
    pdfName.value = catalogVendor.value.catalogs?.[i]?.name || "catalog.pdf";
  } catch (e: any) {
    notify(e.message, "error");
  }
};
</script>

<template>
  <div class="page">
    <!-- Header -->
    <div class="head">
      <div>
        <h2>{{ readonly || catalogues ? "Catalogues" : "Vendors" }}</h2>
        <p v-if="readonly" style="font-size: 12px; color: #94a3b8; margin-top: 3px">
          Browse &amp; download vendor product catalogues
        </p>
        <p v-else-if="catalogues" style="font-size: 12px; color: #94a3b8; margin-top: 3px">
          Admin access: manage vendors, upload and organise PDF catalogues
        </p>
      </div>
      <button v-if="!readonly" class="btn btn-accent" @click="openNew">＋ New Vendor</button>
    </div>

    <!-- Filters -->
    <div class="filters">
      <div class="search-wrap">
        <span class="search-ic">🔍</span>
        <input v-model="search" class="inp" placeholder="Search vendors..." style="padding-left: 30px" />
      </div>
      <select v-model="catFilter" class="inp" style="width: auto">
        <option value="All">All Categories</option>
        <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
      </select>
    </div>

    <!-- Vendor cards -->
    <div class="vendor-list">
      <div v-for="v in filtered" :key="v.id" class="vendor-card">
        <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap">
          <div style="min-width: 0">
            <div class="v-top">
              <h3 class="v-name">{{ v.name }}</h3>
              <span class="chip" style="background: #eff6ff; color: #1d4ed8">{{ v.category || "N/A" }}</span>
              <span class="chip" style="background: #f8fafc; color: #475569">
                {{ COUNTRY_FLAGS[v.country] || "🌍" }} {{ v.country || "N/A" }}
              </span>
            </div>
            <div class="v-meta">👤 {{ v.contact || "N/A" }} · ✉️ {{ v.email || "N/A" }}</div>
            <div class="v-meta">📞 {{ v.phone || "N/A" }}<template v-if="v.address"> · 📍 {{ v.address }}</template></div>
            <p v-if="v.notes" class="v-notes">"{{ v.notes }}"</p>
            <div class="v-cats">
              <button class="cat-pill" @click="openCatalogs(v)">
                📂 {{ v.catalogs?.length || 0 }} Catalog{{ (v.catalogs?.length || 0) === 1 ? "" : "s" }}
              </button>
            </div>
          </div>
          <div v-if="!readonly" class="v-actions">
            <button class="btn btn-secondary btn-sm" @click="openEdit(v)">✏️ Edit</button>
            <button class="btn btn-danger btn-sm" @click="remove(v)">Delete</button>
          </div>
        </div>
      </div>
      <div v-if="!filtered.length" class="empty">No vendors found</div>
    </div>

    <!-- Vendor form modal -->
    <UiAppModal :open="showForm" :title="editing ? 'Edit Vendor' : 'New Vendor'" :width="520" @close="showForm = false">
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
        <div style="grid-column: span 2">
          <label class="lbl">Company Name *</label>
          <input v-model="form.name" class="inp" placeholder="Acme Industries Ltd" />
        </div>
        <div><label class="lbl">Contact</label><input v-model="form.contact" class="inp" placeholder="John Smith" /></div>
        <div><label class="lbl">Email</label><input v-model="form.email" class="inp" type="email" placeholder="john@acme.com" /></div>
        <div><label class="lbl">Phone</label><input v-model="form.phone" class="inp" placeholder="+1 555" /></div>
        <div><label class="lbl">Country</label><input v-model="form.country" class="inp" placeholder="China" /></div>
        <div>
          <label class="lbl">Category</label>
          <select v-model="form.category" class="inp">
            <option value="" disabled>Select category...</option>
            <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div><label class="lbl">Address</label><input v-model="form.address" class="inp" /></div>
        <div style="grid-column: span 2">
          <label class="lbl">Notes</label>
          <textarea v-model="form.notes" class="inp" rows="2" style="resize: vertical"></textarea>
        </div>
      </div>
      <div v-if="err" style="margin-top: 10px; padding: 8px 12px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 7px; font-size: 12px; color: #dc2626; font-weight: 600">{{ err }}</div>
      <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px">
        <button class="btn btn-secondary" @click="showForm = false">Cancel</button>
        <button class="btn btn-accent" :disabled="saving" @click="save">{{ saving ? "Saving…" : editing ? "Save Changes" : "Add Vendor" }}</button>
      </div>
    </UiAppModal>

    <!-- Catalogs modal -->
    <UiAppModal :open="!!catalogVendor" :title="`Catalogues: ${catalogVendor?.name || ''}`" :width="480" @close="catalogVendor = null; pdfUrl = null">
      <div style="display: grid; gap: 8px; margin-bottom: 12px">
        <div
          v-for="(c, i) in catalogVendor?.catalogs || []"
          :key="i"
          style="display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px"
        >
          <span style="font-size: 16px">📕</span>
          <div style="flex: 1; min-width: 0">
            <div style="font-size: 11.5px; font-weight: 700; color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ c.name }}</div>
            <div style="font-size: 9.5px; color: #94a3b8">{{ fmtSize(c.size) }} · {{ fmtDate(c.uploaded) }}</div>
          </div>
          <button class="btn btn-ghost btn-sm" style="font-size: 10px" @click="viewCatalog(i)">View</button>
          <a
            class="btn btn-ghost btn-sm"
            style="font-size: 10px; text-decoration: none"
            :href="`/api/vendors/${catalogVendor.id}/catalogs/${i}/download`"
            target="_blank"
          >↓</a>
          <button v-if="!readonly" class="btn btn-danger btn-sm" style="font-size: 10px" @click="deleteCatalog(i)">✕</button>
        </div>
        <div v-if="!(catalogVendor?.catalogs?.length)" style="text-align: center; padding: 18px; color: #94a3b8; font-size: 12px">
          No catalogs uploaded yet
        </div>
      </div>
      <UiUploadBox v-if="!readonly" label="Upload PDF Catalog" accept="application/pdf" @files="uploadCatalogs" />
      <div v-if="catalogUploading" style="text-align: center; font-size: 11px; color: #3b82f6; margin-top: 8px; font-weight: 600">Uploading…</div>
    </UiAppModal>

    <!-- PDF viewer -->
    <div v-if="pdfUrl" class="pdf-overlay" @click.self="pdfUrl = null">
      <div class="pdf-box">
        <div class="pdf-head">
          <strong style="font-size: 13px">{{ pdfName }}</strong>
          <button class="btn btn-ghost btn-sm" @click="pdfUrl = null">✕ Close</button>
        </div>
        <iframe :src="pdfUrl" style="width: 100%; height: calc(100vh - 160px); border: none"></iframe>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; animation: fadeIn .3s; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
h2 { font-size: 20px; font-weight: 800; }
.filters { display: flex; gap: 10px; margin-bottom: 16px; }
.search-wrap { flex: 1; min-width: 180px; position: relative; }
.search-ic { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 12px; opacity: .55; }
.vendor-list { display: grid; gap: 12px; }
.vendor-card {
  background: #fff; border-radius: 12px; padding: 18px 22px; border: 1px solid #f1f5f9;
  transition: all .15s;
}
.vendor-card:hover { border-color: #c7d2fe; }
.v-top { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; flex-wrap: wrap; }
.v-name { font-size: 15px; font-weight: 700; margin: 0; }
.v-meta { font-size: 12px; color: #64748b; line-height: 1.7; }
.v-notes { font-size: 11.5px; color: #94a3b8; font-style: italic; margin-top: 4px; }
.v-cats { margin-top: 8px; display: flex; gap: 6px; }
.cat-pill {
  font-family: inherit; font-size: 10.5px; font-weight: 700; color: #3b82f6;
  background: #eff6ff; border: 1px solid #dbeafe; border-radius: 20px; padding: 4px 10px; cursor: pointer;
}
.cat-pill:hover { background: #dbeafe; }
.v-actions { display: flex; gap: 6px; align-items: flex-start; flex-shrink: 0; }
.empty { text-align: center; padding: 40px; color: #94a3b8; background: #fff; border-radius: 12px; border: 1px dashed #e2e8f0; }
.pdf-overlay {
  position: fixed; inset: 0; background: rgba(15,23,42,.55); z-index: 1100;
  display: flex; align-items: center; justify-content: center; padding: 30px;
}
.pdf-box { background: #fff; border-radius: 12px; width: 100%; max-width: 900px; overflow: hidden; display: flex; flex-direction: column; }
.pdf-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid #f1f5f9; }
</style>
