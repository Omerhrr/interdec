<script setup lang="ts">
// User Management - platform admin (mirrors original)
const props = defineProps<{ users: any[] }>();
const emit = defineEmits<{ (e: "back"): void; (e: "refresh"): void }>();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { confirm } = useConfirm();
const { user } = useAuth();
const { request } = useApi();

const showForm = ref(false);
const editing = ref<any>(null);
const err = ref("");
const saving = ref(false);
const form = ref<any>({});
const { snap, dirty } = useDirty(() => form.value);

const ROLE_COLORS: Record<string, string> = { admin: "#6d28d9", user: "#1d4ed8", viewer: "#475569", sales: "#92400e" };

const blank = () => ({
  __new: true, name: "", email: "", _password: "", avatar: "",
  platformRole: "user",
  apps: {
    facade: { access: false, role: "sales" },
    importflow: { access: false, role: "viewer" },
    catalogues: { access: false },
    quotes: { access: false, role: "sales" },
  },
});

const openNew = () => {
  editing.value = null;
  form.value = blank();
  err.value = "";
  showForm.value = true;
  nextTick(snap);
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
      quotes: { access: false, role: "sales" },
      ...(u.apps || {}),
    })),
  };
  err.value = "";
  showForm.value = true;
  nextTick(snap);
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

