<script setup lang="ts">
// Budget vs actual for one project (naira): contract value from won quotes
// against what importing its goods has actually cost (goods + shipping + clearing).
const props = defineProps<{ budget: any | null }>();
const router = useRouter();
const b = computed(() => props.budget);
const short = (n: number) => {
  const a = Math.abs(n || 0);
  const s = a >= 1e9 ? (a / 1e9).toFixed(2) + "B" : a >= 1e6 ? (a / 1e6).toFixed(1) + "M" : a >= 1e3 ? Math.round(a / 1e3) + "K" : Math.round(a).toString();
  return (n < 0 ? "−₦" : "₦") + s;
};
const full = (n: number) => "₦" + Math.round(n || 0).toLocaleString("en-NG");
const used = computed(() => Math.min(100, Math.max(0, b.value?.usedPct ?? 0)));
const tone = computed(() => {
  const u = b.value?.usedPct ?? 0;
  return u > 100 ? "bad" : u > 85 ? "warn" : "ok";
});
</script>

<template>
  <section v-if="b" class="card bud" aria-labelledby="bud-t">
    <div class="bud-head">
      <h2 id="bud-t" class="bud-t">Budget vs actual</h2>
      <span class="hint">in naira</span>
    </div>

    <template v-if="b.contract > 0">
      <div class="kpis">
        <div><span class="k">Contract value</span><strong :title="full(b.contract)">{{ short(b.contract) }}</strong><small>won quotes, excl. VAT</small></div>
        <div><span class="k">Spent on imports</span><strong :title="full(b.spent)">{{ short(b.spent) }}</strong><small>{{ b.usedPct }}% of contract</small></div>
        <div :class="tone"><span class="k">Margin so far</span><strong :title="full(b.margin)">{{ short(b.margin) }}</strong><small>{{ b.marginPct }}% of contract</small></div>
      </div>
      <div class="bar" role="img" :aria-label="`${b.usedPct}% of the contract value spent on imports`">
        <span :class="tone" :style="{ width: used + '%' }" />
      </div>
      <p v-if="b.usedPct > 100" class="alert-bad">Import costs are above the contract value by {{ short(b.spent - b.contract) }}.</p>
      <p v-else-if="b.usedPct > 85" class="alert-warn">Over 85% of the contract value is already spent on imports.</p>
    </template>
    <p v-else class="empty">
      No won quote is linked to this project yet. Mark a quote <strong>Won</strong> and link it here to compare the contract value with what you spend.
      <template v-if="b.pendingValue"> Quotes still open for it: {{ short(b.pendingValue) }}.</template>
    </p>

    <div class="cols">
      <div>
        <div class="sub-t">Where the money went</div>
        <ul class="rows">
          <li><span>Goods (vendor orders)</span><span>{{ short(b.goods) }}</span></li>
          <li><span>Shipping</span><span>{{ short(b.shipping) }}</span></li>
          <li><span>Clearing</span><span>{{ short(b.clearing) }}</span></li>
          <li class="tot"><span>Landed cost</span><span>{{ short(b.spent) }}</span></li>
        </ul>
      </div>
      <div>
        <div class="sub-t">Vendors</div>
        <ul class="rows">
          <li><span>Paid so far</span><span>{{ short(b.vendorPaid) }}</span></li>
          <li><span>Still owed</span><span :class="{ owed: b.vendorOwed > 0 }">{{ short(b.vendorOwed) }}</span></li>
          <li v-if="b.estimatedCost"><span>Quoted cost <small>(incl. fabrication &amp; install)</small></span><span>{{ short(b.estimatedCost) }}</span></li>
        </ul>
      </div>
    </div>

    <div v-if="b.wonQuotes.length || b.pendingQuotes.length" class="qs">
      <div class="sub-t">Quotes</div>
      <button v-for="q in [...b.wonQuotes, ...b.pendingQuotes]" :key="q.id" class="q" @click="router.push(`/platform/quotes/${q.id}`)">
        <span class="mono">{{ q.number }}</span>
        <span class="st" :class="q.status">{{ q.status }}</span>
        <span class="qv">{{ short(q.subNgn) }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.bud { margin-bottom: 14px; display: grid; gap: 12px; }
.bud-head { display: flex; align-items: baseline; gap: 8px; }
.bud-t { font-size: 14px; font-weight: 800; color: #0f172a; }
.hint { font-size: 11.5px; color: #64748b; }
.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.kpis > div { display: flex; flex-direction: column; gap: 1px; padding: 10px 12px; border-radius: 10px; background: #f8fafc; }
.k { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: .5px; }
.kpis strong { font-size: 20px; font-weight: 800; color: #0f172a; font-variant-numeric: tabular-nums; }
.kpis small { font-size: 11.5px; color: #64748b; }
.kpis .ok strong { color: #047857; }
.kpis .warn strong { color: #b45309; }
.kpis .bad strong { color: #b91c1c; }
.bar { height: 8px; border-radius: 6px; background: #e2e8f0; overflow: hidden; }
.bar span { display: block; height: 100%; border-radius: 6px; }
.bar .ok { background: #10b981; }
.bar .warn { background: #f59e0b; }
.bar .bad { background: #dc2626; }
.alert-bad, .alert-warn { font-size: 12.5px; font-weight: 600; border-radius: 8px; padding: 7px 10px; }
.alert-bad { background: #fef2f2; color: #b91c1c; }
.alert-warn { background: #fffbeb; color: #92400e; }
.empty { font-size: 12.5px; color: #475569; background: #f8fafc; border-radius: 8px; padding: 10px 12px; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.sub-t { font-size: 11.5px; font-weight: 800; color: #334155; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 4px; }
.rows { list-style: none; padding: 0; margin: 0; display: grid; gap: 3px; }
.rows li { display: flex; justify-content: space-between; gap: 10px; font-size: 12.5px; color: #475569; }
.rows li span:last-child { color: #0f172a; font-variant-numeric: tabular-nums; font-weight: 600; }
.rows li.tot { border-top: 1px solid #e2e8f0; padding-top: 4px; margin-top: 2px; font-weight: 700; }
.rows small { color: #94a3b8; }
.owed { color: #b45309 !important; }
.qs { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.qs .sub-t { width: 100%; margin: 0; }
.q { display: inline-flex; align-items: center; gap: 8px; font: inherit; font-size: 12px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px 9px; cursor: pointer; }
.q:hover { border-color: #93c5fd; background: #eff6ff; }
.q .mono { font-weight: 700; color: #2563eb; }
.st { font-size: 10.5px; font-weight: 800; text-transform: capitalize; border-radius: 20px; padding: 1px 7px; background: #f1f5f9; color: #475569; }
.st.won { background: #dcfce7; color: #166534; }
.qv { font-weight: 700; color: #0f172a; }
@media (max-width: 640px) { .kpis, .cols { grid-template-columns: 1fr; } }
</style>
