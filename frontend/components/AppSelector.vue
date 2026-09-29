<script setup lang="ts">
// App selector screen - mirrors the original portal card grid
const props = defineProps<{ user: any }>();
const emit = defineEmits<{ (e: "open", app: string): void; (e: "admin"): void }>();

const showPwd = ref(false);
const roleLabels: Record<string, string> = { admin: "Admin", user: "User", viewer: "Reports Viewer", sales: "Sales" };
const roleColors: Record<string, string> = { admin: "#8b5cf6", user: "#3b82f6", viewer: "#64748b", sales: "#f59e0b" };

const facadeRole = computed(() => props.user?.apps?.facade?.role || "sales");
const importflowRole = computed(() => props.user?.apps?.importflow?.role || "viewer");
const has = (app: string) => !!props.user?.apps?.[app]?.access;
</script>

<template>
  <div class="selector">
    <div class="selector-inner">
      <!-- Header -->
      <div class="sel-head">
        <div class="sel-brand">
          <div class="sel-icon">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2">
              <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
              <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
            </svg>
          </div>
          <div>
            <div class="sel-title">Interdec Portal</div>
            <div class="sel-sub">UNIFIED ACCESS PORTAL</div>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 8px">
          <UiNotificationBell />
          <button class="pwd-btn" title="Change password" @click="showPwd = true">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </button>
          <div class="sel-user">
            <div class="avatar" :style="{ background: (roleColors[user.platformRole === 'admin' ? 'admin' : 'user'] || '#3b82f6') + '20', color: roleColors[user.platformRole === 'admin' ? 'admin' : 'user'] }">
              {{ user.avatar || user.name.slice(0, 2).toUpperCase() }}
            </div>
            <div>
              <div class="sel-name">{{ user.name }}</div>
              <div class="sel-role">{{ user.platformRole === "admin" ? "Platform Admin" : user.email }}</div>
            </div>
          </div>
        </div>
      </div>

      <p class="sel-cta">Select an application to continue</p>

      <!-- App cards -->
      <div class="cards">
        <button v-if="has('facade')" class="app-card" @click="emit('open', 'facade')">
          <div class="app-ic" style="background: linear-gradient(135deg, #f59e0b, #ea580c)">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8">
              <rect x="3" y="4" width="20" height="18" rx="2"/><line x1="3" y1="10" x2="23" y2="10"/>
              <line x1="10" y1="4" x2="10" y2="22"/><line x1="16.5" y1="4" x2="16.5" y2="22"/>
            </svg>
          </div>
          <div class="app-name">Facade Pricing</div>
          <div class="app-desc">Quotation &amp; pricing system for aluminium &amp; glass products</div>
          <div class="app-access" :style="{ color: roleColors[facadeRole] }">Access: {{ roleLabels[facadeRole] }}</div>
        </button>

        <button v-if="has('importflow')" class="app-card" @click="emit('open', 'importflow')">
          <div class="app-ic" style="background: linear-gradient(135deg, #3b82f6, #8b5cf6)">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8">
              <path d="M4 19l3-3h5l2 2h6l4-4"/><rect x="2" y="8" width="8" height="6" rx="1"/>
              <circle cx="22" cy="14" r="4"/><path d="M6 8V5h4"/><path d="M22 10V7"/><path d="M20 9h4"/>
            </svg>
          </div>
          <div class="app-name">ImportFlow</div>
          <div class="app-desc">Importation cycle &amp; shipment management</div>
          <div class="app-access" :style="{ color: roleColors[importflowRole] }">Access: {{ roleLabels[importflowRole] }}</div>
        </button>

        <button v-if="has('catalogues')" class="app-card" @click="emit('open', 'catalogues')">
          <div class="app-ic" style="background: linear-gradient(135deg, #10b981, #059669)">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8">
              <path d="M4 4h5l2 3h11v14H4z"/><path d="M4 10h18"/>
            </svg>
          </div>
          <div class="app-name">Catalogues</div>
          <div class="app-desc">Browse &amp; download vendor product catalogues</div>
          <div
            class="app-access"
            :style="{ color: user.platformRole === 'admin' ? '#8b5cf6' : '#10b981' }"
          >{{ user.platformRole === "admin" ? "Access: Admin" : "View Only" }}</div>
        </button>
      </div>

      <!-- Manage users (platform admin) -->
      <div v-if="user.platformRole === 'admin'" style="margin-top: 28px; text-align: center">
        <button class="manage-btn" @click="emit('admin')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <circle cx="8" cy="5" r="3"/><path d="M2.5 14.5c0-3 2.5-5 5.5-5s5.5 2 5.5 5"/>
            <path d="M12.5 3.5l1 1 2-2"/>
          </svg>
          Manage Users
        </button>
      </div>

      <p class="sel-foot">© {{ new Date().getFullYear() }} Interdec Group · All Rights Reserved</p>
    </div>

    <ChangePasswordModal v-if="showPwd" @close="showPwd = false" />
  </div>
