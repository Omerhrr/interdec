<script setup lang="ts">
const props = defineProps<{ status: string }>();
const { STATUS_LABELS, STATUS_COLORS } = useConstants();
</script>

<template>
  <span class="chip" :style="{ background: STATUS_COLORS[status] + '18', color: STATUS_COLORS[status] }">
    <span style="width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block"></span>
    {{ STATUS_LABELS[status] || status }}
  </span>
</template>
