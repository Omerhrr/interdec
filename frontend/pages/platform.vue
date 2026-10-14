<script setup lang="ts">
// Platform shell. Every screen has a real URL, so Back, refresh, bookmarks and
// shared links all work:
//   /platform                                 portal
//   /platform/importflow/<page>[/<id>]        dashboard | vendors | shippers | projects | shipments | reports
//   /platform/quotes[/new | /<id>[/edit] | /rates | /design]
//   /platform/catalogues   /platform/facade   /platform/users
// One instance of this page serves them all (no remount, data stays loaded).
definePageMeta({ key: "platform" });
const route = useRoute();
const router = useRouter();
const { user, fetchMe } = useAuth();
const { loadAll, loadUsers } = useData();
const { request } = useApi();
const ready = ref(false);

const IF_PAGES = ["dashboard", "vendors", "shippers", "projects", "shipments", "agents", "reports", "import", "design"];
const slug = computed<string[]>(() => {
  const s = route.params.slug;
  return (Array.isArray(s) ? s : s ? [s] : []).filter(Boolean) as string[];
});
// view: null = portal | importflow | facade | catalogues | admin | quotes
const view = computed<string | null>(() => {
  const a = slug.value[0];
  if (!a) return null;
  if (a === "users") return "admin";
  return ["importflow", "quotes", "catalogues", "facade"].includes(a) ? a : null;
});
const page = computed(() => {
  if (view.value === "importflow") return IF_PAGES.includes(slug.value[1]) ? slug.value[1] : "dashboard";
  if (view.value === "quotes") return ["rates", "design"].includes(slug.value[1]) ? slug.value[1] : "quotes";
  return "vendors";
});
const detailId = computed(() => (view.value === "importflow" && slug.value[2]) || null);
const detail = computed(() => (detailId.value ? "detail" : null));
// quotes sub-view: list | new | detail | edit
const quoteRoute = computed(() => {
  const [, a, b] = slug.value;
  if (!a || a === "rates" || a === "design") return { view: "list", id: null as string | null };
  if (a === "new") return { view: "new", id: null };
  return { view: b === "edit" ? "edit" : "detail", id: a };
});

// Access guard: a URL for an app you can't use sends you to the portal
const canOpen = (v: string | null) => {
  const u = user.value as any;
  if (!u || !v) return true;
  const has = (k: string) => !!u.apps?.[k]?.access;
  const admin = u.platformRole === "admin";
  if (v === "admin" || v === "facade") return admin;
  if (v === "quotes") return admin || has("quotes") || has("facade");
  if (v === "importflow") return admin || has("importflow");
  if (v === "catalogues") return admin || has("catalogues");
  return true;
};
watch([view, user], () => {
  if (ready.value && !canOpen(view.value)) {
    notify("You don't have access to that app", "error");
    router.replace("/platform");
  }
});

