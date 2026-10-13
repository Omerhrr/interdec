export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: false },
  ssr: false, // pure SPA like the original
  app: {
    head: {
      title: "Interdec Platform",
      htmlAttrs: { lang: "en" },
      meta: [
        { charset: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1.0" },
      ],
      // DM Sans was declared in CSS but never loaded, so every OS showed a different font
      link: [
        { rel: "preconnect", href: "https://fonts.googleapis.com" },
        { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: "" },
        { rel: "stylesheet", href: "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700;9..40,800&family=JetBrains+Mono:wght@500;700&display=swap" },
      ],
    },
  },
  css: ["~/assets/css/main.css"],
  runtimeConfig: {
    // server-only: where the /api proxy forwards to (override: NUXT_API_TARGET)
    apiTarget: "http://127.0.0.1:8100",
    public: {
      // empty = same-origin; server/api/[...path].ts proxies /api -> FastAPI :8100
      apiBase: "",
    },
  },
});
