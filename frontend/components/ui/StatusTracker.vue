<script setup lang="ts">
// Shipment progress: an ordered list of steps, current step announced to screen readers
const props = defineProps<{ status: string }>();
const { STATUS_ORDER, STATUS_COLORS, STATUS_TEXT } = useConstants();
const steps = [
  { k: "order_placed", l: "Order placed" },
  { k: "under_production", l: "Production" },
  { k: "in_transit", l: "In transit" },
  { k: "completed", l: "Completed" },
];
const currentIdx = computed(() => STATUS_ORDER.indexOf(props.status));
</script>

<template>
  <ol class="tracker" aria-label="Shipment progress">
    <li
      v-for="(s, i) in steps" :key="s.k" class="step"
      :aria-current="i === currentIdx ? 'step' : undefined"
    >
      <span
        class="dot"
        :style="{
          background: i <= currentIdx ? STATUS_COLORS[s.k] : '#f1f5f9',
          color: i <= currentIdx ? '#fff' : '#475569',
          boxShadow: i === currentIdx ? `0 0 0 3px ${STATUS_COLORS[s.k]}33` : 'none',
        }"
      >
        <UiIcon v-if="i < currentIdx || (s.k === 'completed' && i === currentIdx)" name="check" :size="12" :stroke="3" />
        <template v-else>{{ i + 1 }}</template>
      </span>
      <span class="lab" :style="{ color: i <= currentIdx ? STATUS_TEXT[s.k] : '#64748b', fontWeight: i === currentIdx ? 800 : 600 }">
        {{ s.l }}<span class="sr-only">{{ i < currentIdx ? " (done)" : i === currentIdx ? " (current)" : "" }}</span>
      </span>
      <span v-if="i < steps.length - 1" class="bar" :style="{ background: i < currentIdx ? STATUS_COLORS[steps[i + 1].k] : '#e2e8f0' }" aria-hidden="true" />
    </li>
  </ol>
</template>

<style scoped>
.tracker { display: flex; list-style: none; gap: 0; overflow-x: auto; padding: 4px 0; }
.step { display: flex; align-items: center; gap: 7px; }
.dot {
  width: 24px; height: 24px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800;
}
.lab { font-size: 12px; white-space: nowrap; }
.bar { width: 28px; height: 2px; margin: 0 10px; border-radius: 1px; flex-shrink: 0; }
.tracker { max-width: 100%; min-width: 0; }
/* phones: label under each dot so all four steps fit without sideways scrolling */
@media (max-width: 640px) {
  .tracker { width: 100%; justify-content: space-between; }
  .step { flex-direction: column; gap: 4px; flex: 1 1 0; min-width: 0; text-align: center; }
  .lab { font-size: 10.5px; white-space: normal; line-height: 1.2; }
  .bar { display: none; }
}
</style>