</template>

<style scoped>
.selector { min-height: 100vh; background: #f8fafc; display: flex; justify-content: center; padding: 48px 20px; }
.selector-inner { width: 100%; max-width: 960px; animation: fadeIn .3s; }
.sel-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 14px; margin-bottom: 30px; }
.sel-brand { display: flex; align-items: center; gap: 12px; }
.sel-icon {
  width: 48px; height: 48px; border-radius: 13px;
  background: linear-gradient(135deg, #1e293b, #0f172a);
  display: flex; align-items: center; justify-content: center;
}
.sel-title { font-size: 20px; font-weight: 800; color: #0f172a; }
.sel-sub { font-size: 9px; font-weight: 700; color: #94a3b8; letter-spacing: 2.5px; margin-top: 2px; }
.sel-user { display: flex; align-items: center; gap: 10px; background: #fff; border: 1px solid #e2e8f0; padding: 8px 14px; border-radius: 11px; }
.pwd-btn {
  width: 36px; height: 36px; border-radius: 10px; border: 1.5px solid #e2e8f0; background: #fff;
  color: #475569; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all .15s;
}
.pwd-btn:hover { border-color: #c4b5fd; color: #7c3aed; }
.avatar {
  width: 34px; height: 34px; border-radius: 9px; display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 800;
}
.sel-name { font-size: 12.5px; font-weight: 700; color: #0f172a; }
.sel-role { font-size: 10px; color: #94a3b8; font-weight: 600; }
.sel-cta { font-size: 13px; color: #64748b; margin-bottom: 18px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; }
.app-card {
  background: #fff; border-radius: 16px; padding: 36px 28px; border: 1.5px solid #e2e8f0;
  cursor: pointer; font-family: inherit; text-align: center; transition: all .2s;
  box-shadow: 0 2px 12px rgba(0,0,0,.06); min-height: 200px;
}
.app-card:hover { transform: translateY(-4px); box-shadow: 0 12px 32px rgba(59,130,246,.15); border-color: #93c5fd; }
.app-ic { width: 56px; height: 56px; border-radius: 14px; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; }
.app-name { font-size: 18px; font-weight: 800; color: #0f172a; margin-bottom: 4px; }
.app-desc { font-size: 12.5px; color: #94a3b8; line-height: 1.5; }
.app-access { margin-top: 10px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .8px; }
.manage-btn {
  display: inline-flex; align-items: center; gap: 8px; padding: 10px 22px;
  background: #fff; border: 1.5px solid #e2e8f0; border-radius: 10px; cursor: pointer;
  font-family: inherit; font-size: 13px; font-weight: 600; color: #475569; transition: all .2s;
}
.manage-btn:hover { border-color: #ef4444; color: #ef4444; }
.sel-foot { margin-top: 40px; text-align: center; font-size: 11px; color: #94a3b8; }
</style>