const removeUser = async (u: any) => {
  if (!(await confirm({ title: `Delete ${u.name}?`, message: `${u.email} loses access immediately and this cannot be undone. Disabling the account keeps their history instead.`, confirmLabel: "Delete user", danger: true }))) return;
  try {
    await request(`/api/users/${u.id}`, { method: "DELETE" });
    notify("User deleted");
    emit("refresh");
  } catch (e: any) {
    notify(e.message, "error");
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
  if (!a?.access) return { label: "None", color: "#475569" };
  if (key === "catalogues") return { label: "View", color: "#047857" };
  if (key === "quotes" && !a?.role) return { label: "Sales", color: ROLE_COLORS.sales };
  const role = a.role || "viewer";
  return { label: role === "admin" ? "Admin" : role === "user" ? "User" : role === "sales" ? "Sales" : "Viewer", color: ROLE_COLORS[role] || "#64748b" };
};
</script>

<template>
  <div style="min-height: 100vh; background: #f8fafc">
    <!-- Header -->
    <header class="um-head">
      <button class="back-portal" @click="emit('back')"><UiIcon name="back" :size="14" /> Portal</button>
      <div class="um-who">
        <UiNotificationBell />
        <div class="um-avatar" aria-hidden="true">{{ user?.avatar || "A" }}</div>
      </div>
    </header>

    <main class="um-body">
      <div class="um-headrow">
        <div>
          <h1 style="margin: 0; font-size: 20px; font-weight: 800">User management</h1>
          <p style="margin: 4px 0 0; font-size: 12.5px; color: #64748b">{{ users.length }} user{{ users.length === 1 ? "" : "s" }} · manage access &amp; roles</p>
        </div>
        <button class="btn btn-accent" @click="openNew"><UiIcon name="plus" :size="15" /> New user</button>
      </div>

      <div class="um-tablecard">
        <table class="um-table">
          <thead>
            <tr>
              <th>User</th><th>Platform Role</th><th>Quotations</th><th>Facade</th><th>ImportFlow</th><th>Catalogues</th><th><span class="sr-only">Actions</span></th>
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
                    <div style="font-size: 10.5px; color: #64748b">{{ u.email }}</div>
                  </div>
                </div>
              </td>
              <td>
                <span class="chip" :style="{ background: (u.platformRole === 'admin' ? '#ede9fe' : '#dbeafe'), color: (u.platformRole === 'admin' ? '#5b21b6' : '#1d4ed8') }">
                  {{ u.platformRole === "admin" ? "Admin" : "User" }}
                </span>
                <span class="chip" :style="{ marginLeft: '5px', background: u.active ? '#d1fae5' : '#fee2e2', color: u.active ? '#047857' : '#b91c1c' }">
                  {{ u.active ? "Active" : "Disabled" }}
                </span>
              </td>
              <td><span class="chip" :style="{ background: appBadge(u, 'quotes').color + '15', color: appBadge(u, 'quotes').color }">{{ appBadge(u, 'quotes').label }}</span></td>
              <td><span class="chip" :style="{ background: appBadge(u, 'facade').color + '15', color: appBadge(u, 'facade').color }">{{ appBadge(u, 'facade').label }}</span></td>
              <td><span class="chip" :style="{ background: appBadge(u, 'importflow').color + '15', color: appBadge(u, 'importflow').color }">{{ appBadge(u, 'importflow').label }}</span></td>
              <td><span class="chip" :style="{ background: appBadge(u, 'catalogues').color + '15', color: appBadge(u, 'catalogues').color }">{{ appBadge(u, 'catalogues').label }}</span></td>
              <td style="white-space: nowrap; text-align: right">
                <div style="display: inline-flex; gap: 6px; align-items: center">
                  <button class="btn btn-secondary btn-sm" @click="openEdit(u)"><UiIcon name="edit" :size="13" /> Edit</button>
                  <UiMenu v-if="u.id !== user?.id" :label="`More actions for ${u.name}`" :items="[
                    { label: u.active ? 'Disable account' : 'Enable account', icon: u.active ? 'lock' : 'check', onClick: () => toggleActive(u) },
                    { label: 'Delete user', icon: 'trash', danger: true, onClick: () => removeUser(u) },
                  ]" />
                </div>
              </td>
            </tr>
            <tr v-if="!users.length">
              <td colspan="7" style="text-align: center; padding: 30px; color: #64748b">Loading users…</td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>

    <!-- User form modal -->
    <UiAppModal :open="showForm" :dirty="dirty" :title="form.__new ? 'New User' : `Edit: ${form.name}`" :width="560" @close="showForm = false">
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
            <span v-if="!form.__new" style="font-size: 10px; color: #64748b">Email cannot be changed after creation.</span>
          </div>
          <div>
            <label class="lbl" for="u-pw">{{ form.__new ? "Password *" : "New password" }}</label>
            <UiPasswordInput id="u-pw" v-model="form._password" autocomplete="new-password" :placeholder="form.__new ? 'At least 6 characters' : 'Leave blank to keep'" />
          </div>
        </div>
        <div>
          <label class="lbl" for="u-role">Platform role</label>
          <select id="u-role" v-model="form.platformRole" class="inp">
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
                <input type="checkbox" :checked="form.apps.quotes?.access" @change="setApp('quotes', { access: ($event.target as HTMLInputElement).checked })" />
                <UiIcon name="file" :size="15" /> Quotations
              </label>
              <select v-if="form.apps.quotes?.access" class="inp" aria-label="Quotations role" style="width: 130px; padding: 5px 8px; font-size: 11px"
                :value="form.apps.quotes?.role || 'sales'" @change="setApp('quotes', { role: ($event.target as HTMLSelectElement).value })">
                <option value="admin">Admin</option>
                <option value="sales">Sales</option>
              </select>
            </div>
            <div class="app-row">
              <label class="switch-label">
                <input type="checkbox" :checked="form.apps.facade?.access" @change="setApp('facade', { access: ($event.target as HTMLInputElement).checked })" />
                <UiIcon name="archive" :size="15" /> Legacy Facade archive
              </label>
              <select v-if="form.apps.facade?.access" class="inp" aria-label="Legacy archive role" style="width: 130px; padding: 5px 8px; font-size: 11px"
                :value="form.apps.facade?.role || 'sales'" @change="setApp('facade', { role: ($event.target as HTMLSelectElement).value })">
                <option value="admin">Admin</option>
                <option value="sales">Sales</option>
              </select>
            </div>
            <div class="app-row">
              <label class="switch-label">
                <input type="checkbox" :checked="form.apps.importflow?.access" @change="setApp('importflow', { access: ($event.target as HTMLInputElement).checked })" />
                <UiIcon name="ship" :size="15" /> ImportFlow
              </label>
              <select v-if="form.apps.importflow?.access" class="inp" aria-label="ImportFlow role" style="width: 130px; padding: 5px 8px; font-size: 11px"
                :value="form.apps.importflow?.role || 'viewer'" @change="setApp('importflow', { role: ($event.target as HTMLSelectElement).value })">
                <option value="admin">Admin</option>
                <option value="user">User</option>
                <option value="viewer">Reports Viewer</option>
              </select>
            </div>
            <div class="app-row">
              <label class="switch-label">
                <input type="checkbox" :checked="form.apps.catalogues?.access" @change="setApp('catalogues', { access: ($event.target as HTMLInputElement).checked })" />
                <UiIcon name="folder" :size="15" /> Catalogues
              </label>
              <span v-if="form.apps.catalogues?.access" style="font-size: 10.5px; color: #10b981; font-weight: 600">View-only (platform admins can manage)</span>
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
.um-head { display: flex; align-items: center; justify-content: space-between; max-width: 1000px; margin: 0 auto; padding: 22px 24px 0; }
.um-who { display: flex; align-items: center; gap: 10px; }
.back-portal { display: inline-flex; align-items: center; gap: 6px; background: #fff; border: 1.5px solid #e2e8f0; color: #334155; padding: 7px 14px; border-radius: 9px; cursor: pointer; font-family: inherit; font-size: 12.5px; font-weight: 700; }
.back-portal:hover { background: #f8fafc; border-color: #cbd5e1; }
.um-avatar { width: 36px; height: 36px; border-radius: 10px; background: #ede9fe; color: #6d28d9; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 800; }
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
.switch-label input { width: 18px; height: 18px; cursor: pointer; }
</style>
