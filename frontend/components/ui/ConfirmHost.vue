<script setup lang="ts">
// Renders whatever useConfirm() is asking. Mounted once in the platform shell.
const { pending, answer } = useConfirm();
const box = ref<HTMLElement | null>(null);
const cancelBtn = ref<HTMLButtonElement | null>(null);
let opener: HTMLElement | null = null;

watch(pending, async (p, old) => {
  if (!import.meta.client) return;
  if (p && !old) {
    opener = document.activeElement as HTMLElement;
    await nextTick();
    // the safe choice gets focus, so Enter never destroys anything by accident
    cancelBtn.value?.focus();
  } else if (!p && old) {
    opener?.focus?.();
  }
});

const onKey = (e: KeyboardEvent) => {
  if (e.key === "Escape") { e.stopPropagation(); answer(false); }
  if (e.key === "Tab") {
    const f = [...(box.value?.querySelectorAll<HTMLElement>("button") || [])];
    if (!f.length) return;
    if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
  }
};
</script>

<template>
  <Teleport to="body">
    <div v-if="pending" class="modal-overlay cf" @mousedown.self="answer(false)" @keydown="onKey">
      <div ref="box" class="modal-box" role="alertdialog" aria-modal="true" aria-labelledby="cf-t" aria-describedby="cf-m" style="max-width: 420px">
        <div class="modal-body">
          <h2 id="cf-t" class="cf-t">
            <span v-if="pending.danger" class="cf-ic"><UiIcon name="alert" :size="18" /></span>
            {{ pending.title }}
          </h2>
          <p v-if="pending.message" id="cf-m" class="cf-m">{{ pending.message }}</p>
          <div class="cf-a">
            <button ref="cancelBtn" class="btn btn-secondary" @click="answer(false)">{{ pending.cancelLabel || "Cancel" }}</button>
            <button class="btn" :class="pending.danger ? 'btn-solid-danger' : 'btn-accent'" @click="answer(true)">
              {{ pending.confirmLabel || "Confirm" }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cf { z-index: 1500; align-items: center; }
.cf-t { display: flex; align-items: center; gap: 10px; font-size: 16px; font-weight: 800; color: #0f172a; }
.cf-ic { width: 32px; height: 32px; border-radius: 50%; background: #fef2f2; color: #dc2626; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.cf-m { font-size: 13.5px; color: #475569; line-height: 1.5; margin-top: 10px; }
.cf-a { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
</style>
