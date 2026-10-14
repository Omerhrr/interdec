<script setup lang="ts">
// Vendors page - CRUD + PDF catalogue upload (also powers Catalogues view-only mode)
const props = defineProps<{ readonly?: boolean; catalogues?: boolean }>();
const { vendors } = useData();
const { CATEGORIES, COUNTRY_FLAGS, fmtSize, fmtDate } = useConstants();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { confirm } = useConfirm();
const { request, saveBlob } = useApi();
const { importflowRole } = useAuth();

// In ImportFlow, reports viewers are read-only; Catalogues passes readonly explicitly
const viewOnly = computed(() => props.readonly || !["admin", "user"].includes(importflowRole.value));
const MAX_MB = 15;

const search = ref("");
const catFilter = ref("All");
const showForm = ref(false);
const editing = ref<any>(null);
const form = ref<any>({});
const { snap, dirty } = useDirty(() => form.value);
const err = ref("");
const saving = ref(false);

// catalog modal
const catalogVendor = ref<any>(null);
const catalogUploading = ref(false);
// pdf viewer
const pdfUrl = ref<string | null>(null);
const pdfName = ref("");

const sortBy = ref("name");
const filtered = computed(() =>
  vendors.value
    .filter((v) => {
      const q = search.value.trim().toLowerCase();
      return (
        (!q || v.name?.toLowerCase().includes(q) || v.contact?.toLowerCase().includes(q) || v.country?.toLowerCase().includes(q)) &&
        (catFilter.value === "All" || v.category === catFilter.value)
      );
    })
    .sort((a, b) => (sortBy.value === "newest" ? (b.created || 0) - (a.created || 0) : a.name.localeCompare(b.name)))
);
const PAGE = 50;
const limit = ref(PAGE);
watch([search, catFilter, sortBy], () => (limit.value = PAGE));
const visible = computed(() => filtered.value.slice(0, limit.value));
const vendorMenu = (v: any) => [
  { label: "Edit vendor", icon: "edit", onClick: () => openEdit(v) },
  { label: "Delete vendor", icon: "trash", danger: true, onClick: () => remove(v) },
];

const openNew = () => {
  editing.value = null;
  form.value = { name: "", contact: "", email: "", phone: "", country: "", category: "", address: "", notes: "" };
  err.value = "";
  showForm.value = true;
  nextTick(snap);
};
const openEdit = (v: any) => {
  editing.value = v;
  const { catalogs, id, created, ...fields } = v;
  form.value = { ...fields };
  err.value = "";
  showForm.value = true;
  nextTick(snap);
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
  if (!(await confirm({ title: `Delete ${v.name}?`, message: `The vendor and its ${v.catalogs?.length || 0} catalogue(s) are deleted. This cannot be undone.`, confirmLabel: "Delete vendor", danger: true }))) return;
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
  const tooBig = files.find((f) => f.size > MAX_MB * 1024 * 1024);
  if (tooBig) {
    notify(`${tooBig.name} is larger than ${MAX_MB} MB`, "error");
    return;
  }
  const notPdf = files.find((f) => f.type !== "application/pdf" && !f.name.toLowerCase().endsWith(".pdf"));
  if (notPdf) {
    notify(`${notPdf.name} is not a PDF`, "error");
    return;
  }
  catalogUploading.value = true;
  try {
    const { fileToBase64 } = useConstants();
    const payload = [];
    for (const f of files) {
      payload.push({ name: f.name, size: f.size, type: f.type || "application/pdf", data: await fileToBase64(f), uploaded: Date.now() });
    }
    await request(`/api/vendors/${catalogVendor.value.id}/catalogs`, { method: "POST", body: payload });
    notify(files.length > 1 ? `${files.length} catalogues uploaded` : "Catalogue uploaded");
    await useData().loadAll();
    catalogVendor.value = vendors.value.find((x) => x.id === catalogVendor.value.id) || catalogVendor.value;
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    catalogUploading.value = false;
  }
};
const deleteCatalog = async (i: number) => {
  if (!(await confirm({ title: "Remove this catalogue?", message: catalogVendor.value?.catalogs?.[i]?.name, confirmLabel: "Remove", danger: true }))) return;
  try {
    await request(`/api/vendors/${catalogVendor.value.id}/catalogs/${i}`, { method: "DELETE" });
    notify("Catalogue removed");
    await useData().loadAll();
    catalogVendor.value = vendors.value.find((x) => x.id === catalogVendor.value.id) || catalogVendor.value;
  } catch (e: any) {
    notify(e.message, "error");
  }
};
const fetchCatalog = (i: number) =>
  request<Blob>(`/api/vendors/${catalogVendor.value.id}/catalogs/${i}/download`, { responseType: "blob" });

