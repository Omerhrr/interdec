// Catch-all API proxy: forwards /api/** to the FastAPI backend (:8100)
export default defineEventHandler(async (event) => {
  const path = event.node.req.url || event.path;
  const target = `http://localhost:8100${path}`;
  console.log("[api-proxy]", event.method, path, "->", target);
  try {
    const res = await proxyRequest(event, target);
    return res;
  } catch (e: any) {
    console.error("[api-proxy] error", e?.message);
    throw e;
  }
});
