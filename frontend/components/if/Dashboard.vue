<script setup lang="ts">
// Dashboard: company cards, active/closed stats, active pipeline, recent activity
const emit = defineEmits<{ (e: "navigate", p: string, d?: string | null, id?: string | null): void }>();
const { shipments, vendorName, shipperName, activity, loadActivity, timeAgo, toUsd, fxLabel } = useData();
const { COMPANIES, STATUS_ORDER } = useConstants();
const { importflowRole: role } = useAuth();
const canEdit = computed(() => role.value === "admin" || role.value === "user");

// Activity: 5 latest by default (sign-ins excluded server-side); "View all" loads 30
const showAllActivity = ref(false);
const activityLoading = ref(true);
onMounted(async () => { await loadActivity(5); activityLoading.value = false; });
const toggleActivity = async () => {
  showAllActivity.value = !showAllActivity.value;
  await loadActivity(showAllActivity.value ? 30 : 5);
};

const totalUsd = (list: any[]) => list.reduce((a, s) => a + toUsd(s), 0);
const fmtUsd = (n: number) => "$" + Math.round(n).toLocaleString();

const activeCount = computed(() => shipments.value.filter((s) => s.status !== "completed").length);
const closedCount = computed(() => shipments.value.filter((s) => s.status === "completed").length);

const pipeline = computed(() =>
  shipments.value
    .filter((s) => s.status !== "completed")
    .sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status))
);

const newShipment = ref(false);
const ratesOpen = ref(false);
</script>

<template>
  <div class="page">
    <div class="head">
      <h1 class="ph">Dashboard</h1>
      <div class="head-acts">
        <IfExportMenu kind="dashboard" />
        <button v-if="canEdit" class="btn btn-accent fab-m" @click="newShipment = true">
          <UiIcon name="plus" :size="15" /> New Shipment
        </button>
      </div>
    </div>

    <!-- Company cards -->
    <div class="company-grid">
      <div v-for="c in COMPANIES" :key="c.id" class="company-card" :style="{ borderLeft: `4px solid ${c.color}` }">
        <div class="co-head">
          <img :src="c.logo" alt="" style="height: 22px; object-fit: contain" />
          <span class="co-name">{{ c.name }}</span>
        </div>
        <div class="co-stats">
          <div>
            <div class="co-num">{{ shipments.filter((s) => s.companyId === c.id && s.status !== "completed").length }}</div>
            <div class="co-lbl">Active</div>
          </div>
          <div>
            <div class="co-num">{{ shipments.filter((s) => s.companyId === c.id).length }}</div>
            <div class="co-lbl">Shipments</div>
          </div>
          <div>
            <div class="co-num co-val" :style="{ color: c.text }">{{ fmtUsd(totalUsd(shipments.filter((s) => s.companyId === c.id))) }}</div>
            <div class="co-lbl">Total value (USD)</div>
          </div>
        </div>
      </div>
    </div>
    <p class="fx-note">
      USD totals use {{ fxLabel }}.
      <button class="link" @click="ratesOpen = true">View or edit rates</button>
    </p>

    <!-- Active / Closed stats -->
    <div class="stat-grid">
      <button class="stat-card" @click="emit('navigate', 'shipments', null, null)">
        <span class="stat-ic" style="background: #fef3c7; color: #b45309"><UiIcon name="package" :size="18" /></span>
        <span>
          <span class="stat-num">{{ activeCount }}</span>
          <span class="stat-lbl">Active shipments</span>
        </span>
      </button>
      <button class="stat-card" @click="emit('navigate', 'shipments', null, null)">
        <span class="stat-ic" style="background: #d1fae5; color: #047857"><UiIcon name="check" :size="18" /></span>
        <span>
          <span class="stat-num">{{ closedCount }}</span>
          <span class="stat-lbl">Closed shipments</span>
        </span>
      </button>
    </div>

    <!-- Active Pipeline -->
    <h2 class="pipe-title">Active pipeline</h2>
    <div class="pipe-list">
      <button v-for="s in pipeline" :key="s.id" class="pipe-row" @click="emit('navigate', 'shipments', 'detail', s.id)">
        <span style="min-width: 0; text-align: left">
          <span class="pipe-top">
            <span class="mono pipe-ref">{{ s.ref }}</span>
            <UiCompanyChip :id="s.companyId" />
            <span class="chip" style="background: #f1f5f9; color: #475569">{{ s.category }}</span>
          </span>
          <span class="pipe-desc">{{ s.description }}</span>
          <span class="pipe-meta">
            <span class="mi"><UiIcon name="factory" :size="12" /> {{ vendorName(s.vendorId) }}</span>
            <span v-if="s.shipperId" class="mi"><UiIcon name="ship" :size="12" /> {{ shipperName(s.shipperId) }}</span>
            <span v-if="s.eta" class="mi"><UiIcon name="calendar" :size="12" /> ETA {{ fmtEta(s.eta) }}</span>
          </span>
        </span>
        <span style="text-align: right; flex-shrink: 0">
          <UiStatusChip :status="s.status" />
          <span class="pipe-val num">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</span>
        </span>
      </button>
      <div v-if="!pipeline.length" class="empty">All shipments are completed. Nothing in the pipeline.</div>
    </div>

    <!-- Recent Activity -->
    <div class="act-head">
      <h2 class="pipe-title" style="margin: 0">Recent activity</h2>
      <button class="link" @click="toggleActivity">{{ showAllActivity ? "Show less" : "View all" }}</button>
    </div>
    <div class="act-list">
      <div v-for="a in activity" :key="a.id" class="act-row">
        <span class="act-detail">{{ a.detail }}</span>
        <span class="act-meta">{{ a.userName }} · {{ timeAgo(a.ts) }}</span>
      </div>
      <template v-if="activityLoading && !activity.length">
        <div v-for="n in 3" :key="n" class="act-row" aria-hidden="true"><div class="skel" style="width: 55%" /><div class="skel" style="width: 18%" /></div>
      </template>
      <div v-else-if="!activity.length" class="empty">No activity recorded yet</div>
    </div>

    <IfNewShipmentModal
      v-if="newShipment"
      @close="newShipment = false"
      @created="(id: string) => emit('navigate', 'shipments', 'detail', id)"
    />
    <IfFxRatesModal v-if="ratesOpen" @close="ratesOpen = false" />
  </div>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; animation: fadeIn .3s; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