// The old <a href> download sent no Authorization header, so it always 401'd
const downloadCatalog = async (i: number) => {
  try {
    const blob = await fetchCatalog(i);
    saveBlob(blob, catalogVendor.value.catalogs?.[i]?.name || "catalog.pdf");
  } catch (e: any) {
    notify(e.message, "error");
  }
};
const closePdf = () => {
  if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value);
  pdfUrl.value = null;
};
const viewCatalog = async (i: number) => {
  try {
    const res = await fetchCatalog(i);
    closePdf();
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
        <h1 class="ph">{{ props.readonly || catalogues ? "Catalogues" : "Vendors" }}</h1>
        <p v-if="viewOnly && catalogues" style="font-size: 12px; color: #64748b; margin-top: 3px">
          Browse &amp; download vendor product catalogues
        </p>
        <p v-else-if="catalogues && !viewOnly" style="font-size: 12px; color: #64748b; margin-top: 3px">
          Admin access: manage vendors, upload and organise PDF catalogues
        </p>
      </div>
      <div class="head-acts">
        <IfExportMenu kind="vendors" :params="{ q: search, category: catFilter }" />
        <button v-if="!viewOnly" class="btn btn-accent" @click="openNew"><UiIcon name="plus" :size="15" /> New Vendor</button>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters">
      <div class="search-wrap">
        <span class="search-ic"><UiIcon name="search" :size="14" /></span>
        <input v-model="search" class="inp" placeholder="Search by name, contact or country" style="padding-left: 32px" aria-label="Search vendors" />
      </div>
      <select v-model="catFilter" class="inp" style="width: auto" aria-label="Category">
        <option value="All">All categories</option>
        <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="sortBy" class="inp" style="width: auto" aria-label="Sort">
        <option value="name">Name A–Z</option>
        <option value="newest">Recently added</option>
      </select>
    </div>
    <div class="count">{{ filtered.length === vendors.length ? `${vendors.length} vendors` : `${filtered.length} of ${vendors.length} vendors` }}</div>

    <!-- Vendor cards -->
    <div class="vendor-list">
      <div v-for="v in visible" :key="v.id" class="vendor-card">
        <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap">
          <div style="min-width: 0">
            <div class="v-top">
              <h2 class="v-name">{{ v.name }}</h2>
              <span class="chip" style="background: #eff6ff; color: #1d4ed8">{{ v.category || "N/A" }}</span>
              <span class="chip" style="background: #f8fafc; color: #475569">
                {{ COUNTRY_FLAGS[v.country] || "🌍" }} {{ v.country || "N/A" }}
              </span>
            </div>
            <div class="v-meta">
              <span v-if="v.contact" class="mi"><UiIcon name="user" :size="13" /> {{ v.contact }}</span>
              <a v-if="v.email" class="mi" :href="`mailto:${v.email}`"><UiIcon name="mail" :size="13" /> {{ v.email }}</a>
              <a v-if="v.phone" class="mi" :href="`tel:${v.phone.replace(/\s/g, '')}`"><UiIcon name="phone" :size="13" /> {{ v.phone }}</a>
              <span v-if="v.address" class="mi"><UiIcon name="pin" :size="13" /> {{ v.address }}</span>
            </div>
            <p v-if="v.notes" class="v-notes">"{{ v.notes }}"</p>
            <div v-if="v.catalogs?.length || !viewOnly" class="v-cats">
              <button v-if="v.catalogs?.length" class="cat-pill" @click="openCatalogs(v)">
                <UiIcon name="folder" :size="13" /> {{ v.catalogs.length }} catalogue{{ v.catalogs.length === 1 ? "" : "s" }}
              </button>
              <button v-else class="cat-add" @click="openCatalogs(v)"><UiIcon name="upload" :size="13" /> Add catalogue</button>
            </div>
          </div>
          <div v-if="!viewOnly" class="v-actions">
            <UiMenu :items="vendorMenu(v)" :label="`Actions for ${v.name}`" />
          </div>
        </div>
      </div>
      <div v-if="!filtered.length" class="empty">No vendors match these filters</div>
      <button v-if="filtered.length > limit" class="btn btn-secondary" style="justify-self: center" @click="limit += PAGE">Show more</button>
    </div>

    <!-- Vendor form modal -->
    <UiAppModal :open="showForm" :dirty="dirty" :title="editing ? 'Edit Vendor' : 'New Vendor'" :width="520" @close="showForm = false">
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
    <UiAppModal :open="!!catalogVendor" :title="`Catalogues: ${catalogVendor?.name || ''}`" :width="480" @close="catalogVendor = null; closePdf()">
      <div style="display: grid; gap: 8px; margin-bottom: 12px">
        <div
          v-for="(c, i) in catalogVendor?.catalogs || []"
          :key="i"
          style="display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px"
        >
          <UiIcon name="file" :size="18" style="color: #dc2626" />
          <div style="flex: 1; min-width: 0">
            <div style="font-size: 11.5px; font-weight: 700; color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ c.name }}</div>
            <div style="font-size: 9.5px; color: #64748b">{{ fmtSize(c.size) }} · {{ fmtDate(c.uploaded) }}</div>
          </div>
          <button class="btn btn-ghost btn-sm" :aria-label="`View ${c.name}`" @click="viewCatalog(i)"><UiIcon name="eye" :size="14" /></button>
          <button class="btn btn-ghost btn-sm" title="Download" :aria-label="`Download ${c.name}`" @click="downloadCatalog(i)"><UiIcon name="download" :size="14" /></button>
          <button v-if="!viewOnly" class="btn btn-danger btn-sm" :aria-label="`Remove ${c.name}`" @click="deleteCatalog(i)"><UiIcon name="trash" :size="14" /></button>
        </div>
        <div v-if="!(catalogVendor?.catalogs?.length)" style="text-align: center; padding: 18px; color: #64748b; font-size: 12px">
          No catalogues uploaded yet
        </div>
      </div>
      <UiUploadBox v-if="!viewOnly" label="Upload PDF catalogues" multiple accept="application/pdf" @files="uploadCatalogs" />
      <div v-if="catalogUploading" style="text-align: center; font-size: 11px; color: #3b82f6; margin-top: 8px; font-weight: 600">Uploading…</div>
    </UiAppModal>

    <!-- PDF viewer -->
    <div v-if="pdfUrl" class="pdf-overlay" @click.self="closePdf">
      <div class="pdf-box">
        <div class="pdf-head">
          <strong style="font-size: 13px">{{ pdfName }}</strong>
          <button class="btn btn-ghost btn-sm" @click="closePdf">✕ Close</button>
        </div>
        <iframe :src="pdfUrl" style="width: 100%; height: calc(100vh - 160px); border: none"></iframe>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; animation: fadeIn .3s; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.ph { font-size: 20px; font-weight: 800; }
.filters { display: flex; gap: 10px; margin-bottom: 16px; }
.search-wrap { flex: 1; min-width: 180px; position: relative; }
.search-ic { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #64748b; display: flex; }
.vendor-list { display: grid; gap: 12px; }
.vendor-card {
  background: #fff; border-radius: 12px; padding: 18px 22px; border: 1px solid #f1f5f9;
  transition: all .15s;
}
.vendor-card:hover { border-color: #c7d2fe; }
.v-top { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; flex-wrap: wrap; }
.v-name { font-size: 15px; font-weight: 700; margin: 0; }
.v-meta { font-size: 12px; color: #64748b; line-height: 1.7; display: flex; flex-wrap: wrap; gap: 2px 14px; }
.v-meta a { color: inherit; text-decoration: none; }
.v-meta a:hover { color: var(--primary); }
.mi { display: inline-flex; align-items: center; gap: 5px; }
.count { font-size: 12px; color: #64748b; margin: -6px 0 12px; }
.cat-add {
  display: inline-flex; align-items: center; gap: 5px; font: inherit; font-size: 11px; font-weight: 700; color: #64748b;
  background: none; border: 1px dashed #cbd5e1; border-radius: 20px; padding: 4px 10px; cursor: pointer;
}
.cat-add:hover { color: var(--primary); border-color: #93c5fd; }
.v-notes { font-size: 11.5px; color: #64748b; font-style: italic; margin-top: 4px; }
.v-cats { margin-top: 8px; display: flex; gap: 6px; }
.cat-pill { display: inline-flex; align-items: center; gap: 5px;
  font-family: inherit; font-size: 10.5px; font-weight: 700; color: #3b82f6;
  background: #eff6ff; border: 1px solid #dbeafe; border-radius: 20px; padding: 4px 10px; cursor: pointer;
}
.cat-pill:hover { background: #dbeafe; }
.v-actions { display: flex; gap: 6px; align-items: flex-start; flex-shrink: 0; }
.empty { text-align: center; padding: 40px; color: #64748b; background: #fff; border-radius: 12px; border: 1px dashed #e2e8f0; }
.pdf-overlay {
  position: fixed; inset: 0; background: rgba(15,23,42,.55); z-index: 1100;
  display: flex; align-items: center; justify-content: center; padding: 30px;
}
.pdf-box { background: #fff; border-radius: 12px; width: 100%; max-width: 900px; overflow: hidden; display: flex; flex-direction: column; }
.pdf-head { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid #f1f5f9; }
/* Mobile: let the filter row wrap so the category select never overflows */
@media (max-width: 640px) {
  .filters { flex-wrap: wrap; }
  .search-wrap { min-width: 100%; }
}
</style>
