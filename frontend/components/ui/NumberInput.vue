<script setup lang="ts">
// Number field that reads like money: "3,400" with a ₦ prefix and a unit suffix
// ("/kg", "/m²", "%"). Shows separators when not editing, raw digits while typing.
const props = defineProps<{ modelValue: number | null | undefined; prefix?: string; suffix?: string; id?: string; label?: string; decimals?: number; invalid?: boolean }>();
const emit = defineEmits<{ (e: "update:modelValue", v: number | null): void }>();
const focused = ref(false);
const text = ref("");

const fmt = (n: number | null | undefined) =>
  n === null || n === undefined || Number.isNaN(n) ? "" : Number(n).toLocaleString("en-NG", { maximumFractionDigits: props.decimals ?? 4 });
watch(() => props.modelValue, (v) => { if (!focused.value) text.value = fmt(v); }, { immediate: true });

const onInput = (e: Event) => {
  const raw = (e.target as HTMLInputElement).value;
  text.value = raw;
  const clean = raw.replace(/[^\d.-]/g, "");
  emit("update:modelValue", clean === "" || clean === "-" ? null : Number(clean));
};
const onFocus = () => { focused.value = true; text.value = props.modelValue == null ? "" : String(props.modelValue); };
const onBlur = () => { focused.value = false; text.value = fmt(props.modelValue); };
</script>

<template>
  <div class="ni" :class="{ bad: invalid }">
    <span v-if="prefix" class="ni-pre" aria-hidden="true">{{ prefix }}</span>
    <input
      :id="id" class="inp num" inputmode="decimal" :value="text" :aria-label="label" :aria-invalid="invalid || undefined"
      :style="{ paddingLeft: prefix ? '26px' : undefined, paddingRight: suffix ? `${12 + suffix.length * 7}px` : undefined }"
      @input="onInput" @focus="onFocus" @blur="onBlur"
    />
    <span v-if="suffix" class="ni-suf" aria-hidden="true">{{ suffix }}</span>
  </div>
</template>

<style scoped>
.ni { position: relative; }
.ni-pre, .ni-suf { position: absolute; top: 50%; transform: translateY(-50%); font-size: 12.5px; color: #64748b; pointer-events: none; }
.ni-pre { left: 11px; }
.ni-suf { right: 11px; }
.ni.bad .inp { border-color: #dc2626; }
</style>
