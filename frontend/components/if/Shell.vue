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
  if (props.user?.platformRole === "admin") return "admin";
  const flow = props.user?.apps?.importflow;
  return flow?.access ? flow.role || "viewer" : "viewer";
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
    const items = [{ k: "quotes", icon: "file", label: "Quotations" }];
    if (isPlatformAdmin.value) {
      items.push({ k: "rates", icon: "settings", label: "Rate Card" });
      items.push({ k: "design", icon: "palette", label: "PDF Design" });
    }
    return items;
  }
  if (props.cataloguesMode) return [{ k: "vendors", icon: "folder", label: "Vendors" }];
  return [
    { k: "dashboard", icon: "home", label: "Dashboard" },
    { k: "vendors", icon: "factory", label: "Vendors" },
    { k: "shippers", icon: "ship", label: "Shippers" },
    { k: "agents", icon: "shield", label: "Clearing Agents" },
    { k: "projects", icon: "clipboard", label: "Projects" },
    { k: "shipments", icon: "cycle", label: "Shipments" },
    { k: "reports", icon: "chart", label: "Reports" },
  ].filter((i) => (isAdmin.value ? true : isViewer.value ? i.k === "reports" : true))
    .concat(!isViewer.value ? [{ k: "import", icon: "upload", label: "Import data" }] : [])
    .concat(isAdmin.value ? [{ k: "design", icon: "palette", label: "Document Design" }] : []);
});

const { logout } = useAuth();

// Desktop: collapse to an icon rail (remembered per browser)
const COLLAPSE_KEY = "interdec_sidebar_collapsed";
const collapsed = ref(false);
onMounted(() => {
  try { collapsed.value = localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { /* storage blocked */ }
});
const toggleCollapsed = () => {
  collapsed.value = !collapsed.value;
  try { localStorage.setItem(COLLAPSE_KEY, collapsed.value ? "1" : "0"); } catch { /* storage blocked */ }
};
// Ctrl/Cmd + B toggles, like most editors
const onKey = (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "b") {
    const t = e.target as HTMLElement;
    if (t?.closest?.("input, textarea, [contenteditable]")) return;
    e.preventDefault();
    toggleCollapsed();
  }
};
onMounted(() => window.addEventListener("keydown", onKey));
onUnmounted(() => window.removeEventListener("keydown", onKey));

const showNotif = ref(false);

// Mobile drawer
const mobileOpen = ref(false);
const nav = (k: string) => {
  mobileOpen.value = false;
  emit("nav", k);
};
</script>