onMounted(async () => {
  const u = await fetchMe();
  if (!u) {
    // come back here after signing in
    navigateTo({ path: "/", query: route.fullPath !== "/platform" ? { next: route.fullPath } : {} });
    return;
  }
  await loadAll();
  if (u.platformRole === "admin") loadUsers();
  ready.value = true;
  if (!canOpen(view.value)) router.replace("/platform");
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

// Facade messages: return-to-portal button, the SSO handshake where an
// embedded facade without a session asks for the signed-in platform user,
// the legacy-to-native quote migration bridge, and open-quotes shortcut
const onFacadeMsg = async (e: MessageEvent) => {
  // Only trust messages from our own embedded facade iframe. Without this, any
  // page that framed or opened the portal could trigger a quote migration as
  // the signed-in user or request their SSO identity.
  if (e.origin !== window.location.origin) return;
  if (!facadeFrame.value || e.source !== facadeFrame.value.contentWindow) return;
  const d: any = e.data;
  const t = d?.type;
  if (t === "idf-portal") goPortal();
  else if (t === "idf-sso-request") pushFacadeSSO();
  else if (t === "idf-open-quotes") openApp("quotes");
  else if (t === "idf-migrate") await runFacadeMigration(d.payload);
};

// Migration: the facade hands over its localStorage dataset; the server
// imports it into the native quotes tables, then we tell the facade the result.
const migrating = ref(false);
const runFacadeMigration = async (payload: any) => {
  if (migrating.value || !payload) return;
  migrating.value = true;
  try {
    const res: any = await request("/api/quotes/migrate", { method: "POST", body: payload });
    facadeFrame.value?.contentWindow?.postMessage({ type: "idf-migrate-done", result: res }, window.location.origin);
    const n = res?.imported || 0;
    const s = res?.skipped || 0;
    if (n || s) {
      notify(`Migration complete: ${n} quote(s) imported${s ? `, ${s} already existed (skipped)` : ""}`);
    } else {
      notify("Nothing to migrate - no quotes found in the legacy app");
    }
  } catch (err: any) {
    notify(err?.message || "Migration failed", "error");
  } finally {
    migrating.value = false;
  }
};

onMounted(() => window.addEventListener("message", onFacadeMsg));
onUnmounted(() => window.removeEventListener("message", onFacadeMsg));

const goPortal = () => router.push("/platform");
const openApp = (app: string) => router.push(app === "admin" ? "/platform/users" : `/platform/${app}`);

// In-app navigation keeps the signature the pages already use: (page, 'detail'|null, id)
const navigate = (p: string, d: string | null = null, id: string | null = null) => {
  if (view.value === "quotes") return router.push(["rates", "design"].includes(p) ? `/platform/quotes/${p}` : "/platform/quotes");
  if (view.value === "catalogues") return;
  router.push(`/platform/importflow/${p}${d && id ? `/${id}` : ""}`);
};

// Toasts: success fades after 5s (10s when it offers Undo); errors stay until closed
type Toast = { id: number; m: string; t: string; action?: { label: string; fn: () => void } };
const toasts = ref<Toast[]>([]);
let toastSeq = 0;
const dismiss = (id: number) => (toasts.value = toasts.value.filter((x) => x.id !== id));
const notify = (m: string, t = "success", opts: { action?: Toast["action"] } = {}) => {
  const id = ++toastSeq;
  toasts.value = [...toasts.value.slice(-2), { id, m, t, action: opts.action }];
  if (t !== "error") setTimeout(() => dismiss(id), opts.action ? 10000 : 5000);
};
const runToastAction = (x: Toast) => {
  dismiss(x.id);
  x.action?.fn();
};
provide("notify", notify);

// Switching app, page or record starts at the top. Previously the old scroll
// position carried over, so you landed mid-page with the title hidden.
watch(() => route.path, () => {
  if (import.meta.client) window.scrollTo({ top: 0 });
});
// tab title names the screen (useful with several tabs, history and screen readers)
const TITLES: Record<string, string> = { dashboard: "Dashboard", vendors: "Vendors", shippers: "Shippers", projects: "Projects", shipments: "Shipments", reports: "Reports", rates: "Rate Card", design: "PDF Design", quotes: "Quotations" };
const IF_TITLES: Record<string, string> = { design: "Document Design", agents: "Clearing Agents", import: "Import data" };
useHead({
  title: computed(() => {
    const v = view.value;
    const t = !v ? "Portal" : v === "admin" ? "Users" : v === "facade" ? "Legacy archive" : v === "catalogues" ? "Catalogues" : (v === "importflow" && IF_TITLES[page.value]) || TITLES[page.value];
    return `${t} · Interdec`;
  }),
});
provide("navigate", navigate);
</script>

<template>
  <div v-if="!ready" class="boot" aria-busy="true">
    <div class="spinner" role="status"><span class="sr-only">Loading Interdec Platform</span></div>
  </div>

  <div v-else-if="user" style="min-height: 100vh">
    <!-- App Selector -->
    <AppSelector v-if="!view" :user="user" @open="openApp" @admin="openApp('admin')" />

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
      <IfClearingAgents v-else-if="page === 'agents'" />
      <IfProjects v-else-if="page === 'projects'" :detail="detail" :detail-id="detailId" @navigate="navigate" />
      <IfShipments v-else-if="page === 'shipments'" :detail="detail" :detail-id="detailId" @navigate="navigate" />
      <IfReports v-else-if="page === 'reports'" />
      <IfDocDesign v-else-if="page === 'design'" />
      <IfImportData v-else-if="page === 'import'" />
    </IfShell>

    <!-- Quotations (native pricing engine) -->
    <IfShell
      v-else-if="view === 'quotes'"
      :user="user"
      quotes-mode
      :page="page"
      @portal="goPortal"
      @nav="navigate($event)"
    >
      <QuoteQuotes v-if="page === 'quotes'" :route-view="quoteRoute.view" :route-id="quoteRoute.id" />
      <QuoteRateCard v-else-if="page === 'rates'" />
      <QuotePdfDesign v-else-if="page === 'design'" />
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

    <UiConfirmHost />

    <!-- Forced password change (demo / admin-set passwords) -->
    <ChangePasswordModal v-if="user.mustChangePassword" forced />

    <!-- Toast -->
    <div class="toast-stack" role="status" aria-live="polite">
      <div v-for="x in toasts" :key="x.id" class="toast" :class="x.t">
        <UiIcon class="t-ic" :name="x.t === 'error' ? 'alert' : 'check'" />
        <span style="flex: 1">{{ x.m }}</span>
        <button v-if="x.action" class="toast-act" @click="runToastAction(x)">{{ x.action.label }}</button>
        <button class="toast-x" aria-label="Dismiss" @click="dismiss(x.id)"><UiIcon name="x" :size="14" /></button>
      </div>
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
