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

  const { request } = useApi();

  const loadAll = async () => {
    try {
      const [v, s, p, sh] = await Promise.all([
        request<any[]>("/api/vendors"),
        request<any[]>("/api/shippers"),
        request<any[]>("/api/projects"),
        request<any[]>("/api/shipments"),
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

  const loadUsers = async () => {
    try {
      users.value = await request<any[]>("/api/users");
    } catch (e) {
      console.error("Failed to load users:", e);
    }
  };

  const loadActivity = async (limit = 12) => {
    try {
      activity.value = await request<any[]>(`/api/activity?limit=${limit}`);
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
    notifications, unread, activity,
    loadAll, loadUsers, loadActivity, loadNotifications, markAllRead, timeAgo,
    vendorName, shipperName, projectName, company,
  };
};
