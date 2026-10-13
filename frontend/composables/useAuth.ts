// Auth state - token cookie + current user
export interface AppAccess { access: boolean; role?: string }
export interface PlatformUser {
  id: string;
  name: string;
  email: string;
  avatar: string;
  platformRole: "admin" | "user";
  apps: { facade?: AppAccess; importflow?: AppAccess; catalogues?: AppAccess; quotes?: AppAccess };
  active: boolean;
  mustChangePassword?: boolean;
}

export const useAuth = () => {
  const token = useCookie<string | null>("interdec_token", { maxAge: 60 * 60 * 24 * 7 });
  const user = useState<PlatformUser | null>("auth_user", () => null);

  const { request } = useApi();

  const login = async (email: string, password: string) => {
    const res = await request<{ access_token: string; user: PlatformUser }>("/api/auth/login", {
      method: "POST",
      body: { email, password },
      // a 401 here means wrong credentials, not an expired session: let the
      // login form show the message instead of reloading the page
      keepAuthOn401: true,
    });
    token.value = res.access_token;
    user.value = res.user;
    return res.user;
  };

  const fetchMe = async () => {
    if (!token.value) return null;
    try {
      user.value = await request<PlatformUser>("/api/auth/me");
      return user.value;
    } catch {
      return null;
    }
  };

  const logout = () => {
    token.value = null;
    user.value = null;
    if (import.meta.client) window.location.href = "/";
  };

  const importflowRole = computed<string>(() => {
    if (user.value?.platformRole === "admin") return "admin";
    const flow = user.value?.apps?.importflow;
    return flow?.access ? flow.role || "viewer" : "viewer";
  });

  return { token, user, login, fetchMe, logout, importflowRole };
};
