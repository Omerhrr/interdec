<script setup lang="ts">
// Change own password - validates against the backend then updates the hash
const emit = defineEmits<{ (e: "close"): void; (e: "done"): void }>();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();

const cur = ref("");
const next = ref("");
const rep = ref("");
const err = ref("");
const saving = ref(false);

const save = async () => {
  err.value = "";
  if (!cur.value || !next.value || !rep.value) {
    err.value = "All fields are required";
    return;
  }
  if (next.value.length < 6) {
    err.value = "New password must be at least 6 characters";
    return;
  }
  if (next.value !== rep.value) {
    err.value = "New passwords do not match";
    return;
  }
  saving.value = true;
  try {
    await request("/api/auth/change-password", {
      method: "POST",
      body: { currentPassword: cur.value, newPassword: next.value },
    });
    notify("Password changed successfully");
    emit("done");
    emit("close");
  } catch (e: any) {
    err.value = e.message || "Failed to change password";
  } finally {
    saving.value = false;
  }
};
</script>

<template>
  <UiAppModal open title="Change Password" :width="380" @close="emit('close')">
    <div style="display: grid; gap: 12px">
      <div>
        <label class="lbl">Current Password</label>
        <input v-model="cur" type="password" class="inp" placeholder="Enter current password" />
      </div>
      <div>
        <label class="lbl">New Password</label>
        <input v-model="next" type="password" class="inp" placeholder="At least 6 characters" />
      </div>
      <div>
        <label class="lbl">Repeat New Password</label>
        <input v-model="rep" type="password" class="inp" placeholder="Repeat new password" @keydown.enter="save" />
      </div>
      <div v-if="err" class="err">{{ err }}</div>
      <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 6px">
        <button class="btn btn-secondary" @click="emit('close')">Cancel</button>
        <button class="btn btn-accent" :disabled="saving" @click="save">
          {{ saving ? "Saving…" : "Update Password" }}
        </button>
      </div>
    </div>
  </UiAppModal>
</template>

<style scoped>
.err {
  padding: 8px 12px; background: #fef2f2; border: 1px solid #fecaca;
  border-radius: 7px; font-size: 12px; color: #dc2626; font-weight: 600;
}
</style>
