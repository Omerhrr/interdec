<script setup lang="ts">
// Projects page - list w/ filters, detail w/ shipments, CRUD
const props = defineProps<{ detail?: string | null; detailId?: string | null }>();
const emit = defineEmits<{ (e: "navigate", p: string, d?: string | null, id?: string | null): void }>();
const { projects, shipments, company } = useData();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { confirm } = useConfirm();
const { request } = useApi();
const { fmtDate } = useConstants();

const search = ref("");
const statusFilter = ref("All");
const showForm = ref(false);
const editing = ref<any>(null);
const form = ref<any>({});
const { snap, dirty } = useDirty(() => form.value);
const err = ref("");
const saving = ref(false);
const newShipment = ref(false);

const { importflowRole: role } = useAuth();
const canEdit = computed(() => role.value === "admin" || role.value === "user");

const { toUsd } = useData();
const fmtUsd = (n: number) => "$ " + Math.round(n).toLocaleString();

// budget vs actual for every project (naira), refreshed when shipments change
const budgets = ref<Record<string, any>>({});
const loadBudgets = async () => {
  try { budgets.value = await request("/api/projects/budgets"); } catch { /* card just stays hidden */ }
};
onMounted(loadBudgets);
watch(() => shipments.value.map((s: any) => s.updated).join(), loadBudgets);
const shortN = (n: number) => {
  const a = Math.abs(n || 0);
  return (n < 0 ? "−₦" : "₦") + (a >= 1e9 ? (a / 1e9).toFixed(2) + "B" : a >= 1e6 ? (a / 1e6).toFixed(1) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : Math.round(a));
};

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
  nextTick(snap);
};
const openEdit = (p: any) => {
  editing.value = p;
  form.value = { name: p.name, client: p.client, description: p.description, status: p.status };
  err.value = "";
  showForm.value = true;
  nextTick(snap);
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
  if (!(await confirm({ title: `Delete ${p.name}?`, message: "Its shipments and quotes stay, but are no longer linked to a project. This cannot be undone.", confirmLabel: "Delete project", danger: true }))) return;
  try {
    await request(`/api/projects/${p.id}`, { method: "DELETE" });
    notify("Project deleted");
    await useData().loadAll();
    emit("navigate", "projects", null, null);
  } catch (e: any) {
    notify(e.message, "error");
  }
};

// fills stay bright; text uses the dark shade so chips pass 4.5:1 contrast
const statusColor = (s: string) => (s === "Active" ? "#10b981" : s === "Completed" ? "#6366f1" : "#f59e0b");
const statusText = (s: string) => (s === "Active" ? "#047857" : s === "Completed" ? "#4338ca" : "#92400e");
const detailProject = computed(() => projects.value.find((p) => p.id === props.detailId));
const detailShipments = computed(() =>
  detailProject.value ? shipments.value.filter((s) => s.projectId === detailProject.value!.id) : []
);
</script>