<template>
  <div class="shell" :class="{ collapsed }">
    <a href="#main" class="skip">Skip to content</a>
    <!-- Mobile top bar -->
    <div class="mtop">
      <button class="burger" aria-label="Open menu" :aria-expanded="mobileOpen" @click="mobileOpen = true">
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
        <div class="side-brand">
          <div style="font-size: 14px; font-weight: 800; letter-spacing: -.3px; color: #fff">
            {{ appTitle }}
          </div>
          <div style="font-size: 8.5px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 1px">
            {{ appSub }}
          </div>
        </div>
        <button class="side-close" aria-label="Close menu" @click="mobileOpen = false"><UiIcon name="x" :size="16" /></button>
      </div>
      <button
        class="collapse-btn" :aria-label="collapsed ? 'Expand sidebar' : 'Collapse sidebar'" :aria-expanded="!collapsed"
        :title="(collapsed ? 'Expand' : 'Collapse') + ' sidebar (Ctrl+B)'" @click="toggleCollapsed"
      >
        <UiIcon :name="collapsed ? 'chevRight' : 'chevLeft'" :size="14" />
      </button>

      <button class="back-btn" :title="collapsed ? 'Interdec Portal' : undefined" :aria-label="collapsed ? 'Interdec Portal' : undefined" @click="emit('portal')">
        <UiIcon name="back" :size="13" /> <span class="txt">Interdec Portal</span>
      </button>

      <nav class="side-nav" :aria-label="`${appTitle} navigation`">
        <button
          v-for="item in navItems"
          :key="item.k"
          class="nav-btn"
          :style="page === item.k ? { background: '#334155', color: '#fff' } : {}"
          :aria-current="page === item.k ? 'page' : undefined"
          :title="collapsed ? item.label : undefined"
          :aria-label="collapsed ? item.label : undefined"
          @click="nav(item.k)"
        >
          <UiIcon :name="item.icon" :size="16" />
          <span class="txt">{{ item.label }}</span>
        </button>
      </nav>

      <div class="side-foot">
        <div class="user-row">
          <div class="user-avatar" :style="{ background: (roleColors[role] || '#64748b') + '20', color: roleColors[role] }">
            {{ user.avatar || user.name.slice(0, 2).toUpperCase() }}
          </div>
          <div class="user-meta" style="flex: 1; min-width: 0">
            <div class="user-name">{{ user.name }}</div>
            <div class="user-role" :style="{ color: roleColors[role] }">{{ roleLabels[role] }}</div>
          </div>
          <UiNotificationBell class="side-bellbtn" dark />
          <button class="mail-btn" title="Email notifications" aria-label="Email notifications" @click="showNotif = true"><UiIcon name="mail" :size="14" /></button>
        </div>
        <button class="logout-btn collapse-row" :title="collapsed ? 'Expand sidebar (Ctrl+B)' : 'Collapse sidebar (Ctrl+B)'" :aria-label="collapsed ? 'Expand sidebar' : undefined" :aria-expanded="!collapsed" @click="toggleCollapsed">
          <UiIcon name="panel" :size="13" /> <span class="txt">Collapse sidebar</span>
        </button>
        <button class="logout-btn" :title="collapsed ? 'Sign Out' : undefined" :aria-label="collapsed ? 'Sign Out' : undefined" @click="logout"><UiIcon name="logout" :size="13" /> <span class="txt">Sign Out</span></button>
      </div>
    </aside>
    <NotifPrefsModal v-if="showNotif" @close="showNotif = false" />

    <!-- Content -->
    <main id="main" class="content" tabindex="-1">
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
.nav-btn[style*="background"] { box-shadow: inset 3px 0 0 #60a5fa; }
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
  display: flex; align-items: center; justify-content: center; gap: 6px;
  width: 100%; padding: 6px; border-radius: 6px; border: 1px solid #334155; background: transparent;
  color: #94a3b8; cursor: pointer; font-family: inherit; font-size: 11px; font-weight: 600; transition: all .15s;
}
.logout-btn:hover { background: #334155; color: #fff; }
.content { flex: 1; min-width: 0; }
.side-bell { padding: 8px 12px 0; }
.side-close { display: none; }
.side { transition: width .2s ease; position: sticky; }
.collapse-btn {
  position: absolute; top: 20px; right: -11px; z-index: 5; width: 22px; height: 22px; border-radius: 50%;
  border: 1px solid #cbd5e1; background: #fff; color: #334155; cursor: pointer; display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 6px rgba(15,23,42,.15); transition: background .15s, color .15s;
}
.collapse-btn { opacity: 1; }
.collapse-btn:hover { background: #eff6ff; color: #2563eb; border-color: #93c5fd; }
/* icon rail */
.collapsed .side { width: 64px; }
.collapsed .side-head { justify-content: center; padding: 16px 0; }
.collapsed .side-brand, .collapsed .txt, .collapsed .user-meta { display: none; }
.collapsed .back-btn { margin: 10px 10px 4px; width: calc(100% - 20px); padding: 8px 0; }
.collapsed .side-nav { padding: 10px; }
.collapsed .nav-btn { justify-content: center; padding: 10px 0; }
.collapsed .side-foot { padding: 12px 10px; }
.collapsed .user-row { flex-direction: column; justify-content: center; gap: 8px; }
.collapsed .logout-btn { padding: 8px 0; }
.mail-btn { width: 28px; height: 28px; border-radius: 7px; border: 1px solid #334155; background: transparent; color: #94a3b8; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.mail-btn:hover { background: #334155; color: #fff; }
.collapse-row { margin-bottom: 6px; border-style: dashed; }

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
  .side, .collapsed .side {
    position: fixed; left: 0; top: 0; bottom: 0; z-index: 60; transform: translateX(-100%);
    transition: transform .25s ease; width: 240px;
  }
  .collapse-btn, .collapse-row { display: none; }
  .collapsed .side-brand, .collapsed .txt, .collapsed .user-meta { display: revert; }
  .collapsed .user-row { flex-direction: row; gap: 8px; }
  .collapsed .side-head { justify-content: flex-start; padding: 16px 14px; }
  .collapsed .nav-btn { justify-content: flex-start; padding: 9px 11px; }
  .side.open { transform: none; box-shadow: 24px 0 60px rgba(0,0,0,.45); }
  .backdrop { display: block; position: fixed; inset: 0; background: rgba(15,23,42,.55); z-index: 50; }
  .side-close {
    display: block; margin-left: auto; background: none; border: none; color: #94a3b8;
    font-size: 14px; cursor: pointer; padding: 2px 4px;
  }
}
</style>
