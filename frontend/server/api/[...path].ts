// Catch-all API proxy: forwards /api/** to the FastAPI backend.
// Target comes from runtimeConfig.apiTarget (env override: NUXT_API_TARGET).
export default defineEventHandler(async (event) => {
  const API_TARGET = String(useRuntimeConfig(event).apiTarget || "http://127.0.0.1:8100").replace(/\/+$/, "");
  const path = event.node.req.url || event.path;
  // only ever forward API paths (never an absolute URL smuggled into the path)
  if (!path.startsWith("/api/")) {
    throw createError({ statusCode: 404, statusMessage: "Not found" });
  }
  try {
    return await proxyRequest(event, `${API_TARGET}${path}`);
  } catch (e: any) {
    console.error("[api-proxy] backend unreachable:", e?.message);
    throw createError({ statusCode: 502, statusMessage: "API server is not reachable. Is the backend running on port 8100?" });
  }
});
