<script setup lang="ts">
// Overflow ("more") menu: keeps destructive actions one step away from routine ones
export interface MenuItem { label: string; icon?: string; danger?: boolean; disabled?: boolean; onClick: () => void }
const props = withDefaults(defineProps<{ items: MenuItem[]; label?: string; align?: "left" | "right" }>(), {
  label: "More actions",
  align: "right",
});
const open = ref(false);
const wrap = ref<HTMLElement | null>(null);
const onDoc = (e: MouseEvent) => { if (wrap.value && !wrap.value.contains(e.target as Node)) open.value = false; };
const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") open.value = false; };
onMounted(() => { document.addEventListener("click", onDoc); document.addEventListener("keydown", onKey); });
onUnmounted(() => { document.removeEventListener("click", onDoc); document.removeEventListener("keydown", onKey); });
const pick = (it: MenuItem) => {
  if (it.disabled) return;
  open.value = false;
  it.onClick();
};
</script>

<template>
  <div ref="wrap" class="mn">
    <button class="mn-btn" :aria-label="label" :title="label" aria-haspopup="menu" :aria-expanded="open" @click.stop="open = !open">
      <slot><UiIcon name="more" :size="16" /></slot>
    </button>
    <div v-if="open" class="mn-pop" :class="align" role="menu">
      <button
        v-for="it in props.items" :key="it.label" role="menuitem" class="mn-it"
        :class="{ danger: it.danger }" :disabled="it.disabled" @click.stop="pick(it)"
      >
        <UiIcon v-if="it.icon" :name="it.icon" :size="14" />
        {{ it.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.mn { position: relative; display: inline-flex; }
.mn-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-width: 32px; height: 32px;
  padding: 0 8px; border-radius: 8px; border: 1.5px solid #e2e8f0; background: #fff; color: #475569;
  cursor: pointer; font: inherit; font-size: 12px; font-weight: 600;
}
.mn-btn:hover { background: #f8fafc; border-color: #cbd5e1; }
.mn-pop {
  position: absolute; top: calc(100% + 6px); z-index: 80; min-width: 170px; padding: 5px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; box-shadow: 0 14px 36px rgba(15,23,42,.14);
}
.mn-pop.right { right: 0; }
.mn-pop.left { left: 0; }
.mn-it {
  display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; border: none; background: none;
  border-radius: 7px; font: inherit; font-size: 12.5px; font-weight: 600; color: #334155; cursor: pointer; text-align: left;
}
.mn-it:hover:not(:disabled) { background: #f1f5f9; }
.mn-it.danger { color: #dc2626; }
.mn-it.danger:hover { background: #fef2f2; }
.mn-it:disabled { opacity: .45; cursor: default; }
</style>