<template>
  <!-- DETAIL -->
  <div v-if="detail === 'detail' && detailProject" class="page">
    <div class="topbar">
      <button class="back-link" @click="emit('navigate', 'projects', null, null)">← Projects</button>
      <IfExportMenu kind="project" :params="{ id: detailProject.id }" />
    </div>

    <div class="card" style="margin-bottom: 14px">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap">
        <div>
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap">
            <h1 style="font-size: 17px; font-weight: 800">{{ detailProject.name }}</h1>
            <span class="chip" :style="{ background: statusColor(detailProject.status) + '18', color: statusText(detailProject.status) }">{{ detailProject.status }}</span>
          </div>
          <div style="font-size: 12.5px; color: #64748b">Client: <strong>{{ detailProject.client || "N/A" }}</strong></div>
          <p v-if="detailProject.description" style="font-size: 12.5px; color: #64748b; margin-top: 4px; max-width: 560px">{{ detailProject.description }}</p>
          <div style="font-size: 10.5px; color: #64748b; margin-top: 6px">Created {{ fmtDate(detailProject.created) }}</div>
        </div>
        <div v-if="canEdit" style="display: flex; gap: 6px; flex-shrink: 0">
          <button class="btn btn-secondary btn-sm" @click="openEdit(detailProject)"><UiIcon name="edit" :size="13" /> Edit</button>
          <UiMenu :items="[{ label: 'Delete project', icon: 'trash', danger: true, onClick: () => remove(detailProject) }]" />
        </div>
      </div>
    </div>

    <IfProjectBudget :budget="budgets[detailProject.id] || null" />

    <div class="head" style="margin-bottom: 12px">
      <h2 style="font-size: 14px; font-weight: 700; color: #475569">Shipments ({{ detailShipments.length }})</h2>
      <button v-if="canEdit && detailProject.status === 'Active'" class="btn btn-accent btn-sm" @click="newShipment = true"><UiIcon name="plus" :size="14" /> New Shipment</button>
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

    <IfNewShipmentModal
      v-if="newShipment"
      :preset-project-id="detailProject.id"
      @close="newShipment = false"
      @created="(id: string) => emit('navigate', 'shipments', 'detail', id)"
    />

    <UiAppModal :open="showForm" :dirty="dirty" :title="editing ? 'Edit Project' : 'New Project'" :width="480" @close="showForm = false">
      <div style="display: grid; gap: 12px">
        <div><label class="lbl" for="pj-name">Project name *</label><input :id="`pj-name`" v-model="form.name" class="inp" placeholder="Azrieli Tower Phase 2" /></div>
        <div><label class="lbl" for="pj-client">Client</label><input :id="`pj-client`" v-model="form.client" class="inp" placeholder="Client company name" /></div>
        <div>
          <label class="lbl" for="pj-status">Status</label>
          <select id="pj-status" v-model="form.status" class="inp">
            <option>Active</option><option>Completed</option><option>On Hold</option>
          </select>
        </div>
        <div><label class="lbl" for="pj-desc">Description</label><textarea id="pj-desc" v-model="form.description" class="inp" rows="3" style="resize: vertical" placeholder="Project details..."></textarea></div>
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
      <h1 class="ph">Projects</h1>
      <div class="head-acts">
        <IfExportMenu kind="projects" :params="{ status: statusFilter, q: search }" />
        <button v-if="canEdit" class="btn btn-accent" @click="openNew"><UiIcon name="plus" :size="15" /> New Project</button>
      </div>
    </div>

    <div class="filters">
      <div class="search-wrap">
        <span class="search-ic"><UiIcon name="search" :size="14" /></span>
        <input v-model="search" class="inp" placeholder="Search by project or client" style="padding-left: 32px" aria-label="Search projects" />
      </div>
      <select v-model="statusFilter" class="inp" style="width: auto" aria-label="Filter by status">
        <option value="All">All Statuses</option>
        <option>Active</option><option>Completed</option><option>On Hold</option>
      </select>
    </div>

    <div class="count">{{ filtered.length === projects.length ? `${projects.length} projects` : `${filtered.length} of ${projects.length} projects` }}</div>
    <div class="p-list">
      <div v-for="p in filtered" :key="p.id" class="p-card" @click="emit('navigate', 'projects', 'detail', p.id)">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px">
          <div style="min-width: 0">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap">
              <h2 style="font-size: 15px; font-weight: 700; margin: 0">{{ p.name }}</h2>
              <span class="chip" :style="{ background: statusColor(p.status) + '18', color: statusText(p.status) }">{{ p.status }}</span>
            </div>
            <div style="font-size: 12.5px; color: #64748b">Client: <strong>{{ p.client || "N/A" }}</strong></div>
            <p v-if="p.description" style="font-size: 12px; color: #64748b; margin-top: 3px">{{ p.description }}</p>
            <div style="display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap">
              <span
                v-for="cid in [...new Set(shipments.filter((s) => s.projectId === p.id).map((s) => s.companyId))]"
                :key="cid"
              ><UiCompanyChip :id="cid" /></span>
            </div>
          </div>
          <div style="text-align: right; flex-shrink: 0">
            <div class="mono" style="font-size: 16px; font-weight: 700">{{ shipments.filter((s) => s.projectId === p.id).length }}</div>
            <div style="font-size: 9px; color: #64748b; font-weight: 600; text-transform: uppercase">Shipments</div>
            <div class="mono" style="font-size: 12px; font-weight: 600; color: #475569; margin-top: 4px">
              {{ fmtUsd(shipments.filter((s) => s.projectId === p.id).reduce((a, s) => a + toUsd(s), 0)) }}
            </div>
            <div v-if="budgets[p.id]?.contract" class="mg" :class="{ neg: budgets[p.id].margin < 0 }" :title="`Contract ${shortN(budgets[p.id].contract)} · spent ${shortN(budgets[p.id].spent)}`">
              Margin {{ budgets[p.id].marginPct }}%
            </div>
          </div>
        </div>
      </div>
      <div v-if="!filtered.length" class="empty">{{ projects.length ? "No projects match these filters" : "No projects yet" }}</div>
    </div>

    <UiAppModal :open="showForm" :dirty="dirty" :title="editing ? 'Edit Project' : 'New Project'" :width="480" @close="showForm = false">
      <div style="display: grid; gap: 12px">
        <div><label class="lbl" for="pj-name">Project name *</label><input :id="`pj-name`" v-model="form.name" class="inp" placeholder="Azrieli Tower Phase 2" /></div>
        <div><label class="lbl" for="pj-client">Client</label><input :id="`pj-client`" v-model="form.client" class="inp" placeholder="Client company name" /></div>
        <div>
          <label class="lbl" for="pj-status">Status</label>
          <select id="pj-status" v-model="form.status" class="inp">
            <option>Active</option><option>Completed</option><option>On Hold</option>
          </select>
        </div>
        <div><label class="lbl" for="pj-desc">Description</label><textarea id="pj-desc" v-model="form.description" class="inp" rows="3" style="resize: vertical" placeholder="Project details..."></textarea></div>
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
.ph { font-size: 20px; font-weight: 800; }
.back-link {
  display: inline-flex; align-items: center; gap: 6px; background: none; border: none; cursor: pointer;
  color: #3b82f6; font-family: inherit; font-size: 12.5px; font-weight: 700; margin-bottom: 14px; padding: 0;
}
.filters { display: flex; gap: 10px; margin-bottom: 16px; }
.search-wrap { flex: 1; min-width: 180px; position: relative; }
.search-ic { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #64748b; display: flex; }
.p-list { display: grid; gap: 12px; }
.mg { margin-top: 6px; font-size: 11px; font-weight: 800; color: #047857; background: #ecfdf5; border-radius: 20px; padding: 2px 8px; display: inline-block; }
.mg.neg { color: #b91c1c; background: #fef2f2; }
.p-card { background: #fff; border-radius: 12px; padding: 18px 22px; border: 1px solid #f1f5f9; cursor: pointer; transition: all .15s; }
.p-card:hover { border-color: #c7d2fe; }
.sh-list { display: grid; gap: 10px; }
.sh-row {
  background: #fff; border-radius: 11px; padding: 14px 18px; border: 1px solid #f1f5f9;
  cursor: pointer; display: flex; justify-content: space-between; gap: 12px; transition: all .15s;
}
.sh-row:hover { border-color: #c7d2fe; }
.count { font-size: 12px; color: #64748b; margin: -6px 0 12px; }
.empty { text-align: center; padding: 40px; color: #64748b; background: #fff; border-radius: 12px; border: 1px dashed #e2e8f0; }
</style>
