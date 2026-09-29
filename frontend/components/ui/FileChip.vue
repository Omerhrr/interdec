<script setup lang="ts">
// File chip - mirrors original Md component (file display w/ download)
const props = defineProps<{ file: any; color?: string; kind?: string; fileId?: string }>();
const { fmtSize } = useConstants();
const { request } = useApi();

const downloading = ref(false);
const download = async () => {
  if (!props.kind || !props.fileId) return;
  downloading.value = true;
  try {
    const res = await request<Blob>(`/api/shipments/${props.fileId}/files/${props.kind}`, { responseType: "blob" });
    const url = URL.createObjectURL(res);
    const a = document.createElement("a");
    a.href = url;
    a.download = props.file?.name || "document";
    a.target = "_blank";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 200);
  } finally {
    downloading.value = false;
  }
};

const view = async () => {
  if (!props.kind || !props.fileId) return;
  downloading.value = true;
  try {
    const res = await request<Blob>(`/api/shipments/${props.fileId}/files/${props.kind}`, { responseType: "blob" });
    const url = URL.createObjectURL(res);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  } finally {
    downloading.value = false;
  }
};
</script>

<template>
  <div
    :style="{
      display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
      background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8,
    }"
  >
    <span style="font-size: 16px">📄</span>
    <div style="flex: 1; min-width: 0">
      <div style="font-size: 11.5px; font-weight: 700; color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
        {{ file?.name || "document" }}
      </div>
      <div style="font-size: 9.5px; color: #94a3b8">{{ fmtSize(file?.size) }}</div>
    </div>
    <button class="btn btn-ghost btn-sm" style="font-size: 10px" @click="view">View</button>
    <button class="btn btn-ghost btn-sm" style="font-size: 10px" :disabled="downloading" @click="download">
      {{ downloading ? "…" : "↓" }}
    </button>
  </div>
</template>
