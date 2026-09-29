<script setup lang="ts">
// User Management - platform admin (mirrors original)
const props = defineProps<{ users: any[] }>();
const emit = defineEmits<{ (e: "back"): void; (e: "refresh"): void }>();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { user } = useAuth();
const { request } = useApi();

const showForm = ref(false);
const editing = ref<any>(null);
const err = ref("");
const saving = ref(false);
const form = ref<any>({});

const ROLE_COLORS: Record<string, string> = { admin: "#8b5cf6", user: "#3b82f6", viewer: "#64748b", sales: "#f59e0b" };

const blank = () => ({
  __new: true, name: "", email: "", _password: "", avatar: "",
  platformRole: "user",
  apps: {
    facade: { access: false, role: "sales" },
    importflow: { access: false, role: "viewer" },
    catalogues: { access: false },
  },
});

const openNew = () => {
  editing.value = null;
  form.value = blank();
  err.value = "";
  showForm.value = true;
};

const openEdit = (u: any) => {
  editing.value = u;
  form.value = {
    __new: false, id: u.id, name: u.name, email: u.email, _password: "",
    avatar: u.avatar || "",
    platformRole: u.platformRole || "user",
    apps: JSON.parse(JSON.stringify({
      facade: { access: false, role: "sales" },
      importflow: { access: false, role: "viewer" },
      catalogues: { access: false },
      ...(u.apps || {}),
    })),
  };
  err.value = "";
  showForm.value = true;
};

const setApp = (key: string, patch: any) => {
  form.value.apps[key] = { ...(form.value.apps[key] || {}), ...patch };
};

const save = async () => {
  err.value = "";
  if (!form.value.name?.trim()) { err.value = "Name is required"; return; }
  if (!form.value.email?.trim()) { err.value = "Email is required"; return; }
  if (form.value.__new && form.value._password.length < 6) { err.value = "Password must be at least 6 characters"; return; }
  saving.value = true;
  try {
    if (form.value.__new) {
      await request("/api/users", {
        method: "POST",
        body: {
          name: form.value.name, email: form.value.email, password: form.value._password,
          avatar: form.value.avatar, platformRole: form.value.platformRole, apps: form.value.apps,
        },
      });
      notify("User created");
    } else {
      await request(`/api/users/${form.value.id}`, {
        method: "PUT",
        body: {
          name: form.value.name, email: form.value.email,
          password: form.value._password || undefined,
          avatar: form.value.avatar, platformRole: form.value.platformRole, apps: form.value.apps,
        },
      });
      notify("User updated");
    }
    showForm.value = false;
    emit("refresh");
  } catch (e: any) {
    err.value = e.message;
  } finally {
    saving.value = false;
  }
};

const toggleActive = async (u: any) => {
  try {
    await request(`/api/users/${u.id}`, { method: "PUT", body: { active: !u.active } });
    notify(u.active ? "User disabled" : "User enabled");
    emit("refresh");
  } catch (e: any) {
    notify(e.message, "error");
  }
};

const appBadge = (u: any, key: string) => {
  const a = u.apps?.[key];
  if (!a?.access) return { label: "None", color: "#94a3b8" };
  if (key === "catalogues") return { label: "View", color: "#10b981" };
  const role = a.role || "viewer";
  return { label: role === "admin" ? "Admin" : role === "user" ? "User" : role === "sales" ? "Sales" : "Viewer", color: ROLE_COLORS[role] || "#64748b" };
};
</script>

