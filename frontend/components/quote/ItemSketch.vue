<script setup lang="ts">
// Live outline of an item (and its composite elements) drawn to proportion, so a
// swapped width/height or a wrong panel count is obvious before the quote is sent.
const props = defineProps<{ item: any; subLabel?: (id: string) => string }>();

const frames = computed(() => {
  const it = props.item || {};
  const list = [{ w: Number(it.width) || 0, h: Number(it.height) || 0, sub: it.subTypeId || "" }];
  for (const el of it.elements || []) list.push({ w: Number(el.width) || 0, h: Number(el.height) || 0, sub: el.subTypeId || "" });
  return list;
});
const ready = computed(() => frames.value.every((f) => f.w > 0 && f.h > 0));

const BOX_W = 200, BOX_H = 120, PAD = 18;
const layout = computed(() => {
  const totalW = frames.value.reduce((a, f) => a + f.w, 0);
  const maxH = Math.max(...frames.value.map((f) => f.h));
  const k = Math.min((BOX_W - PAD * 2) / totalW, (BOX_H - PAD * 2) / maxH);
  let x = (BOX_W - totalW * k) / 2;
  return frames.value.map((f) => {
    const r = { x, y: (BOX_H - PAD) - f.h * k, w: f.w * k, h: f.h * k, f };
    x += f.w * k;
    return r;
  });
});

// panes: how many vertical divisions and what kind of opening
const kind = (sub: string) => {
  const m = sub.match(/_s(\d)$/);
  if (m) return { panes: Number(m[1]), type: "slide" };
  if (/_double$/.test(sub)) return { panes: 2, type: "hinge" };
  if (/_single$/.test(sub)) return { panes: 1, type: "hinge" };
  if (/cw_g$|str_g$/.test(sub)) return { panes: 3, type: "grid" };
  return { panes: 1, type: "fixed" };
};
const totalW = computed(() => frames.value.reduce((a, f) => a + f.w, 0));
const maxH = computed(() => Math.max(...frames.value.map((f) => f.h)));
</script>

<template>
  <div class="sk" :aria-label="ready ? `Outline ${totalW} by ${maxH} millimetres` : 'Outline appears once sizes are entered'" role="img">
    <svg v-if="ready" :viewBox="`0 0 ${BOX_W} ${BOX_H}`" width="100%" height="100%">
      <g v-for="(r, i) in layout" :key="i">
        <rect :x="r.x" :y="r.y" :width="r.w" :height="r.h" fill="#eff6ff" stroke="#1e3a8a" stroke-width="1.6" />
        <template v-for="p in kind(r.f.sub).panes - 1" :key="p">
          <line :x1="r.x + (r.w * p) / kind(r.f.sub).panes" :y1="r.y" :x2="r.x + (r.w * p) / kind(r.f.sub).panes" :y2="r.y + r.h" stroke="#1e3a8a" stroke-width="1" />
        </template>
        <template v-if="kind(r.f.sub).type === 'grid'">
          <line :x1="r.x" :y1="r.y + r.h / 2" :x2="r.x + r.w" :y2="r.y + r.h / 2" stroke="#1e3a8a" stroke-width="1" />
        </template>
        <!-- hinged: opening triangle per sash; sliding: arrow per pane -->
        <template v-for="p in kind(r.f.sub).panes" :key="'o' + p">
          <polyline
            v-if="kind(r.f.sub).type === 'hinge'"
            :points="`${r.x + (r.w * (p - 1)) / kind(r.f.sub).panes + 3},${r.y + 3} ${r.x + (r.w * (p - (p % 2 ? 0 : 1))) / kind(r.f.sub).panes + (p % 2 ? -3 : 3)},${r.y + r.h / 2} ${r.x + (r.w * (p - 1)) / kind(r.f.sub).panes + 3},${r.y + r.h - 3}`"
            fill="none" stroke="#60a5fa" stroke-width=".9" stroke-dasharray="3 2"
          />
          <path
            v-if="kind(r.f.sub).type === 'slide'"
            :d="`M${r.x + (r.w * (p - .5)) / kind(r.f.sub).panes - 6},${r.y + r.h / 2} h12 m-3,-3 l3,3 l-3,3`"
            fill="none" stroke="#60a5fa" stroke-width="1.1"
          />
        </template>
      </g>
      <text :x="BOX_W / 2" :y="BOX_H - 3" text-anchor="middle" font-size="9" fill="#475569">{{ totalW }} mm</text>
      <text :x="6" :y="BOX_H / 2" font-size="9" fill="#475569" :transform="`rotate(-90 6 ${BOX_H / 2})`" text-anchor="middle">{{ maxH }} mm</text>
    </svg>
    <div v-else class="sk-empty">Outline appears once width and height are entered</div>
  </div>
</template>

<style scoped>
.sk { width: 100%; aspect-ratio: 5 / 3; background: #fff; border: 1px solid #e2e8f0; border-radius: 9px; display: flex; align-items: center; justify-content: center; }
.sk-empty { font-size: 11px; color: #64748b; text-align: center; padding: 10px; line-height: 1.4; }
</style>
