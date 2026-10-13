<script setup lang="ts">
// Password field with a show/hide toggle (hard to type blind on a phone)
const props = defineProps<{ modelValue: string; id?: string; placeholder?: string; autocomplete?: string; invalid?: boolean; describedby?: string }>();
const emit = defineEmits<{ (e: "update:modelValue", v: string): void; (e: "enter"): void }>();
const shown = ref(false);
</script>

<template>
  <div class="pw">
    <input
      :id="id" class="inp" :type="shown ? 'text' : 'password'" :value="modelValue" :placeholder="placeholder"
      :autocomplete="autocomplete || 'current-password'" :aria-invalid="invalid || undefined" :aria-describedby="describedby"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" @keydown.enter="emit('enter')"
    />
    <button type="button" class="pw-t" :aria-label="shown ? 'Hide password' : 'Show password'" :aria-pressed="shown" @click="shown = !shown">
      <UiIcon :name="shown ? 'eyeOff' : 'eye'" :size="16" />
    </button>
  </div>
</template>

<style scoped>
.pw { position: relative; }
.pw .inp { padding-right: 44px; }
.pw-t {
  position: absolute; right: 2px; top: 50%; transform: translateY(-50%); width: 40px; height: 36px;
  border: none; background: none; color: #64748b; cursor: pointer; display: flex; align-items: center; justify-content: center; border-radius: 6px;
}
.pw-t:hover { color: #0f172a; }
</style>
