export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: false },
  ssr: false, // pure SPA like the original
  app: {
    head: {
      title: "Interdec Platform",
      meta: [
        { charset: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1.0" },
      ],
      link: [{ rel: "preconnect", href: "https://fonts.googleapis.com" }],
    },
  },
  css: ["~/assets/css/main.css"],
  runtimeConfig: {
    public: {
      // empty = same-origin; server/api/[...path].ts proxies /api -> FastAPI :8100
      apiBase: "",
    },
  },
});
