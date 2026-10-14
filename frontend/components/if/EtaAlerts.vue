<script setup lang="ts">
// ETA email alerts for one shipment: who gets them and when. Reminders are sent
// by the server on schedule; this card only edits the settings and shows what went out.
const props = defineProps<{ shipment: any; canEdit: boolean }>();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();
const user = useAuth().user;
const { fmtEta, etaToIso } = useConstants();

const info = ref<any>(null);
const form = ref<any>(null);
const saved = ref("");
const saving = ref(false);
const testing = ref(false);
const newAddr = ref("");
const addrErr = ref("");
watch(newAddr, () => (addrErr.value = ""));

const pick = (x: any) => ({ enabled: !!x.enabled, recipients: [...(x.recipients || [])], before: [...(x.before || [])], onDay: !!x.onDay, overdue: !!x.overdue, onChange: !!x.onChange });
const load = async () => {
  try {
    info.value = await request(`/api/shipments/${props.shipment.id}/eta-alerts`);
    form.value = pick(info.value);
    saved.value = JSON.stringify(form.value);
  } catch (e: any) {
    notify(e.message, "error");
  }
};
onMounted(load);
watch(() => props.shipment.id, load);
watch(() => props.shipment.eta, () => { if (!dirty.value) load(); });
const dirty = computed(() => !!form.value && JSON.stringify(form.value) !== saved.value);

const DAYS = [30, 14, 7, 5, 3, 2, 1];
const toggleDay = (n: number) => {
  const s = new Set<number>(form.value.before);
  s.has(n) ? s.delete(n) : s.add(n);
  form.value.before = [...s].sort((a, b) => b - a);
};
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const addAddr = (addr = newAddr.value) => {
  const a = addr.trim().toLowerCase();
  addrErr.value = "";
  if (!a) return;
  if (!EMAIL.test(a)) { addrErr.value = "That doesn't look like an email address"; return; }
  if (!form.value.recipients.includes(a)) form.value.recipients.push(a);
  newAddr.value = "";
};
const removeAddr = (a: string) => (form.value.recipients = form.value.recipients.filter((x: string) => x !== a));
const me = computed(() => (user.value as any)?.email?.toLowerCase() || "");

// next reminder, in plain words
const etaIso = computed(() => etaToIso(props.shipment.eta));
const nextText = computed(() => {
  if (!form.value?.enabled) return "";
  if (!etaIso.value) return "No ETA yet. Reminders start once one is set.";
  if (props.shipment.status === "completed") return "Shipment received. No more reminders.";
  const [y, m, d] = etaIso.value.split("-").map(Number);
  const eta = new Date(y, m - 1, d);
  const t = new Date(); t.setHours(0, 0, 0, 0);
  const days = Math.round((eta.getTime() - t.getTime()) / 864e5);
  const day = (n: number) => { const x = new Date(eta); x.setDate(x.getDate() - n); return x.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }); };
  const upcoming = form.value.before.filter((n: number) => n < days).sort((a: number, b: number) => b - a);
  if (days > 0 && upcoming.length) return `Next: ${upcoming[0]} day${upcoming[0] === 1 ? "" : "s"} before, on ${day(upcoming[0])}.`;
  if (days > 0 && form.value.onDay) return `Next: on arrival day, ${day(0)}.`;
  if (days === 0) return form.value.onDay ? "Due today. The on-the-day email goes out today." : "Due today.";
  if (days < 0) return form.value.overdue ? `Overdue by ${-days} day${days === -1 ? "" : "s"}. An overdue email is sent once.` : `Overdue by ${-days} days.`;
  return "";
});

