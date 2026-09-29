<script setup lang="ts">
// Company logo chip - mirrors original `pn` component
import { COMPANIES } from "~/composables/useConstants";
const props = defineProps<{ id: string }>();
const c = COMPANIES.find((x) => x.id === props.id);
</script>

<template>
  <span v-if="c" class="chip" :style="{ background: c.color + '14', color: c.color }">
    <img :src="c.logo" :alt="c.name" style="height: 10px; width: auto; object-fit: contain" />
    {{ c.name }}
  </span>
</template>
