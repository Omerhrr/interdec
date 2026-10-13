<script setup lang="ts">
// Upload dropzone - mirrors original _l component
const props = defineProps<{ label: string; multiple?: boolean; accept?: string }>();
const emit = defineEmits<{ (e: "files", f: File[]): void }>();
const drag = ref(false);
const inputRef = ref<HTMLInputElement>();

const pick = () => inputRef.value?.click();

const onDrop = (e: DragEvent) => {
  drag.value = false;
  const files = Array.from(e.dataTransfer?.files || []);
  if (files.length) emit("files", files);
};
const onChange = (e: Event) => {
  const files = Array.from((e.target as HTMLInputElement).files || []);
  if (files.length) emit("files", files);
  if (inputRef.value) inputRef.value.value = "";
};
</script>

<template>
  <div
    :style="{
      border: `1.5px dashed ${drag ? '#93c5fd' : '#e2e8f0'}`,
      borderRadius: '9px', padding: '18px 14px', textAlign: 'center', cursor: 'pointer',
      background: drag ? '#eff6ff' : '#f8fafc', transition: 'all .15s',
    }"
    role="button" tabindex="0" :aria-label="label"
    @click="pick" @keydown.enter.prevent="pick" @keydown.space.prevent="pick"
    @dragover.prevent="drag = true"
    @dragleave="drag = false"
    @drop.prevent="onDrop"
  >
    <UiIcon name="upload" :size="20" style="color: #2563eb; margin-bottom: 4px" />
    <div style="font-size: 12px; font-weight: 700; color: #334155">{{ label }}</div>
    <div style="font-size: 10px; color: #64748b; margin-top: 2px">Click or drag &amp; drop</div>
    <input ref="inputRef" type="file" :multiple="multiple" :accept="accept" style="display: none" @change="onChange" />
  </div>
</template>
