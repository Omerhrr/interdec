<script setup lang="ts">
// ImportFlow shell - dark sidebar w/ nav, user footer (mirrors original)
const props = defineProps<{ user: any; cataloguesMode?: boolean; quotesMode?: boolean; page?: string }>();
const emit = defineEmits<{ (e: "portal"): void; (e: "nav", k: string): void }>();

const roleColors: Record<string, string> = { admin: "#ef4444", user: "#3b82f6", viewer: "#64748b", sales: "#f59e0b" };
const roleLabels: Record<string, string> = { admin: "Admin", user: "User", viewer: "Reports Viewer", sales: "Sales" };

const role = computed(() => {
  if (props.quotesMode) return props.user?.apps?.quotes?.role || props.user?.apps?.facade?.role || "sales";
  if (props.cataloguesMode)
    return props.user?.platformRole === "admin" ? "admin" : "viewer";
  return props.user?.apps?.importflow?.role || "viewer";
});
const isPlatformAdmin = computed(() => props.user?.platformRole === "admin");
const isAdmin = computed(() => role.value === "admin" && !props.cataloguesMode);
const isViewer = computed(() => role.value === "viewer" && !props.quotesMode);

const appTitle = computed(() => (props.quotesMode ? "Quotations" : props.cataloguesMode ? "Catalogues" : "ImportFlow"));
const appSub = computed(() =>
  props.quotesMode ? "Pricing Engine"
  : props.cataloguesMode ? (isPlatformAdmin.value ? "Admin Access" : "View-Only")
  : "Cycle Manager"
);
const appGradient = computed(() =>
  props.quotesMode ? "linear-gradient(135deg,#f59e0b,#ea580c)"
  : props.cataloguesMode ? "linear-gradient(135deg,#10b981,#059669)"
  : "linear-gradient(135deg,#3b82f6,#8b5cf6)"
);

const navItems = computed(() => {
  if (props.quotesMode) {
    const items = [{ k: "quotes", icon: "🧾", label: "Quotations" }];
    if (isPlatformAdmin.value) items.push({ k: "rates", icon: "⚙", label: "Rate Card" });
    return items;
  }
  if (props.cataloguesMode) return [{ k: "vendors", icon: "📂", label: "Vendors" }];
  return [
    { k: "dashboard", icon: "⌂", label: "Dashboard" },
    { k: "vendors", icon: "🏗", label: "Vendors" },
    { k: "shippers", icon: "🚢", label: "Shippers" },
    { k: "projects", icon: "📋", label: "Projects" },
    { k: "shipments", icon: "🔄", label: "Shipments" },
    { k: "reports", icon: "📊", label: "Reports" },
  ].filter((i) => (isAdmin.value ? true : isViewer.value ? i.k === "reports" : true));
});

const { logout } = useAuth();

// Mobile drawer
const mobileOpen = ref(false);
const nav = (k: string) => {
  mobileOpen.value = false;
  emit("nav", k);
};
</script>