const save = async () => {
  addAddr();
  if (addrErr.value) return;
  if (form.value.enabled && !form.value.recipients.length) { addrErr.value = "Add at least one email address"; return; }
  saving.value = true;
  try {
    info.value = await request(`/api/shipments/${props.shipment.id}/eta-alerts`, { method: "PUT", body: form.value });
    form.value = pick(info.value);
    saved.value = JSON.stringify(form.value);
    notify(form.value.enabled ? `ETA alerts on for ${form.value.recipients.length} recipient${form.value.recipients.length === 1 ? "" : "s"}` : "ETA alerts turned off");
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    saving.value = false;
  }
};
const toggleEnabled = () => {
  form.value.enabled = !form.value.enabled;
  if (form.value.enabled && !form.value.recipients.length && me.value) form.value.recipients.push(me.value);
};
const sendTest = async () => {
  addAddr();
  const to = form.value.recipients.length ? form.value.recipients : me.value ? [me.value] : [];
  if (!to.length) { addrErr.value = "Add an email address to send the test to"; return; }
  testing.value = true;
  try {
    await request(`/api/shipments/${props.shipment.id}/eta-alerts/test`, { method: "POST", body: { recipients: to } });
    notify(`Test email sent to ${to.join(", ")}`);
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    testing.value = false;
    load();
  }
};
const KIND: Record<string, string> = { "eta.on_day": "Arrival day", "eta.overdue": "Overdue", "eta.changed": "ETA changed", "eta.test": "Test" };
const kindLabel = (k: string) => KIND[k] || (k?.startsWith("eta.before_") ? `${k.split("_")[1]} day${k.endsWith("_1") ? "" : "s"} before` : k);
const when = (ts: number) => new Date(ts).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
</script>

<template>
  <section v-if="form" class="card ea" aria-labelledby="ea-t">
    <div class="ea-head">
      <span class="ea-ic"><UiIcon name="bell" :size="16" /></span>
      <div style="flex: 1; min-width: 0">
        <h2 id="ea-t" class="ea-t">ETA email alerts</h2>
        <p class="ea-sub">
          <template v-if="form.enabled">On · {{ form.recipients.length }} recipient{{ form.recipients.length === 1 ? "" : "s" }}<template v-if="shipment.eta"> · ETA {{ fmtEta(shipment.eta) }}</template></template>
          <template v-else>Get an email before this shipment arrives</template>
        </p>
      </div>
      <button
        v-if="canEdit" type="button" role="switch" class="sw" :aria-checked="form.enabled" aria-labelledby="ea-t"
        @click="toggleEnabled"
      ><span /></button>
      <span v-else class="chip" :style="{ background: form.enabled ? '#ecfdf5' : '#f1f5f9', color: form.enabled ? '#047857' : '#475569' }">{{ form.enabled ? "On" : "Off" }}</span>
    </div>

    <div v-if="info && !info.email.configured" class="ea-warn" role="status">
      Email isn't set up on the server yet, so nothing can be sent. Settings are kept and alerts start as soon as it is.
    </div>
    <p v-if="nextText" class="ea-next">{{ nextText }}</p>

    <template v-if="form.enabled && canEdit">
      <div class="ea-block">
        <span class="lbl">Send to</span>
        <div class="chips">
          <span v-for="a in form.recipients" :key="a" class="rc">
            {{ a }}<button type="button" :aria-label="`Remove ${a}`" @click="removeAddr(a)"><UiIcon name="x" :size="12" /></button>
          </span>
        </div>
        <div class="add">
          <input
            v-model="newAddr" class="inp" type="email" placeholder="name@company.com" aria-label="Add email address"
            :aria-invalid="!!addrErr || undefined" @keydown.enter.prevent="addAddr()"
          />
          <button class="btn btn-secondary btn-sm" type="button" @click="addAddr()">Add</button>
          <button v-if="me && !form.recipients.includes(me)" class="btn btn-ghost btn-sm" type="button" @click="addAddr(me)">Add me</button>
        </div>
        <p v-if="addrErr" class="fe" role="alert">{{ addrErr }}</p>
      </div>

      <div class="ea-block">
        <span class="lbl">Remind</span>
        <div class="pills" role="group" aria-label="Days before arrival">
          <button v-for="n in DAYS" :key="n" type="button" class="pill" :aria-pressed="form.before.includes(n)" @click="toggleDay(n)">
            {{ n }} day{{ n === 1 ? "" : "s" }} before
          </button>
        </div>
        <div class="checks">
          <label class="chk"><input v-model="form.onDay" type="checkbox" /> On arrival day</label>
          <label class="chk"><input v-model="form.overdue" type="checkbox" /> If it's overdue</label>
          <label class="chk"><input v-model="form.onChange" type="checkbox" /> When the ETA changes</label>
        </div>
      </div>
    </template>
    <p v-else-if="form.enabled" class="ea-ro">Sent to {{ form.recipients.join(", ") }}</p>

    <div v-if="canEdit && (dirty || form.enabled)" class="ea-acts">
      <button v-if="form.enabled" class="btn btn-secondary btn-sm" :disabled="testing" @click="sendTest">{{ testing ? "Sending…" : "Send test email" }}</button>
      <button v-if="dirty" class="btn btn-accent btn-sm" :disabled="saving" @click="save">{{ saving ? "Saving…" : "Save alerts" }}</button>
    </div>

    <details v-if="info?.log?.length" class="ea-log">
      <summary>Recent emails ({{ info.log.length }})</summary>
      <ul>
        <li v-for="(l, i) in info.log" :key="i">
          <span class="st" :class="l.status">{{ l.status === "sent" ? "Sent" : l.status === "failed" ? "Failed" : "Not sent" }}</span>
          <span class="k">{{ kindLabel(l.kind) }}</span>
          <span class="w">{{ when(l.ts) }}</span>
          <span class="to" :title="l.error || l.to">{{ l.status === "sent" ? l.to : l.error || l.to }}</span>
        </li>
      </ul>
    </details>
  </section>
