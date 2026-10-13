<script setup lang="ts">
// Change own password - validates against the backend then updates the hash
// forced: shown after login with a demo or admin-set password; cannot be dismissed
const props = defineProps<{ forced?: boolean }>();
const emit = defineEmits<{ (e: "close"): void; (e: "done"): void }>();
const { fetchMe, logout } = useAuth();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();

const cur = ref("");
const next = ref("");
const rep = ref("");
const err = ref("");      // server / general error
const tried = ref(false);
const saving = ref(false);
const DEMO = ["123456", "sales123", "viewer123"];

// each field says what's wrong with it, next to it
const fieldErr = computed(() => {
  const e: Record<string, string> = {};
  if (!cur.value) e.cur = "Enter your current password";
  if (!next.value) e.next = "Choose a new password";
  else if (next.value.length < 6) e.next = `Use at least 6 characters (${next.value.length} so far)`;
  else if (next.value === cur.value) e.next = "Must be different from your current password";
  else if (DEMO.includes(next.value)) e.next = "That password is publicly known; choose another";
  if (!rep.value) e.rep = "Type the new password again";
  else if (next.value && rep.value !== next.value) e.rep = "Doesn't match the new password";
  return e;
});
const show = (k: string) => (tried.value ? fieldErr.value[k] : "");

const save = async () => {
  err.value = "";
  tried.value = true;
  if (Object.keys(fieldErr.value).length) {
    await nextTick();
    document.querySelector<HTMLElement>(".pwf [aria-invalid=true]")?.focus();
    return;
  }
  saving.value = true;
  try {
    await request("/api/auth/change-password", {
      method: "POST",
      keepAuthOn401: true,
      body: { currentPassword: cur.value, newPassword: next.value },
    });
    notify("Password changed");
    await fetchMe();
    emit("done");
    emit("close");
  } catch (e: any) {
    err.value = e.message || "Couldn't change the password";
  } finally {
    saving.value = false;
  }
};
</script>

<template>
  <UiAppModal open :title="forced ? 'Choose a new password' : 'Change password'" :width="400" :dirty="!forced && !!(cur || next || rep)" @close="!forced && emit('close')">
    <form class="pwf" novalidate @submit.prevent="save">
      <p v-if="forced" class="intro">
        You signed in with a demo or temporary password. Set your own to continue.
      </p>
      <div>
        <label class="lbl" for="pw-cur">Current password</label>
        <UiPasswordInput id="pw-cur" v-model="cur" :invalid="!!show('cur')" describedby="pw-cur-e" />
        <p v-if="show('cur')" id="pw-cur-e" class="fe">{{ show("cur") }}</p>
      </div>
      <div>
        <label class="lbl" for="pw-new">New password</label>
        <UiPasswordInput id="pw-new" v-model="next" autocomplete="new-password" :invalid="!!show('next')" describedby="pw-new-e" />
        <p id="pw-new-e" :class="show('next') ? 'fe' : 'fh'">{{ show("next") || "At least 6 characters" }}</p>
      </div>
      <div>
        <label class="lbl" for="pw-rep">Repeat new password</label>
        <UiPasswordInput id="pw-rep" v-model="rep" autocomplete="new-password" :invalid="!!show('rep')" describedby="pw-rep-e" />
        <p v-if="show('rep')" id="pw-rep-e" class="fe">{{ show("rep") }}</p>
      </div>
      <div v-if="err" class="err" role="alert">{{ err }}</div>
      <div class="acts">
        <button v-if="!forced" type="button" class="btn btn-secondary" @click="emit('close')">Cancel</button>
        <button v-else type="button" class="btn btn-secondary" @click="logout">Sign out</button>
        <button class="btn btn-accent" :disabled="saving">{{ saving ? "Saving…" : "Update password" }}</button>
      </div>
    </form>
  </UiAppModal>
</template>


<style scoped>
.pwf { display: grid; gap: 12px; }
.intro { font-size: 13px; color: #475569; margin: 0; line-height: 1.5; }
.fe { font-size: 12px; color: #b91c1c; font-weight: 600; margin-top: 5px; }
.fh { font-size: 12px; color: #64748b; margin-top: 5px; }
.acts { display: flex; gap: 8px; justify-content: flex-end; margin-top: 6px; }
.err {
  padding: 8px 12px; background: #fef2f2; border: 1px solid #fecaca;
  border-radius: 7px; font-size: 12px; color: #dc2626; font-weight: 600;
}
</style>
