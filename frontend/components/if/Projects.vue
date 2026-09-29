<script setup lang="ts">
// Projects page - list w/ filters, detail w/ shipments, CRUD
const props = defineProps<{ detail?: string | null; detailId?: string | null }>();
const emit = defineEmits<{ (e: "navigate", p: string, d?: string | null, id?: string | null): void }>();
const { projects, shipments, company } = useData();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();
const { fmtDate } = useConstants();

const search = ref("");
const statusFilter = ref("All");
const showForm = ref(false);
const editing = ref<any>(null);
const form = ref<any>({});
const err = ref("");
const saving = ref(false);

const role = computed(() => useAuth().user.value?.apps?.importflow?.role || "viewer");
const canEdit = computed(() => role.value === "admin" || role.value === "user");

const toUsd = (s: any) => (s.value || 0) * (DEFAULT_RATES[s.currency] || 1);
const fmtUsd = (n: number) => "$ " + Math.round(n).toLocaleString();

const filtered = computed(() =>
  projects.value.filter((p) => {
    const q = search.value.toLowerCase();
    return (
      (!q || p.name?.toLowerCase().includes(q) || p.client?.toLowerCase().includes(q)) &&
      (statusFilter.value === "All" || p.status === statusFilter.value)
    );
  })
);

const openNew = () => {
  editing.value = null;
  form.value = { name: "", client: "", description: "", status: "Active" };
  err.value = "";
  showForm.value = true;
};
const openEdit = (p: any) => {
  editing.value = p;
  form.value = { ...p };
  err.value = "";
  showForm.value = true;
};
const save = async () => {
  if (!form.value.name?.trim()) {
    err.value = "Project name is required";
    return;
  }
  saving.value = true;
  try {
    if (editing.value) {
      await request(`/api/projects/${editing.value.id}`, { method: "PUT", body: form.value });
      notify("Project updated");
    } else {
      await request("/api/projects", { method: "POST", body: form.value });
      notify("Project created");
    }
    showForm.value = false;
    await useData().loadAll();
  } catch (e: any) {
    err.value = e.message;
  } finally {
    saving.value = false;
  }
};
const remove = async (p: any) => {
  if (!confirm(`Delete project "${p.name}"? Shipments will be detached.`)) return;
  try {
    await request(`/api/projects/${p.id}`, { method: "DELETE" });
    notify("Deleted");
    await useData().loadAll();
    emit("navigate", "projects", null, null);
  } catch (e: any) {
    notify(e.message, "error");
  }
};

const statusColor = (s: string) => (s === "Active" ? "#10b981" : s === "Completed" ? "#6366f1" : "#f59e0b");
const detailProject = computed(() => projects.value.find((p) => p.id === props.detailId));
const detailShipments = computed(() =>
  detailProject.value ? shipments.value.filter((s) => s.projectId === detailProject.value!.id) : []
);
</script>

