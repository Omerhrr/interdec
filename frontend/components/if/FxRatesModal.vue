<script setup lang="ts">
// Exchange rates to USD (server-stored). Admins edit; everyone else sees what's used.
const emit = defineEmits<{ (e: "close"): void }>();
const { fx, fxLabel, saveFx } = useData();
const { importflowRole } = useAuth();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const canEdit = computed(() => importflowRole.value === "admin");
const draft = ref<Record<string, number>>({ ...fx.value.rates });
const saving = ref(false);

const save = async () => {
  if (Object.entries(draft.value).some(([, v]) => !(Number(v) > 0))) {
    notify("Every rate must be greater than zero", "error");
    return;
  }
  saving.value = true;
  try {
    await saveFx(Object.fromEntries(Object.entries(draft.value).map(([k, v]) => [k, Number(v)])));
    notify("Exchange rates saved for everyone");
    emit("close");
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    saving.value = false;
  }
};
</script>

<template>
  <UiAppModal open title="Exchange rates to USD" :width="420" @close="emit('close')">
    <p class="note">
      Used to convert every shipment value into the USD totals on the dashboard, projects and reports.
      Currently using <strong>{{ fxLabel }}</strong>.
    </p>
    <div class="rows">
      <label v-for="(r, k) in draft" :key="k" class="row">
        <span class="code">1 {{ k }}</span>
        <span class="eq">=</span>
        <input
          v-model.number="draft[k]" type="number" step="0.0001" min="0" class="inp num"
          :disabled="k === 'USD' || !canEdit" :aria-label="`${k} to USD`"
        />
        <span class="code">USD</span>
      </label>
    </div>
    <p v-if="!canEdit" class="note" style="margin-top: 12px">Only ImportFlow admins can change rates.</p>
    <div class="actions">
      <button class="btn btn-secondary" @click="emit('close')">{{ canEdit ? "Cancel" : "Close" }}</button>
      <button v-if="canEdit" class="btn btn-accent" :disabled="saving" @click="save">
        {{ saving ? "Saving…" : "Save rates" }}
      </button>
    </div>
  </UiAppModal>
</template>

<style scoped>
.note { font-size: 12.5px; color: #64748b; line-height: 1.5; margin-bottom: 14px; }
.rows { display: grid; gap: 8px; }
.row { display: grid; grid-template-columns: 64px 14px 1fr 40px; align-items: center; gap: 8px; }
.code { font-size: 12px; font-weight: 700; color: #334155; }
.eq { color: #64748b; }
.actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
</style>
