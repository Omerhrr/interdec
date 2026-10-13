<script setup lang="ts">
// Accessible dialog: role=dialog + aria-modal, labelled by its title, focus moves in
// and stays in (Tab is trapped), Escape / backdrop / ✕ close it, focus returns to the
// button that opened it. With `dirty`, closing asks before throwing typed work away.
const props = withDefaults(defineProps<{ open: boolean; title: string; width?: number; dirty?: boolean; danger?: boolean }>(), {
  width: 520,
});
const emit = defineEmits<{ (e: "close"): void }>();
const { confirm } = useConfirm();

const box = ref<HTMLElement | null>(null);
const uid = `dlg-${Math.random().toString(36).slice(2, 8)}`;
let opener: HTMLElement | null = null;

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
const focusables = () => [...(box.value?.querySelectorAll<HTMLElement>(FOCUSABLE) || [])].filter((e) => e.offsetParent !== null);

const requestClose = async () => {
  if (props.dirty) {
    const ok = await confirm({
      title: "Discard changes?",
      message: "You have unsaved changes in this form. They will be lost.",
      confirmLabel: "Discard",
      cancelLabel: "Keep editing",
      danger: true,
    });
    if (!ok) return;
  }
  emit("close");
};

const onKey = (e: KeyboardEvent) => {
  if (e.key === "Escape") {
    e.stopPropagation();
    requestClose();
    return;
  }
  if (e.key !== "Tab") return;
  const f = focusables();
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
};

watch(() => props.open, async (o) => {
  if (!import.meta.client) return;
  if (o) {
    opener = document.activeElement as HTMLElement;
    document.body.style.overflow = "hidden";
    await nextTick();
    // first form field if there is one, else the dialog itself
    const field = box.value?.querySelector<HTMLElement>(".modal-body input:not([type=hidden]):not([disabled]), .modal-body select, .modal-body textarea");
    (field || box.value)?.focus();
  } else {
    document.body.style.overflow = "";
    opener?.focus?.();
  }
}, { immediate: true });
onBeforeUnmount(() => {
  if (!import.meta.client) return;
  document.body.style.overflow = "";
  opener?.focus?.();
});
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-overlay" @mousedown.self="requestClose" @keydown="onKey">
      <div
        ref="box" class="modal-box" role="dialog" aria-modal="true" :aria-labelledby="`${uid}-t`" tabindex="-1"
        :style="{ maxWidth: width + 'px' }"
      >
        <div class="modal-head">
          <h2 :id="`${uid}-t`" style="font-size: 15px; font-weight: 800">{{ title }}</h2>
          <button class="modal-x" aria-label="Close dialog" @click="requestClose"><UiIcon name="x" :size="16" /></button>
        </div>
        <div class="modal-body">
          <slot />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-x {
  width: 36px; height: 36px; border-radius: 8px; border: none; background: none; color: #475569; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.modal-x:hover { background: #f1f5f9; color: #0f172a; }
.modal-box:focus { outline: none; }
</style>
