<script setup lang="ts">
// Platform shell - auth guard, app selector, app views (mirrors original WP() flow)
const { user, fetchMe } = useAuth();
const { loadAll, loadUsers, loaded } = useData();
const ready = ref(false);

// view: null = app selector | importflow | facade | catalogues | admin
const view = ref<string | null>(null);

// importflow internal page state
const page = ref("dashboard");
const detail = ref<string | null>(null); // 'detail' | null
const detailId = ref<string | null>(null);

onMounted(async () => {
  const u = await fetchMe();
  if (!u) {
    navigateTo("/");
    return;
  }
  await loadAll();
  if (u.platformRole === "admin") loadUsers();
  ready.value = true;
});

// Facade SSO - push the logged-in platform user into the facade app on iframe load
const facadeFrame = ref<HTMLIFrameElement | null>(null);
const pushFacadeSSO = () => {
  const u = user.value;
  if (!u || view.value !== "facade") return;
  try {
    facadeFrame.value?.contentWindow?.postMessage(
      {
        type: "idf-sso",
        user: {
          id: u.id,
          name: u.name,
          email: u.email,
          platformRole: u.platformRole,
          facadeRole: u.apps?.facade?.role,
        },
      },
      window.location.origin
    );
  } catch {
    /* facade falls back to its own login screen */
  }
};

// Facade messages: return-to-portal button, plus the SSO handshake where an
// embedded facade without a session asks for the signed-in platform user
const onFacadeMsg = (e: MessageEvent) => {
  const t = (e.data as any)?.type;
  if (t === "idf-portal") goPortal();
  else if (t === "idf-sso-request") pushFacadeSSO();
};
onMounted(() => window.addEventListener("message", onFacadeMsg));
onUnmounted(() => window.removeEventListener("message", onFacadeMsg));

const goPortal = () => {
  view.value = null;
  page.value = "dashboard";
  detail.value = null;
  detailId.value = null;
};

const openApp = (app: string) => {
  if (app === "catalogues") {
    view.value = "catalogues";
    page.value = "vendors";
  } else {
    view.value = app;
    page.value = "dashboard";
  }
  detail.value = null;
  detailId.value = null;
};

// ImportFlow navigation (mirrors Tn function)
const navigate = (p: string, d: string | null = null, id: string | null = null) => {
  page.value = p;
  detail.value = d;
  detailId.value = id;
};

const toast = ref<{ m: string; t: string } | null>(null);
let toastTimer: any = null;
const notify = (m: string, t = "success") => {
  toast.value = { m, t };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (toast.value = null), 2500);
};
provide("notify", notify);
provide("navigate", navigate);
</script>

<template>
  <div v-if="!ready" class="boot">
    <div class="spinner"></div>
  </div>

  <div v-else-if="user" style="min-height: 100vh">
    <!-- App Selector -->
    <AppSelector v-if="!view" :user="user" @open="openApp" @admin="view = 'admin'" />

    <!-- Facade (iframe) -->
    <div v-else-if="view === 'facade'" style="height: 100vh; background: #f0eee9">
      <iframe
        ref="facadeFrame"
        src="/facade.html"
        style="width: 100%; height: 100%; border: none"
        title="Facade Pricing"
        @load="pushFacadeSSO"
      ></iframe>
    </div>

    <!-- User Management (admin) -->
    <UsersAdmin v-else-if="view === 'admin'" :users="useData().users.value" @back="goPortal" @refresh="loadUsers()" />

    <!-- ImportFlow -->
    <IfShell
      v-else-if="view === 'importflow'"
      :user="user"
      :page="page"
      @portal="goPortal"
      @nav="navigate($event)"
    >
      <IfDashboard v-if="page === 'dashboard'" @navigate="navigate" />
      <IfVendors v-else-if="page === 'vendors'" />
      <IfShippers v-else-if="page === 'shippers'" />
      <IfProjects v-else-if="page === 'projects'" :detail="detail" :detail-id="detailId" @navigate="navigate" />
      <IfShipments v-else-if="page === 'shipments'" :detail="detail" :detail-id="detailId" @navigate="navigate" />
      <IfReports v-else-if="page === 'reports'" />
    </IfShell>

    <!-- Catalogues -->
    <IfShell
      v-else-if="view === 'catalogues'"
      :user="user"
      catalogues-mode
      page="vendors"
      @portal="goPortal"
      @nav="navigate($event)"
    >
      <IfVendors catalogues :readonly="user.platformRole !== 'admin'" />
    </IfShell>

    <!-- Toast -->
    <div v-if="toast" class="toast" :style="{ background: toast.t === 'error' ? '#ef4444' : '#10b981' }">
      {{ toast.m }}
    </div>
  </div>
</template>

<style scoped>
.boot {
  height: 100vh; display: flex; align-items: center; justify-content: center; background: #f8fafc;
}
.spinner {
  width: 34px; height: 34px; border-radius: 50%;
  border: 3px solid #e2e8f0; border-top-color: #3b82f6;
  animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