<template>
  <div class="shell">
    <!-- Mobile top bar -->
    <div class="mtop">
      <button class="burger" @click="mobileOpen = true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
      <div class="mtop-title">
        {{ appTitle }}
        <span class="mtop-sub">{{ appSub }}</span>
      </div>
      <UiNotificationBell />
    </div>
    <div v-if="mobileOpen" class="backdrop" @click="mobileOpen = false" />

    <!-- Sidebar -->
    <aside class="side" :class="{ open: mobileOpen }">
      <div class="side-head">
        <div class="side-logo" :style="{ background: appGradient }">
          <svg v-if="quotesMode" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8">
            <path d="M6 2h9l4 4v16H6z"/><path d="M14 2v5h5"/><path d="M9 12h7M9 16h7"/>
          </svg>
          <svg v-else-if="cataloguesMode" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8">
            <path d="M4 4h5l2 3h11v14H4z"/><path d="M4 10h18"/>
          </svg>
          <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8">
            <path d="M4 19l3-3h5l2 2h6l4-4"/><rect x="2" y="8" width="8" height="6" rx="1"/>
            <circle cx="22" cy="14" r="4"/><path d="M6 8V5h4"/>
          </svg>
        </div>
        <div>
          <div style="font-size: 14px; font-weight: 800; letter-spacing: -.3px; color: #fff">
            {{ appTitle }}
          </div>
          <div style="font-size: 8.5px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 1px">
            {{ appSub }}
          </div>
        </div>
        <button class="side-close" @click="mobileOpen = false">✕</button>
      </div>

      <button class="back-btn" @click="emit('portal')">
        <span style="font-size: 12px">←</span> Interdec Portal
      </button>

      <div class="side-bell">
        <UiNotificationBell />
      </div>

      <nav class="side-nav">
        <button
          v-for="item in navItems"
          :key="item.k"
          class="nav-btn"
          :style="page === item.k ? { background: '#334155', color: '#fff' } : {}"
          @click="nav(item.k)"
        >
          <span style="font-size: 13px; width: 16px; text-align: center">{{ item.icon }}</span>
          {{ item.label }}
        </button>
      </nav>

      <div class="side-foot">
        <div class="user-row">
          <div class="user-avatar" :style="{ background: (roleColors[role] || '#64748b') + '20', color: roleColors[role] }">
            {{ user.avatar || user.name.slice(0, 2).toUpperCase() }}
          </div>
          <div style="flex: 1; min-width: 0">
            <div class="user-name">{{ user.name }}</div>
            <div class="user-role" :style="{ color: roleColors[role] }">{{ roleLabels[role] }}</div>
          </div>
        </div>
        <button class="logout-btn" @click="logout">Sign Out</button>
      </div>
    </aside>

    <!-- Content -->
    <main class="content">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.shell { display: flex; min-height: 100vh; background: #f8fafc; }
.side {
  width: 208px; flex-shrink: 0; background: linear-gradient(180deg, #1e293b, #0f172a);
  display: flex; flex-direction: column; position: sticky; top: 0; height: 100vh;
}
.side-head { display: flex; align-items: center; gap: 9px; padding: 16px 14px; border-bottom: 1px solid #334155; }
.side-logo {
  width: 30px; height: 30px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.back-btn {
  margin: 10px 12px 4px; display: flex; align-items: center; justify-content: center; gap: 5px;
  width: calc(100% - 24px); padding: 7px; border-radius: 7px; border: none; cursor: pointer;
  background: rgba(51, 65, 85, .5); color: #94a3b8; font-family: inherit; font-size: 10.5px;
  font-weight: 700; transition: all .15s;
}
.back-btn:hover { background: #334155; color: #fff; }
.side-nav { flex: 1; padding: 10px 8px; display: flex; flex-direction: column; gap: 2px; overflow-y: auto; }
.nav-btn {
  display: flex; align-items: center; gap: 9px; padding: 9px 11px; border-radius: 7px; border: none;
  cursor: pointer; font-family: inherit; font-size: 12.5px; font-weight: 600; line-height: 1;
  background: transparent; color: #94a3b8; transition: all .15s; text-align: left;
}
.nav-btn:hover { background: rgba(51,65,85,.5); color: #cbd5e1; }
.side-foot { padding: 12px; border-top: 1px solid #334155; }
.user-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.user-avatar {
  width: 30px; height: 30px; border-radius: 8px; display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 800; flex-shrink: 0;
}
.user-name { font-size: 11.5px; font-weight: 700; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.user-role { font-size: 9.5px; font-weight: 600; }
.logout-btn {
  width: 100%; padding: 6px; border-radius: 6px; border: 1px solid #334155; background: transparent;
  color: #94a3b8; cursor: pointer; font-family: inherit; font-size: 11px; font-weight: 600; transition: all .15s;
}
.logout-btn:hover { background: #334155; color: #fff; }
.content { flex: 1; min-width: 0; }
.side-bell { padding: 8px 12px 0; }
.side-close { display: none; }

/* Mobile top bar + drawer */
.mtop { display: none; }
.backdrop { display: none; }
@media (max-width: 860px) {
  /* stack the shell so the mobile top bar is a real top bar (not a stretched
     flex item squeezed beside the content) */
  .shell { flex-direction: column; }
  .content { width: 100%; }
  .mtop {
    display: flex; align-items: center; gap: 10px; padding: 10px 14px;
    background: linear-gradient(180deg, #1e293b, #0f172a); position: sticky; top: 0; z-index: 40;
    flex-shrink: 0; width: 100%;
  }
  .burger {
    width: 36px; height: 36px; border-radius: 9px; border: 1px solid #334155; background: rgba(51,65,85,.5);
    color: #cbd5e1; cursor: pointer; display: flex; align-items: center; justify-content: center;
  }
  .mtop-title { flex: 1; color: #fff; font-size: 14px; font-weight: 800; }
  .mtop-sub { font-size: 8.5px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-left: 6px; }
  .side {
    position: fixed; left: 0; top: 0; bottom: 0; z-index: 60; transform: translateX(-100%);
    transition: transform .25s ease; width: 240px;
  }
  .side.open { transform: none; box-shadow: 24px 0 60px rgba(0,0,0,.45); }
  .backdrop { display: block; position: fixed; inset: 0; background: rgba(15,23,42,.55); z-index: 50; }
  .side-close {
    display: block; margin-left: auto; background: none; border: none; color: #94a3b8;
    font-size: 14px; cursor: pointer; padding: 2px 4px;
  }
}
</style>