<template>
  <div style="min-height: 100vh; background: #f8fafc">
    <!-- Header -->
    <div class="um-head">
      <div style="display: flex; align-items: center; gap: 10px">
        <button class="back-portal" @click="emit('back')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2">
            <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
            <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
          </svg>
          Portal
        </button>
        <span style="color: #334155">|</span>
        <span style="color: #fff; font-size: 14px; font-weight: 700">⚙ User Management</span>
      </div>
      <div style="display: flex; align-items: center; gap: 10px">
        <span style="font-size: 10.5px; font-weight: 700; color: #ef4444; text-transform: uppercase; letter-spacing: .6px">Platform Admin</span>
        <div class="um-avatar">{{ user?.avatar || "A" }}</div>
      </div>
    </div>

    <div class="um-body">
      <div class="um-headrow">
        <div>
          <h2 style="margin: 0; font-size: 20px; font-weight: 800">Platform Users</h2>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #94a3b8">{{ users.length }} user{{ users.length === 1 ? "" : "s" }} · manage access &amp; roles</p>
        </div>
        <button class="btn btn-accent" @click="openNew">＋ New User</button>
      </div>

      <div class="um-tablecard">
        <table class="um-table">
          <thead>
            <tr>
              <th>User</th><th>Platform Role</th><th>Facade</th><th>ImportFlow</th><th>Catalogues</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>
                <div style="display: flex; align-items: center; gap: 9px">
                  <div class="um-av" :style="{ background: ROLE_COLORS[u.platformRole === 'admin' ? 'admin' : 'user'] + '18', color: ROLE_COLORS[u.platformRole === 'admin' ? 'admin' : 'user'] }">
                    {{ u.avatar || u.name.slice(0, 2).toUpperCase() }}
                  </div>
                  <div>
                    <div style="font-size: 12.5px; font-weight: 700; color: #0f172a">{{ u.name }}</div>
                    <div style="font-size: 10.5px; color: #94a3b8">{{ u.email }}</div>
                  </div>
                </div>
              </td>
              <td>
                <span class="chip" :style="{ background: (u.platformRole === 'admin' ? '#8b5cf6' : '#dbeafe'), color: (u.platformRole === 'admin' ? '#6d28d9' : '#1d4ed8') }">
                  {{ u.platformRole === "admin" ? "Admin" : "User" }}
                </span>
                <span class="chip" :style="{ marginLeft: '5px', background: u.active ? '#d1fae5' : '#fee2e2', color: u.active ? '#059669' : '#dc2626' }">
                  {{ u.active ? "Active" : "Disabled" }}
                </span>
              </td>
              <td><span class="chip" :style="{ background: appBadge(u, 'facade').color + '15', color: appBadge(u, 'facade').color }">{{ appBadge(u, 'facade').label }}</span></td>
              <td><span class="chip" :style="{ background: appBadge(u, 'importflow').color + '15', color: appBadge(u, 'importflow').color }">{{ appBadge(u, 'importflow').label }}</span></td>
              <td><span class="chip" :style="{ background: appBadge(u, 'catalogues').color + '15', color: appBadge(u, 'catalogues').color }">{{ appBadge(u, 'catalogues').label }}</span></td>
              <td style="white-space: nowrap; text-align: right">
                <button class="btn btn-secondary btn-sm" @click="openEdit(u)">Edit</button>
                <button class="btn btn-secondary btn-sm" :style="{ color: u.active ? '#dc2626' : '#16a34a' }" @click="toggleActive(u)">
                  {{ u.active ? "Disable" : "Enable" }}
                </button>
              </td>
            </tr>
            <tr v-if="!users.length">
              <td colspan="6" style="text-align: center; padding: 30px; color: #94a3b8">Loading users…</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- User form modal -->
    <UiAppModal :open="showForm" :title="form.__new ? 'New User' : `Edit: ${form.name}`" :width="560" @close="showForm = false">
      <div style="display: grid; gap: 12px">
        <div style="display: grid; grid-template-columns: 1fr 100px; gap: 12px">
          <div>
            <label class="lbl">Full Name *</label>
            <input v-model="form.name" class="inp" placeholder="Jane Doe" />
          </div>
          <div>
            <label class="lbl">Avatar</label>
            <input v-model="form.avatar" class="inp" placeholder="JD" maxlength="2"
              style="text-align: center; font-weight: 800; text-transform: uppercase" />
          </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
          <div>
            <label class="lbl">Email *</label>
            <input v-model="form.email" class="inp" type="email" placeholder="user@interdecng.com" :disabled="!form.__new" />
            <span v-if="!form.__new" style="font-size: 10px; color: #94a3b8">Email cannot be changed after creation.</span>
          </div>
          <div>
            <label class="lbl">{{ form.__new ? "Password *" : "New Password" }}</label>
            <input v-model="form._password" class="inp" type="password" :placeholder="form.__new ? 'Min 6 chars' : 'Leave blank to keep'" />
          </div>
        </div>
        <div>
          <label class="lbl">Platform Role</label>
          <select v-model="form.platformRole" class="inp">
            <option value="user">User</option>
            <option value="admin">Admin (can manage users)</option>
          </select>
        </div>

        <div style="border-top: 1px solid #f1f5f9; padding-top: 14px">
          <div style="font-size: 11px; font-weight: 700; color: #334155; text-transform: uppercase; letter-spacing: .8px; margin-bottom: 10px">
            App Access &amp; Roles
          </div>
          <div style="display: grid; gap: 10px">
            <div class="app-row">
              <label class="switch-label">
                <input type="checkbox" :checked="form.apps.facade?.access" @change="setApp('facade', { access: ($event.target as HTMLInputElement).checked })" />
                🪟 Facade Pricing
              </label>
              <select v-if="form.apps.facade?.access" class="inp" style="width: 130px; padding: 5px 8px; font-size: 11px"
                :value="form.apps.facade?.role || 'sales'" @change="setApp('facade', { role: ($event.target as HTMLSelectElement).value })">
                <option value="admin">Admin</option>
                <option value="sales">Sales</option>
              </select>
            </div>
            <div class="app-row">
              <label class="switch-label">
                <input type="checkbox" :checked="form.apps.importflow?.access" @change="setApp('importflow', { access: ($event.target as HTMLInputElement).checked })" />
                📦 ImportFlow
              </label>
              <select v-if="form.apps.importflow?.access" class="inp" style="width: 130px; padding: 5px 8px; font-size: 11px"
                :value="form.apps.importflow?.role || 'viewer'" @change="setApp('importflow', { role: ($event.target as HTMLSelectElement).value })">
                <option value="admin">Admin</option>
                <option value="user">User</option>
                <option value="viewer">Reports Viewer</option>
              </select>
            </div>
            <div class="app-row">
              <label class="switch-label">
                <input type="checkbox" :checked="form.apps.catalogues?.access" @change="setApp('catalogues', { access: ($event.target as HTMLInputElement).checked })" />
                📂 Catalogues
              </label>
              <span v-if="form.apps.catalogues?.access" style="font-size: 10.5px; color: #10b981; font-weight: 600">View-only, no role needed</span>
            </div>
          </div>
        </div>

        <div v-if="err" style="padding: 10px 14px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; font-size: 12.5px; color: #dc2626; font-weight: 600">
          ⚠️ {{ err }}
        </div>

        <div style="display: flex; gap: 8px; justify-content: flex-end; padding-top: 2px">
          <button class="btn btn-secondary" @click="showForm = false">Cancel</button>
          <button class="btn btn-accent" :disabled="saving" @click="save">
            {{ saving ? "Saving…" : form.__new ? "Create User" : "Save Changes" }}
          </button>
        </div>
      </div>
    </UiAppModal>
  </div>
