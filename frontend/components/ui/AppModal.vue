<script setup lang="ts">
defineProps<{ open: boolean; title: string; width?: number }>();
const emit = defineEmits<{ (e: "close"): void }>();
</script>

<template>
  <div v-if="open" class="modal-overlay" @click.self="emit('close')">
    <div class="modal-box" :style="{ maxWidth: (width || 520) + 'px' }">
      <div class="modal-head">
        <h3 style="font-size:15px;font-weight:800">{{ title }}</h3>
        <button class="btn btn-ghost btn-sm" style="font-size:16px;padding:4px 8px" @click="emit('close')">✕</button>
      </div>
      <div class="modal-body">
        <slot />
      </div>
    </div>
  </div>
</template>
