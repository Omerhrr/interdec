<script setup lang="ts">
// File chip - mirrors original Md component (file display w/ download)
const props = defineProps<{ file: any; color?: string; kind?: string; fileId?: string }>();
const { fmtSize } = useConstants();
const { request } = useApi();
const notify = inject<(m: string, t?: string) => void>("notify", () => {});

// Demo records carry metadata only (no stored bytes)
const hasData = computed(() => props.file?.hasData !== false);

const downloading = ref(false);
const fetchBlob = async () =>
  request<Blob>(`/api/shipments/${props.fileId}/files/${props.kind}`, { responseType: "blob" });

const download = async () => {
  if (!props.kind || !props.fileId) return;
  downloading.value = true;
  try {
    const res = await fetchBlob();
    const url = URL.createObjectURL(res);
    const a = document.createElement("a");
    a.href = url;
    a.download = props.file?.name || "document";
    a.target = "_blank";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 200);
  } catch (e: any) {
    notify(e?.message || "Download failed", "error");
  } finally {
    downloading.value = false;
  }
};

const view = async () => {
  if (!props.kind || !props.fileId) return;
  // open the tab synchronously (popup blockers reject window.open after an await)
  const win = window.open("", "_blank");
  downloading.value = true;
  try {
    const res = await fetchBlob();
    const url = URL.createObjectURL(res);
    if (win) win.location.href = url;
    else window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e: any) {
    win?.close();
    notify(e?.message || "Could not open file", "error");
  } finally {
    downloading.value = false;
  }
};
</script>

<template>
  <div
    :style="{
      display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px',
      background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px',
    }"
  >
    <UiIcon name="file" :size="18" style="color: #64748b" />
    <div style="flex: 1; min-width: 0">
      <div style="font-size: 11.5px; font-weight: 700; color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
        {{ file?.name || "document" }}
      </div>
      <div style="font-size: 9.5px; color: #64748b">{{ fmtSize(file?.size) }}</div>
    </div>
    <span v-if="!hasData" style="font-size: 9.5px; color: #64748b">demo record</span>
    <button v-if="hasData" class="btn btn-ghost btn-sm" :aria-label="`View ${file?.name || 'file'}`" :disabled="downloading" @click="view"><UiIcon name="eye" :size="14" /></button>
    <button v-if="hasData" class="btn btn-ghost btn-sm" :aria-label="`Download ${file?.name || 'file'}`" :disabled="downloading" @click="download">
      <UiIcon name="download" :size="14" />
    </button>
  </div>
</template>
