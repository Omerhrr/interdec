<script setup lang="ts">
// Status tracker - exact replica of the original lv() component
const props = defineProps<{ status: string }>();
const { STATUS_ORDER, STATUS_COLORS } = useConstants();
const steps = [
  { k: "order_placed", l: "Order Placed", n: "1" },
  { k: "under_production", l: "Production", n: "2" },
  { k: "in_transit", l: "In Transit", n: "3" },
  { k: "completed", l: "Completed", n: "✓" },
];
const currentIdx = computed(() => STATUS_ORDER.indexOf(props.status));
</script>

<template>
  <div class="tracker">
    <template v-for="(s, i) in steps" :key="s.k">
      <div class="step">
        <div class="step-col" style="min-width: 52px">
          <div
            class="dot"
            :style="{
              background: i <= currentIdx ? STATUS_COLORS[s.k] : '#f1f5f9',
              color: i <= currentIdx ? '#fff' : '#94a3b8',
              border: i === currentIdx ? `2px solid ${STATUS_COLORS[s.k]}` : '2px solid transparent',
              boxShadow: i === currentIdx ? `0 0 0 3px ${STATUS_COLORS[s.k]}22` : 'none',
            }"
          >{{ s.n }}</div>
          <span :style="{ fontSize: '8px', fontWeight: 600, color: i <= currentIdx ? STATUS_COLORS[s.k] : '#94a3b8', marginTop: '2px', whiteSpace: 'nowrap' }">{{ s.l }}</span>
        </div>
      </div>
      <div
        v-if="i < steps.length - 1"
        :style="{ width: '18px', height: '2px', background: i < currentIdx ? STATUS_COLORS[steps[i + 1].k] : '#e2e8f0', marginBottom: '12px', borderRadius: '1px', flexShrink: 0 }"
      />
    </template>
  </div>
</template>

<style scoped>
.tracker { display: flex; align-items: flex-start; gap: 0; overflow-x: auto; padding: 4px 0; }
.step { display: flex; align-items: center; }
.step-col { display: flex; flex-direction: column; align-items: center; }
.dot {
  width: 24px; height: 24px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 700;
}
</style>
