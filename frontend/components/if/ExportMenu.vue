<script setup lang="ts">
// "Export" button with PDF / Excel choices. Everything is built on the server
// (same data the page shows), styled by ImportFlow → Document Design.
const props = withDefaults(defineProps<{ kind: string; params?: Record<string, any>; label?: string; small?: boolean }>(), {
  params: () => ({}),
  label: "Export",
  small: true,
});
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { download, saveBlob } = useApi();
const open = ref(false);
const busy = ref<"" | "pdf" | "xlsx">("");
const wrap = ref<HTMLElement | null>(null);

const run = async (format: "pdf" | "xlsx") => {
  open.value = false;
  busy.value = format;
  try {
    const qs = new URLSearchParams({ format });
    for (const [k, v] of Object.entries(props.params)) if (v !== undefined && v !== null && v !== "" && v !== "All") qs.set(k, String(v));
    const { blob, filename } = await download(`/api/importflow/export/${props.kind}?${qs}`);
    saveBlob(blob, filename);
  } catch (e: any) {
    notify(e.message || "Export failed", "error");
  } finally {
    busy.value = "";
  }
};
const onDoc = (e: MouseEvent) => { if (wrap.value && !wrap.value.contains(e.target as Node)) open.value = false; };
const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") open.value = false; };
onMounted(() => { document.addEventListener("click", onDoc); document.addEventListener("keydown", onKey); });
onUnmounted(() => { document.removeEventListener("click", onDoc); document.removeEventListener("keydown", onKey); });
</script>

<template>
  <div ref="wrap" class="xm">
    <button
      class="btn btn-secondary" :class="{ 'btn-sm': small }" :disabled="!!busy" aria-haspopup="menu" :aria-expanded="open"
      @click.stop="open = !open"
    >
      <UiIcon name="download" :size="14" />
      {{ busy === "pdf" ? "Preparing PDF…" : busy === "xlsx" ? "Preparing Excel…" : label }}
    </button>
    <div v-if="open" class="xm-pop" role="menu">
      <button role="menuitem" class="xm-it" @click="run('pdf')"><UiIcon name="pdf" :size="15" /> <span><b>PDF</b><small>To share or print</small></span></button>
      <button role="menuitem" class="xm-it" @click="run('xlsx')"><UiIcon name="grid" :size="15" /> <span><b>Excel</b><small>To sort, filter or sum</small></span></button>
    </div>
  </div>
</template>

<style scoped>
.xm { position: relative; display: inline-block; }
.xm-pop {
  position: absolute; right: 0; top: calc(100% + 6px); z-index: 30; min-width: 200px; background: #fff;
  border: 1px solid #e2e8f0; border-radius: 10px; box-shadow: 0 12px 32px rgba(15,23,42,.14); padding: 5px;
}
.xm-it {
  display: flex; align-items: center; gap: 10px; width: 100%; padding: 8px 10px; border: none; background: none; border-radius: 7px;
  cursor: pointer; font: inherit; text-align: left; color: #0f172a;
}
.xm-it:hover, .xm-it:focus-visible { background: #f1f5f9; }
.xm-it span { display: flex; flex-direction: column; }
.xm-it b { font-size: 13px; }
.xm-it small { font-size: 11.5px; color: #64748b; }
</style>
