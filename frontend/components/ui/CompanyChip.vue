<script setup lang="ts">
// Company chip: coloured dot + name (the 10px logo was unreadable and repeated the name)
import { COMPANIES } from "~/composables/useConstants";
const props = defineProps<{ id: string }>();
const c = computed(() => COMPANIES.find((x) => x.id === props.id));
</script>

<template>
  <span v-if="c" class="chip" :style="{ background: c.color + '14', color: c.text }">
    <span :style="{ width: '7px', height: '7px', borderRadius: '2px', background: c.color }" />
    {{ c.name }}
  </span>
</template>