.ph { font-size: 20px; font-weight: 800; }
.company-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 8px; }
@media (max-width: 900px) { .company-grid { grid-template-columns: 1fr; } }
.company-card { background: #fff; border-radius: 12px; padding: 16px 20px; border: 1px solid #eef2f6; }
.co-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.co-name { font-size: 15px; font-weight: 700; color: #0f172a; }
.co-stats { display: grid; grid-template-columns: 1fr 1fr 1.5fr; gap: 8px; align-items: end; }
.co-num { font-size: 19px; font-weight: 800; color: #0f172a; line-height: 1.2; }
.co-val { font-size: 15px; }
.co-lbl { font-size: 10px; color: #64748b; font-weight: 600; line-height: 1.4; }
.fx-note { font-size: 11.5px; color: #64748b; margin-bottom: 18px; }
.link { background: none; border: none; padding: 0; font: inherit; font-weight: 700; color: var(--primary); cursor: pointer; }
.link:hover { text-decoration: underline; }
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px; }
.stat-card {
  background: #fff; border-radius: 11px; padding: 14px 18px; border: 1px solid #eef2f6;
  display: flex; align-items: center; gap: 12px; cursor: pointer; font: inherit; text-align: left;
}
.stat-card:hover { border-color: #bfdbfe; }
.stat-ic { width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; }
.stat-num { display: block; font-size: 22px; font-weight: 800; color: #0f172a; }
.stat-lbl { display: block; font-size: 11px; color: #64748b; font-weight: 600; }
.pipe-title { margin: 0 0 12px; font-size: 14px; font-weight: 700; color: #334155; }
.pipe-list { display: grid; gap: 10px; margin-bottom: 26px; }
.pipe-row {
  background: #fff; border-radius: 11px; padding: 14px 18px; border: 1px solid #eef2f6; width: 100%;
  cursor: pointer; display: flex; align-items: center; justify-content: space-between; gap: 14px;
  transition: border-color .15s; font: inherit; color: inherit;
}
.pipe-row:hover { border-color: #bfdbfe; }
.pipe-top { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; flex-wrap: wrap; }
.pipe-ref { font-size: 11.5px; font-weight: 700; color: #1d4ed8; }
.pipe-desc { display: block; font-size: 13.5px; font-weight: 600; color: #0f172a; margin-bottom: 4px; }
.pipe-meta { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 11.5px; color: #64748b; }
.mi { display: inline-flex; align-items: center; gap: 4px; }
.pipe-val { display: block; font-size: 13.5px; font-weight: 700; margin-top: 5px; color: #0f172a; }
.empty { text-align: center; padding: 30px; color: #64748b; font-size: 13px; background: #fff; border-radius: 11px; border: 1px dashed #e2e8f0; }
.act-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; font-size: 12.5px; }
.act-list { background: #fff; border: 1px solid #eef2f6; border-radius: 11px; overflow: hidden; }
.act-row { display: flex; justify-content: space-between; gap: 12px; padding: 10px 16px; border-bottom: 1px solid #f1f5f9; }
.act-row:last-child { border-bottom: none; }
.act-detail { font-size: 12.5px; color: #334155; font-weight: 600; min-width: 0; }
.act-meta { font-size: 11px; color: #64748b; white-space: nowrap; }
.act-list .empty { border: none; }
@media (max-width: 640px) {
  .page { padding: 16px 14px 90px; }
  .stat-grid { grid-template-columns: 1fr 1fr; }
  .act-row { flex-direction: column; gap: 2px; }
  .pipe-row { flex-direction: column; align-items: stretch; }
  .pipe-row > span:last-child { display: flex; justify-content: space-between; align-items: center; text-align: left !important; }
  /* primary action stays reachable as a floating button */
  .fab-m { position: fixed; right: 16px; bottom: 18px; z-index: 30; border-radius: 999px; padding: 13px 18px; box-shadow: 0 8px 24px rgba(37,99,235,.35); }
}
</style>