</template>

<style scoped>
.ea { margin-bottom: 14px; display: grid; gap: 12px; }
.ea-head { display: flex; align-items: center; gap: 10px; }
.ea-ic { width: 32px; height: 32px; border-radius: 9px; background: #eff6ff; color: #2563eb; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ea-t { font-size: 14px; font-weight: 800; color: #0f172a; }
.ea-sub { font-size: 12px; color: #64748b; margin-top: 1px; }
.sw { width: 42px; height: 24px; border-radius: 20px; border: none; background: #cbd5e1; position: relative; cursor: pointer; flex-shrink: 0; transition: background .15s; }
.sw span { position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%; background: #fff; transition: transform .15s; box-shadow: 0 1px 3px rgba(0,0,0,.2); }
.sw[aria-checked="true"] { background: #2563eb; }
.sw[aria-checked="true"] span { transform: translateX(18px); }
.sw:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.ea-warn { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; border-radius: 8px; padding: 8px 11px; font-size: 12.5px; font-weight: 600; }
.ea-next { font-size: 12.5px; color: #1e3a8a; background: #eff6ff; border-radius: 8px; padding: 7px 11px; font-weight: 600; }
.ea-block { display: grid; gap: 7px; }
.lbl { font-size: 12px; font-weight: 700; color: #334155; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.rc { display: inline-flex; align-items: center; gap: 4px; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 20px; padding: 3px 4px 3px 10px; font-size: 12.5px; color: #0f172a; max-width: 100%; overflow-wrap: anywhere; }
.rc button { border: none; background: none; cursor: pointer; color: #64748b; display: flex; padding: 3px; border-radius: 50%; }
.rc button:hover { background: #fee2e2; color: #b91c1c; }
.add { display: flex; gap: 6px; flex-wrap: wrap; }
.add .inp { flex: 1 1 200px; min-width: 0; }
.fe { font-size: 12px; color: #b91c1c; font-weight: 600; }
.pills { display: flex; flex-wrap: wrap; gap: 6px; }
.pill { font: inherit; font-size: 12px; font-weight: 600; color: #475569; background: #fff; border: 1px solid #cbd5e1; border-radius: 20px; padding: 5px 11px; cursor: pointer; }
.pill[aria-pressed="true"] { background: #1d4ed8; border-color: #1d4ed8; color: #fff; }
.checks { display: flex; flex-wrap: wrap; gap: 6px 16px; }
.chk { display: flex; align-items: center; gap: 7px; font-size: 12.5px; font-weight: 600; color: #334155; cursor: pointer; min-height: 28px; }
.chk input { width: 16px; height: 16px; accent-color: #2563eb; }
.ea-ro { font-size: 12.5px; color: #475569; overflow-wrap: anywhere; }
.ea-acts { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }
.ea-log summary { font-size: 12px; font-weight: 700; color: #475569; cursor: pointer; }
.ea-log ul { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 5px; }
.ea-log li { display: grid; grid-template-columns: auto auto auto 1fr; gap: 8px; align-items: center; font-size: 12px; color: #475569; }
.st { font-size: 10.5px; font-weight: 800; border-radius: 20px; padding: 1px 8px; }
.st.sent { background: #ecfdf5; color: #047857; }
.st.failed { background: #fef2f2; color: #b91c1c; }
.st.not_configured { background: #fffbeb; color: #92400e; }
.k { font-weight: 700; color: #0f172a; }
.to { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
@media (max-width: 560px) { .ea-log li { grid-template-columns: auto 1fr; } .ea-log .w, .ea-log .to { grid-column: 2; } }
</style>
