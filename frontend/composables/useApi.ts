// API client - wraps $fetch with auth header + error handling
export const useApi = () => {
  const config = useRuntimeConfig();
  const token = useCookie<string | null>("interdec_token");

  const request = async <T = any>(path: string, opts: any = {}): Promise<T> => {
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
      const d = e?.data?.detail;
      // FastAPI validation errors arrive as an array of {msg, loc}
      const msg = Array.isArray(d)
        ? d.map((x: any) => x?.msg || String(x)).join("; ")
        : d || e?.message || "Request failed";
      // A 401 normally means the session expired, but endpoints like
      // change-password return 401 for validation (wrong current password).
      // Callers can pass keepAuthOn401 to handle the error inline instead
      // of being logged out.
      if (e?.status === 401 && !keepAuthOn401) {
        token.value = null;
        if (import.meta.client && !window.location.pathname.includes("__nuxt_error")) {
          const here = window.location.pathname + window.location.search;
          window.location.href = here.startsWith("/platform") ? `/?next=${encodeURIComponent(here)}` : "/";
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
    try {
      const res = await $fetch.raw(path, {
        baseURL: config.public.apiBase as string,
        headers,
        responseType: "blob",
      });
      const cd = (res.headers.get("content-disposition") || "") as string;
      const star = cd.match(/filename\*=UTF-8''([^;]+)/i);
      const plain = cd.match(/filename="?([^";]+)"?/);
      let filename = plain?.[1] || "export.xlsx";
      if (star?.[1]) {
        try { filename = decodeURIComponent(star[1]); } catch { /* keep plain */ }
      }
      return { blob: res._data as Blob, filename };
    } catch (e: any) {
      // blob error bodies hide the API's {detail}; surface it
      let msg = e?.message || "Download failed";
      try {
        const body = e?.data instanceof Blob ? JSON.parse(await e.data.text()) : e?.data;
        if (body?.detail) msg = body.detail;
      } catch { /* not JSON */ }
      if (e?.status === 401) {
        token.value = null;
        if (import.meta.client) window.location.href = "/";
      }
      throw new Error(msg);
    }
  };

  // Save a Blob to disk via a temporary link
  const saveBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 200);
  };

  return { request, download, saveBlob };
};