</template>

<style scoped>
.um-head {
  display: flex; align-items: center; justify-content: space-between;
  background: linear-gradient(135deg, #1e293b, #0f172a); padding: 14px 22px;
}
.back-portal {
  display: inline-flex; align-items: center; gap: 7px; background: rgba(51,65,85,.6);
  border: 1px solid #334155; color: #fff; padding: 7px 14px; border-radius: 8px;
  cursor: pointer; font-family: inherit; font-size: 12px; font-weight: 700; transition: all .15s;
}
.back-portal:hover { background: #334155; }
.um-avatar {
  width: 30px; height: 30px; border-radius: 8px; background: #ef444420; color: #ef4444;
  display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800;
}
.um-body { max-width: 1000px; margin: 0 auto; padding: 26px 24px; }
.um-headrow { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
.um-tablecard { background: #fff; border-radius: 12px; border: 1px solid #f1f5f9; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.03); }
.um-table { width: 100%; border-collapse: collapse; }
.um-table th {
  padding: 11px 14px; text-align: left; font-size: 10px; font-weight: 700; color: #64748b;
  text-transform: uppercase; letter-spacing: .6px; background: #f8fafc; border-bottom: 2px solid #e2e8f0;
}
.um-table td { padding: 11px 14px; border-bottom: 1px solid #f1f5f9; font-size: 12px; }
.um-table tr:hover td { background: #fafbfc; }
.um-av {
  width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 800; flex-shrink: 0;
}
.app-row {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 9px 12px; background: #f8fafc; border: 1px solid #f1f5f9; border-radius: 8px;
}
.switch-label { display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 700; color: #334155; cursor: pointer; }
.switch-label input { width: 15px; height: 15px; cursor: pointer; }
</style>
