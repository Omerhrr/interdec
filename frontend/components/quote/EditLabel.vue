<script setup lang="ts">
// A name with a pencil: click to rename in place (Enter saves, Esc cancels).
// Saving an empty name means "back to the original", which the parent handles.
const props = defineProps<{ text: string; what?: string }>();
const emit = defineEmits<{ (e: "save", v: string): void }>();
const editing = ref(false);
const val = ref("");
const inp = ref<HTMLInputElement | null>(null);
// Inside a collapsible section heading, typing a space would open/close the
// section; keep it as it was while the name is being edited.
let holder: HTMLDetailsElement | null = null;
let stop: (() => void) | null = null;
const root = ref<HTMLElement | null>(null);
const start = () => {
  val.value = props.text;
  editing.value = true;
  const d = (root.value?.closest("summary")?.parentElement as HTMLDetailsElement) || null;
  if (d) {
    const wasOpen = d.open;
    const keep = () => { if (d.open !== wasOpen) d.open = wasOpen; };
    d.addEventListener("toggle", keep);
    holder = d;
    stop = () => d.removeEventListener("toggle", keep);
  }
  nextTick(() => inp.value?.select());
};
// keep guarding briefly after editing ends: a late key event can still toggle
const release = () => { const s = stop; stop = null; holder = null; setTimeout(() => s?.(), 400); };
onUnmounted(() => stop?.());
const done = (save: boolean) => {
  if (!editing.value) return;
  editing.value = false;
  release();
  if (save && val.value.trim() !== props.text) emit("save", val.value.trim());
};
</script>

<template>
  <span ref="root" class="el">
    <input
      v-if="editing" ref="inp" v-model="val" class="inp el-in" maxlength="60" :aria-label="`New name for ${what || text}`"
      placeholder="Empty = original name"
      @click.stop.prevent @keydown.stop @keyup.stop @keydown.enter.prevent="done(true)" @keydown.esc.prevent="done(false)" @blur="done(true)"
    />
    <template v-else>{{ text }}</template>
    <button v-if="!editing" type="button" class="el-pen" :aria-label="`Rename ${what || text}`" title="Rename" @click.stop.prevent="start">
      <UiIcon name="edit" :size="12" />
    </button>
  </span>
</template>

<style scoped>
.el { display: inline-flex; align-items: center; gap: 4px; min-width: 0; }
.el-in { padding: 3px 7px; font-size: 12px; font-weight: 700; min-width: 140px; text-transform: none; letter-spacing: 0; }
.el-pen { background: none; border: none; color: #94a3b8; cursor: pointer; padding: 2px; border-radius: 5px; display: inline-flex; opacity: .6; }
.el-pen:hover, .el-pen:focus-visible { color: #2563eb; background: #eff6ff; opacity: 1; }
</style>