<template>
  <!-- DETAIL -->
  <div v-if="detail === 'detail' && detailProject" class="page">
    <button class="back-link" @click="emit('navigate', 'projects', null, null)">← Projects</button>

    <div class="card" style="margin-bottom: 14px">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap">
        <div>
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap">
            <h2 style="font-size: 17px; font-weight: 800">{{ detailProject.name }}</h2>
            <span class="chip" :style="{ background: statusColor(detailProject.status) + '18', color: statusColor(detailProject.status) }">{{ detailProject.status }}</span>
          </div>
          <div style="font-size: 12.5px; color: #64748b">Client: <strong>{{ detailProject.client || "N/A" }}</strong></div>
          <p v-if="detailProject.description" style="font-size: 12.5px; color: #94a3b8; margin-top: 4px; max-width: 560px">{{ detailProject.description }}</p>
          <div style="font-size: 10.5px; color: #cbd5e1; margin-top: 6px">Created {{ fmtDate(detailProject.created) }}</div>
        </div>
        <div v-if="canEdit" style="display: flex; gap: 6px; flex-shrink: 0">
          <button class="btn btn-secondary btn-sm" @click="openEdit(detailProject)">✏️ Edit</button>
          <button class="btn btn-danger btn-sm" @click="remove(detailProject)">Delete</button>
        </div>
      </div>
    </div>

    <div class="head" style="margin-bottom: 12px">
      <h3 style="font-size: 14px; font-weight: 700; color: #475569">Shipments ({{ detailShipments.length }})</h3>
      <button v-if="canEdit" class="btn btn-accent btn-sm" @click="emit('navigate', 'shipments', null, null)">＋ New Shipment</button>
    </div>

    <div class="sh-list">
      <div
        v-for="s in detailShipments" :key="s.id"
        class="sh-row"
        @click="emit('navigate', 'shipments', 'detail', s.id)"
      >
        <div style="min-width: 0">
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 3px">
            <span class="mono" style="font-size: 11.5px; font-weight: 700; color: #3b82f6">{{ s.ref }}</span>
            <UiCompanyChip :id="s.companyId" />
          </div>
          <div style="font-size: 13px; font-weight: 600">{{ s.description }}</div>
        </div>
        <div style="text-align: right; flex-shrink: 0">
          <UiStatusChip :status="s.status" />
          <div class="mono" style="font-size: 12.5px; font-weight: 700; margin-top: 4px">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</div>
        </div>
      </div>
      <div v-if="!detailShipments.length" class="empty">No shipments under this project yet</div>
    </div>

    <UiAppModal :open="showForm" :title="editing ? 'Edit Project' : 'New Project'" :width="480" @close="showForm = false">
      <div style="display: grid; gap: 12px">
        <div><label class="lbl">Project Name *</label><input v-model="form.name" class="inp" placeholder="Azrieli Tower Phase 2" /></div>
        <div><label class="lbl">Client</label><input v-model="form.client" class="inp" placeholder="Client company name" /></div>
        <div>
          <label class="lbl">Status</label>
          <select v-model="form.status" class="inp">
            <option>Active</option><option>Completed</option><option>On Hold</option>
          </select>
        </div>
        <div><label class="lbl">Description</label><textarea v-model="form.description" class="inp" rows="3" style="resize: vertical" placeholder="Project details..."></textarea></div>
      </div>
      <div v-if="err" style="margin-top: 10px; padding: 8px 12px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 7px; font-size: 12px; color: #dc2626; font-weight: 600">{{ err }}</div>
      <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px">
        <button class="btn btn-secondary" @click="showForm = false">Cancel</button>
        <button class="btn btn-accent" :disabled="saving" @click="save">{{ saving ? "Saving…" : editing ? "Save Changes" : "Create Project" }}</button>
      </div>
    </UiAppModal>
  </div>

  <!-- LIST -->
  <div v-else class="page">
    <div class="head">
      <h2>Projects</h2>
      <button v-if="canEdit" class="btn btn-accent" @click="openNew">＋ New Project</button>
    </div>

    <div class="filters">
      <div class="search-wrap">
        <span class="search-ic">🔍</span>
        <input v-model="search" class="inp" placeholder="Search projects..." style="padding-left: 30px" />
      </div>
      <select v-model="statusFilter" class="inp" style="width: auto">
        <option value="All">All Statuses</option>
        <option>Active</option><option>Completed</option><option>On Hold</option>
      </select>
    </div>

    <div class="p-list">
      <div v-for="p in filtered" :key="p.id" class="p-card" @click="emit('navigate', 'projects', 'detail', p.id)">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px">
          <div style="min-width: 0">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap">
              <h3 style="font-size: 15px; font-weight: 700; margin: 0">{{ p.name }}</h3>
              <span class="chip" :style="{ background: statusColor(p.status) + '18', color: statusColor(p.status) }">{{ p.status }}</span>
            </div>
            <div style="font-size: 12.5px; color: #64748b">Client: <strong>{{ p.client || "N/A" }}</strong></div>
            <p v-if="p.description" style="font-size: 12px; color: #94a3b8; margin-top: 3px">{{ p.description }}</p>
            <div style="display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap">
              <span
                v-for="cid in [...new Set(shipments.filter((s) => s.projectId === p.id).map((s) => s.companyId))]"
                :key="cid"
              ><UiCompanyChip :id="cid" /></span>
            </div>
          </div>
          <div style="text-align: right; flex-shrink: 0">
            <div class="mono" style="font-size: 16px; font-weight: 700">{{ shipments.filter((s) => s.projectId === p.id).length }}</div>
            <div style="font-size: 9px; color: #94a3b8; font-weight: 600; text-transform: uppercase">Shipments</div>
            <div class="mono" style="font-size: 12px; font-weight: 600; color: #475569; margin-top: 4px">
              {{ fmtUsd(shipments.filter((s) => s.projectId === p.id).reduce((a, s) => a + toUsd(s), 0)) }}
            </div>
          </div>
        </div>
      </div>
      <div v-if="!filtered.length" class="empty">No projects yet</div>
    </div>

    <UiAppModal :open="showForm" :title="editing ? 'Edit Project' : 'New Project'" :width="480" @close="showForm = false">
      <div style="display: grid; gap: 12px">
        <div><label class="lbl">Project Name *</label><input v-model="form.name" class="inp" placeholder="Azrieli Tower Phase 2" /></div>
        <div><label class="lbl">Client</label><input v-model="form.client" class="inp" placeholder="Client company name" /></div>
        <div>
          <label class="lbl">Status</label>
          <select v-model="form.status" class="inp">
            <option>Active</option><option>Completed</option><option>On Hold</option>
          </select>
        </div>
        <div><label class="lbl">Description</label><textarea v-model="form.description" class="inp" rows="3" style="resize: vertical" placeholder="Project details..."></textarea></div>
      </div>
      <div v-if="err" style="margin-top: 10px; padding: 8px 12px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 7px; font-size: 12px; color: #dc2626; font-weight: 600">{{ err }}</div>
      <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px">
        <button class="btn btn-secondary" @click="showForm = false">Cancel</button>
        <button class="btn btn-accent" :disabled="saving" @click="save">{{ saving ? "Saving…" : editing ? "Save Changes" : "Create Project" }}</button>
      </div>
    </UiAppModal>
  </div>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; animation: fadeIn .3s; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
h2 { font-size: 20px; font-weight: 800; }
.back-link {
  display: inline-flex; align-items: center; gap: 6px; background: none; border: none; cursor: pointer;
  color: #3b82f6; font-family: inherit; font-size: 12.5px; font-weight: 700; margin-bottom: 14px; padding: 0;
}
.filters { display: flex; gap: 10px; margin-bottom: 16px; }
.search-wrap { flex: 1; min-width: 180px; position: relative; }
.search-ic { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 12px; opacity: .55; }
.p-list { display: grid; gap: 12px; }
.p-card { background: #fff; border-radius: 12px; padding: 18px 22px; border: 1px solid #f1f5f9; cursor: pointer; transition: all .15s; }
.p-card:hover { border-color: #c7d2fe; }
.sh-list { display: grid; gap: 10px; }
.sh-row {
  background: #fff; border-radius: 11px; padding: 14px 18px; border: 1px solid #f1f5f9;
  cursor: pointer; display: flex; justify-content: space-between; gap: 12px; transition: all .15s;
}
.sh-row:hover { border-color: #c7d2fe; }
.empty { text-align: center; padding: 40px; color: #94a3b8; background: #fff; border-radius: 12px; border: 1px dashed #e2e8f0; }
</style>
