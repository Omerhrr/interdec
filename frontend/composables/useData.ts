// Central data store - vendors/shippers/projects/shipments (loaded from FastAPI)
export const useData = () => {
  const vendors = useState<any[]>("vendors", () => []);
  const shippers = useState<any[]>("shippers", () => []);
  const projects = useState<any[]>("projects", () => []);
  const shipments = useState<any[]>("shipments", () => []);
  const users = useState<any[]>("platform_users", () => []);
  const loaded = useState<boolean>("data_loaded", () => false);
  const notifications = useState<any[]>("notifications", () => []);
  const unread = useState<number>("unread_count", () => 0);
  const activity = useState<any[]>("activity_feed", () => []);
  // Exchange rates to USD, stored on the server with who/when changed them
  const fx = useState<{ rates: Record<string, number>; updated: number; updatedBy: string; isDefault: boolean }>(
    "fx_rates", () => ({ rates: { ...DEFAULT_RATES }, updated: 0, updatedBy: "", isDefault: true })
  );

  const { request } = useApi();

  const loadAll = async () => {
    try {
      const [v, s, p, sh] = await Promise.all([
        request<any[]>("/api/vendors"),
        request<any[]>("/api/shippers"),
        request<any[]>("/api/projects"),
        request<any[]>("/api/shipments"),
        loadFx(),
      ]);
      vendors.value = v;
      shippers.value = s;
      projects.value = p;
      shipments.value = sh;
      loaded.value = true;
    } catch (e) {
      console.error("Failed to load data:", e);
    }
  };

  const loadFx = async () => {
    try {
      fx.value = await request("/api/settings/fx");
    } catch {
      /* keep defaults */
    }
  };
  const saveFx = async (rates: Record<string, number>) => {
    fx.value = await request("/api/settings/fx", { method: "PUT", body: { rates } });
  };
  const toUsd = (s: any) => (Number(s?.value) || 0) * (fx.value.rates[s?.currency] ?? 1);
  const fxLabel = computed(() =>
    fx.value.isDefault || !fx.value.updated
      ? "default rates"
      : `rates of ${fmtDate(fx.value.updated)}${fx.value.updatedBy ? ` (${fx.value.updatedBy})` : ""}`
  );

  const loadUsers = async () => {
    try {
      users.value = await request<any[]>("/api/users");
    } catch (e) {
      console.error("Failed to load users:", e);
    }
  };

  const loadActivity = async (limit = 12, includeAuth = false) => {
    try {
      activity.value = await request<any[]>(`/api/activity?limit=${limit}${includeAuth ? "&include_auth=true" : ""}`);
    } catch {
      /* activity feed is non-critical */
    }
  };

  const loadNotifications = async () => {
    try {
      notifications.value = await request<any[]>("/api/notifications");
      unread.value = notifications.value.filter((n) => !n.read).length;
    } catch {
      /* notifications are non-critical */
    }
  };

  const markAllRead = async () => {
    try {
      await request("/api/notifications/read-all", { method: "POST" });
      notifications.value = notifications.value.map((n) => ({ ...n, read: true }));
      unread.value = 0;
    } catch {
      /* ignore */
    }
  };

  const timeAgo = (ts: number) => {
    if (!ts) return "";
    const s = Math.floor((Date.now() - ts) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s / 60) + "m ago";
    if (s < 86400) return Math.floor(s / 3600) + "h ago";
    if (s < 604800) return Math.floor(s / 86400) + "d ago";
    return fmtDate(ts);
  };

  const vendorName = (id?: string | null) => vendors.value.find((v) => v.id === id)?.name || "N/A";
  const shipperName = (id?: string | null) => shippers.value.find((s) => s.id === id)?.name || "N/A";
  const projectName = (id?: string | null) =>
    id ? projects.value.find((p) => p.id === id)?.name || "N/A" : "General Stock";
  const company = (id?: string | null) => COMPANIES.find((c) => c.id === id);

  return {
    vendors, shippers, projects, shipments, users, loaded,
    notifications, unread, activity, fx, fxLabel, toUsd,
    loadAll, loadUsers, loadFx, saveFx, loadActivity, loadNotifications, markAllRead, timeAgo,
    vendorName, shipperName, projectName, company,
  };
};
