// Central data store — vendors/shippers/projects/shipments (loaded from FastAPI)
export const useData = () => {
  const vendors = useState<any[]>("vendors", () => []);
  const shippers = useState<any[]>("shippers", () => []);
  const projects = useState<any[]>("projects", () => []);
  const shipments = useState<any[]>("shipments", () => []);
  const users = useState<any[]>("platform_users", () => []);
  const loaded = useState<boolean>("data_loaded", () => false);

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

  const vendorName = (id?: string | null) => vendors.value.find((v) => v.id === id)?.name || "—";
  const shipperName = (id?: string | null) => shippers.value.find((s) => s.id === id)?.name || "—";
  const projectName = (id?: string | null) =>
    id ? projects.value.find((p) => p.id === id)?.name || "—" : "General Stock";
  const company = (id?: string | null) => COMPANIES.find((c) => c.id === id);

  return {
    vendors, shippers, projects, shipments, users, loaded,
    loadAll, loadUsers, vendorName, shipperName, projectName, company,
  };
};
