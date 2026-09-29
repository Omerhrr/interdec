// API client — wraps $fetch with auth header + error handling
export const useApi = () => {
  const config = useRuntimeConfig();
  const token = useCookie<string | null>("interdec_token");

  const request = async <T>(path: string, opts: any = {}): Promise<T> => {
    const headers: Record<string, string> = { ...(opts.headers || {}) };
    if (token.value) headers.Authorization = `Bearer ${token.value}`;
    try {
      return await $fetch<T>(path, {
        baseURL: config.public.apiBase as string,
        ...opts,
        headers,
      });
    } catch (e: any) {
      const msg = e?.data?.detail || e?.message || "Request failed";
      if (e?.status === 401) {
        token.value = null;
        if (import.meta.client && !window.location.pathname.includes("__nuxt_error")) {
          window.location.href = "/";
        }
      }
      throw new Error(msg);
    }
  };

  return { request };
};
