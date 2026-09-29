<script setup lang="ts">
// Dashboard — company cards, active/closed stats, active pipeline (mirrors original)
const emit = defineEmits<{ (e: "navigate", p: string, d?: string | null, id?: string | null): void }>();
const { shipments, vendorName, shipperName } = useData();
const { user } = useAuth();
const { COMPANIES, STATUS_LABELS, STATUS_COLORS, STATUS_ORDER, COUNTRY_FLAGS } = useConstants();

const role = computed(() => user.value?.apps?.importflow?.role || "viewer");
const canEdit = computed(() => role.value === "admin" || role.value === "user");

const toUsd = (s: any) => (s.value || 0) * (DEFAULT_RATES[s.currency] || 1);
const totalUsd = (list: any[]) => list.reduce((a, s) => a + toUsd(s), 0);
const fmtUsd = (n: number) => "$ " + Math.round(n).toLocaleString();

const activeCount = computed(() => shipments.value.filter((s) => s.status !== "completed").length);
const closedCount = computed(() => shipments.value.filter((s) => s.status === "completed").length);

const pipeline = computed(() =>
  shipments.value
    .filter((s) => s.status !== "completed")
    .sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status))
);

const newShipment = ref(false);
</script>

<template>
  <div class="page">
    <div class="head">
      <h2>Dashboard</h2>
      <button v-if="canEdit" class="btn btn-accent" @click="newShipment = true">＋ New Shipment</button>
    </div>

    <!-- Company cards -->
    <div class="company-grid">
      <div
        v-for="c in COMPANIES"
        :key="c.id"
        class="company-card"
        :style="{ border: `1.5px solid ${c.color}20`, borderLeft: `4px solid ${c.color}` }"
      >
        <div class="co-head">
          <img :src="c.logo" :alt="c.name" style="height: 24px; object-fit: contain" />
          <span class="co-name">{{ c.name }}</span>
        </div>
        <div class="co-stats">
          <div>
            <div class="co-num" :style="{ color: c.color }">
              {{ shipments.filter((s) => s.companyId === c.id && s.status !== "completed").length }}
            </div>
            <div class="co-lbl">Active</div>
          </div>
          <div>
            <div class="co-num" style="color: #334155">
              {{ shipments.filter((s) => s.companyId === c.id).length }}
            </div>
            <div class="co-lbl">Shipments</div>
          </div>
          <div style="grid-column: span 1.4">
            <div class="co-num co-val" :style="{ color: c.color }">
              {{ fmtUsd(totalUsd(shipments.filter((s) => s.companyId === c.id))) }}
            </div>
            <div class="co-lbl">Total Value (USD)</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Active / Closed stats -->
    <div class="stat-grid">
      <div class="stat-card" :style="{ borderLeft: '4px solid #f59e0b' }">
        <div class="stat-ic" style="background: #fef3c7">📦</div>
        <div>
          <div class="stat-num">{{ activeCount }}</div>
          <div class="stat-lbl">Active Shipments</div>
        </div>
      </div>
      <div class="stat-card" :style="{ borderLeft: '4px solid #10b981' }">
        <div class="stat-ic" style="background: #d1fae5">✅</div>
        <div>
          <div class="stat-num">{{ closedCount }}</div>
          <div class="stat-lbl">Closed Shipments</div>
        </div>
      </div>
    </div>

    <!-- Active Pipeline -->
    <h3 class="pipe-title">Active Pipeline</h3>
    <div class="pipe-list">
      <div
        v-for="s in pipeline"
        :key="s.id"
        class="pipe-row"
        @click="emit('navigate', 'shipments', 'detail', s.id)"
      >
        <div style="min-width: 0">
          <div class="pipe-top">
            <span class="mono pipe-ref">{{ s.ref }}</span>
            <UiCompanyChip :id="s.companyId" />
            <span class="chip" style="background: #f1f5f9; color: #475569">{{ s.category }}</span>
          </div>
          <div class="pipe-desc">{{ s.description }}</div>
          <div class="pipe-meta">
            🏭 {{ vendorName(s.vendorId) }}
            <template v-if="s.shipperId"> · 🚢 {{ shipperName(s.shipperId) }}</template>
            <template v-if="s.eta"> · 📅 ETA: <strong class="mono" style="color: #0ea5e9">{{ s.eta }}</strong></template>
          </div>
        </div>
        <div style="text-align: right; flex-shrink: 0">
          <UiStatusChip :status="s.status" />
          <div class="mono pipe-val">{{ s.currency }} {{ (s.value || 0).toLocaleString() }}</div>
        </div>
      </div>
      <div v-if="!pipeline.length" class="empty">🎉 All shipments completed — no active pipeline</div>
    </div>

    <IfNewShipmentModal v-if="newShipment" @close="newShipment = false" />
  </div>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 22px 26px; animation: fadeIn .3s; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
h2 { font-size: 20px; font-weight: 800; }
.company-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 20px; }
@media (max-width: 900px) { .company-grid { grid-template-columns: 1fr; } }
.company-card { background: #fff; border-radius: 12px; padding: 18px 20px; box-shadow: 0 1px 3px rgba(0,0,0,.03); }
.co-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.co-name { font-size: 15px; font-weight: 700; color: #0f172a; }
.co-stats { display: grid; grid-template-columns: 1fr 1fr 1.5fr; gap: 8px; align-items: end; }
.co-num { font-size: 18px; font-weight: 700; font-family: "JetBrains Mono", monospace; line-height: 1.2; }
.co-val { font-size: 14px; }
.co-lbl { font-size: 9px; color: #94a3b8; font-weight: 600; text-transform: uppercase; line-height: 1.4; }
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 22px; }
.stat-card {
  background: #fff; border-radius: 11px; padding: 16px 18px; border: 1px solid #f1f5f9;
  display: flex; align-items: center; gap: 12px;
}
.stat-ic { width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 17px; }
.stat-num { font-size: 22px; font-weight: 800; font-family: "JetBrains Mono", monospace; }
.stat-lbl { font-size: 10.5px; color: #94a3b8; font-weight: 600; text-transform: uppercase; }
.pipe-title { margin: 0 0 12px; font-size: 14px; font-weight: 700; color: #475569; }
.pipe-list { display: grid; gap: 10px; margin-bottom: 22px; }
.pipe-row {
  background: #fff; border-radius: 11px; padding: 14px 18px; border: 1px solid #f1f5f9;
  cursor: pointer; display: flex; align-items: center; justify-content: space-between; gap: 14px;
  transition: all .15s;
}
.pipe-row:hover { border-color: #ddd6fe; }
.pipe-top { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; flex-wrap: wrap; }
.pipe-ref { font-size: 11.5px; font-weight: 700; color: #3b82f6; }
.pipe-desc { font-size: 13px; font-weight: 600; color: #0f172a; margin-bottom: 3px; }
.pipe-meta { font-size: 11px; color: #94a3b8; }
.pipe-val { font-size: 13.5px; font-weight: 700; margin-top: 4px; }
.empty { text-align: center; padding: 34px; color: #94a3b8; font-size: 13px; background: #fff; border-radius: 11px; border: 1px dashed #e2e8f0; }
</style>
