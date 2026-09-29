<script setup lang="ts">
// Select dropdown field — mirrors original Kn component
const props = defineProps<{
  label: string;
  options: (string | { value: string; label: string })[];
  modelValue: string;
  placeholder?: string;
  disabled?: boolean;
}>();
const emit = defineEmits<{ (e: "update:modelValue", v: string): void }>();
</script>

<template>
  <div>
    <label class="lbl">{{ label }}</label>
    <select
      class="inp"
      :value="modelValue"
      :disabled="disabled"
      :style="disabled ? { background: '#f8fafc', color: '#94a3b8', cursor: 'not-allowed' } : {}"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option value="" disabled>{{ placeholder || "Select..." }}</option>
      <option v-for="o in options" :key="typeof o === 'string' ? o : o.value" :value="typeof o === 'string' ? o : o.value">
        {{ typeof o === 'string' ? o : o.label }}
      </option>
    </select>
  </div>
</template>
