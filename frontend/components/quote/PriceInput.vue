<script setup lang="ts">
// Rate-card price with its own currency. Shows the naira equivalent for
// foreign prices so admins can sanity-check the conversion.
const props = defineProps<{
  modelValue: number | null | undefined; currency?: string; suffix?: string; plus?: boolean;
  invalid?: boolean; fx: Record<string, number>; label?: string;
}>();
const emit = defineEmits<{ (e: "update:modelValue", v: number | null): void; (e: "update:currency", v: string): void }>();
const { sym } = useMoney();
const code = computed(() => (props.currency || "NGN").toUpperCase());
const codes = computed(() => {
  const list = Object.keys(props.fx || {}).sort((a, b) => (a === "NGN" ? -1 : b === "NGN" ? 1 : a.localeCompare(b)));
  return list.includes(code.value) ? list : [code.value, ...list];
});
const ngn = computed(() => {
  const r = props.fx?.[code.value];
  if (code.value === "NGN" || !r || props.modelValue == null) return "";
  return `≈ ₦${Math.round(Number(props.modelValue) * r).toLocaleString("en-NG")}`;
});
</script>

<template>
  <div class="pi">
    <div class="pi-row">
      <select
        class="pi-cur" :value="code" :aria-label="`Currency${label ? ' for ' + label : ''}`" title="Currency of this price"
        @click.stop @change="emit('update:currency', ($event.target as HTMLSelectElement).value)"
      >
        <option v-for="c in codes" :key="c" :value="c">{{ c }}</option>
      </select>
      <UiNumberInput
        class="pi-num" :model-value="modelValue" :prefix="(plus ? '+' : '') + sym(code).trim()" :suffix="suffix"
        :invalid="invalid" :label="label" @update:model-value="emit('update:modelValue', $event)"
      />
    </div>
    <span v-if="ngn" class="pi-ngn">{{ ngn }}{{ suffix }}</span>
  </div>
</template>

<style scoped>
.pi-row { display: flex; }
.pi-cur {
  flex: 0 0 auto; width: 62px; border: 1.5px solid #e2e8f0; border-right: none; border-radius: 8px 0 0 8px; background: #f8fafc;
  font: inherit; font-size: 11.5px; font-weight: 700; color: #334155; padding: 0 4px 0 7px; cursor: pointer;
}
.pi-cur:focus-visible { outline: 2px solid #2563eb; outline-offset: -2px; }
.pi-num { flex: 1; min-width: 0; }
.pi-num :deep(.inp) { border-top-left-radius: 0; border-bottom-left-radius: 0; }
.pi-ngn { display: block; font-size: 11px; font-weight: 600; color: #64748b; margin-top: 3px; }
</style>
