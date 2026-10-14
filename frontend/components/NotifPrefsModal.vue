<script setup lang="ts">
// My email notifications: which emails this person wants from Interdec.
const emit = defineEmits<{ (e: "close"): void }>();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();
const data = ref<any>(null);
const form = ref<any>({});
const saving = ref(false);
const sending = ref(false);
onMounted(async () => {
  try {
    data.value = await request("/api/auth/me/notifications");
    form.value = { ...data.value.prefs };
  } catch (e: any) {
    notify(e.message, "error");
    emit("close");
  }
});
const dirty = computed(() => !!data.value && JSON.stringify(form.value) !== JSON.stringify(data.value.prefs));
const OPTS = computed(() => [
  { k: "statusChanges", t: "Shipment status changes", d: "When a shipment moves to Under Production, In Transit or Completed.", show: data.value?.canImportflow },
  { k: "payablesDigest", t: "Weekly payables summary", d: "Monday morning: vendor balances and unpaid shipping and clearing, with what's due now.", show: data.value?.canImportflow },
  { k: "quoteOutcomes", t: "Quotes won or lost", d: "When anyone marks a quote won or lost, with the PO number or reason.", show: data.value?.canQuotes },
].filter((o) => o.show));
const save = async () => {
  saving.value = true;
  try {
    data.value = await request("/api/auth/me/notifications", { method: "PUT", body: form.value });
    form.value = { ...data.value.prefs };
    notify("Email notification settings saved");
    emit("close");
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    saving.value = false;
  }
};
const sendDigest = async () => {
  sending.value = true;
  try {
    await request("/api/auth/me/notifications/digest", { method: "POST" });
    notify(`This week's payables summary was sent to ${data.value.email}`);
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    sending.value = false;
  }
};
</script>

<template>
  <UiAppModal open title="Email notifications" :width="480" :dirty="dirty && !saving" @close="emit('close')">
    <div v-if="data" class="np">
      <p class="np-to">Sent to <strong>{{ data.email }}</strong>. ETA reminders are set on each shipment.</p>
      <p v-if="!data.emailSetUp" class="np-warn">Email isn't set up on the server yet. Your choices are saved and emails start once it is.</p>
      <label v-for="o in OPTS" :key="o.k" class="np-row">
        <input v-model="form[o.k]" type="checkbox" />
        <span><strong>{{ o.t }}</strong><small>{{ o.d }}</small></span>
      </label>
      <p v-if="!OPTS.length" class="np-to">There are no email notifications for the apps you use yet.</p>
      <div class="np-acts">
        <button v-if="data.canImportflow" type="button" class="btn btn-ghost btn-sm" :disabled="sending" @click="sendDigest">{{ sending ? "Sending…" : "Send me this week's summary" }}</button>
        <span style="flex: 1" />
        <button type="button" class="btn btn-secondary" @click="emit('close')">Cancel</button>
        <button type="button" class="btn btn-accent" :disabled="saving || !dirty" @click="save">{{ saving ? "Saving…" : "Save" }}</button>
      </div>
    </div>
  </UiAppModal>
</template>

<style scoped>
.np { display: grid; gap: 10px; }
.np-to { font-size: 12.5px; color: #475569; }
.np-warn { font-size: 12.5px; font-weight: 600; color: #92400e; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 8px 10px; }
.np-row { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 10px; cursor: pointer; }
.np-row:has(input:checked) { border-color: #93c5fd; background: #eff6ff; }
.np-row input { width: 17px; height: 17px; margin-top: 2px; accent-color: #2563eb; flex-shrink: 0; }
.np-row span { display: flex; flex-direction: column; gap: 2px; }
.np-row strong { font-size: 13.5px; color: #0f172a; }
.np-row small { font-size: 12px; color: #64748b; line-height: 1.4; }
.np-acts { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
</style>
