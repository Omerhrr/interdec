// API client - wraps $fetch with auth header + error handling
export const useApi = () => {
  const config = useRuntimeConfig();
  const token = useCookie<string | null>("interdec_token");

  const request = async <T>(path: string, opts: any = {}): Promise<T> => {
    const { keepAuthOn401, ...rest } = opts;
    const headers: Record<string, string> = { ...(rest.headers || {}) };
    if (token.value) headers.Authorization = `Bearer ${token.value}`;
    try {
      return await $fetch<T>(path, {
        baseURL: config.public.apiBase as string,
        ...rest,
        headers,
      });
    } catch (e: any) {
      const msg = e?.data?.detail || e?.message || "Request failed";
      // A 401 normally means the session expired, but endpoints like
      // change-password return 401 for validation (wrong current password).
      // Callers can pass keepAuthOn401 to handle the error inline instead
      // of being logged out.
      if (e?.status === 401 && !keepAuthOn401) {
        token.value = null;
        if (import.meta.client && !window.location.pathname.includes("__nuxt_error")) {
          window.location.href = "/";
        }
      }
      throw new Error(msg);
    }
  };

  // Binary download (Excel exports etc.): fetch raw with the auth header and
  // hand back the blob + filename from Content-Disposition.
  const download = async (path: string): Promise<{ blob: Blob; filename: string }> => {
    const headers: Record<string, string> = {};
    if (token.value) headers.Authorization = `Bearer ${token.value}`;
    const res = await $fetch.raw(path, {
      baseURL: config.public.apiBase as string,
      headers,
      responseType: "blob",
    });
    const cd = (res.headers.get("content-disposition") || "") as string;
    const m = cd.match(/filename="?([^";]+)"?/);
    return { blob: res._data as Blob, filename: m?.[1] || "export.xlsx" };
  };

  return { request, download };
};
