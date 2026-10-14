<script setup lang="ts">
// PDF Design (admin): how the client quotation PDF looks. Edits preview live
// against the latest quote (rendered by the same WeasyPrint engine as the real
// export) and only apply to downloads once saved.
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();
const { confirm } = useConfirm();
const user = useAuth().user;
const isAdmin = computed(() => user.value?.platformRole === "admin");
const token = useCookie<string | null>("interdec_token");
const config = useRuntimeConfig();

const defaults = ref<any>(null);
const d = ref<any>(null);
const original = ref("");
const loaded = ref(false);
const saving = ref(false);

const clone = (v: any) => JSON.parse(JSON.stringify(v ?? null));
const merge = (saved: any) => {
  const base = clone(defaults.value);
  const out = { ...base, ...(saved || {}) };
  out.show = { ...base.show, ...((saved || {}).show || {}) };
  return out;
};
const load = async () => {
  try {
    const [def, cat] = await Promise.all([request("/api/quotes/pdf/defaults"), request("/api/quotes/catalog")]);
    defaults.value = def.design;
    d.value = merge(cat.values?.pdfDesign);
  } catch (e: any) {
    notify(e.message, "error");
    return;
  }
  original.value = JSON.stringify(d.value);
  loaded.value = true;
  refresh();
};
onMounted(load);
const dirty = computed(() => loaded.value && JSON.stringify(d.value) !== original.value);

// ---- live preview (debounced; latest request wins) ----
const pdfUrl = ref("");
const previewErr = ref("");
const previewing = ref(false);
let timer: any = null;
let seq = 0;
const refresh = () => {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const my = ++seq;
    previewing.value = true;
    try {
      const blob = await $fetch<Blob>("/api/quotes/pdf/preview", {
        baseURL: config.public.apiBase as string, method: "POST", body: { design: d.value },
        headers: token.value ? { Authorization: `Bearer ${token.value}` } : {}, responseType: "blob",
      });
      if (my !== seq) return;
      if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value);
      pdfUrl.value = URL.createObjectURL(blob) + "#toolbar=0&navpanes=0&view=FitH";
      previewErr.value = "";
    } catch (e: any) {
      if (my !== seq) return;
      let msg = e?.message || "Preview failed";
      try { const b = e?.data instanceof Blob ? JSON.parse(await e.data.text()) : e?.data; if (b?.detail) msg = b.detail; } catch { /* keep */ }
      previewErr.value = msg;
    } finally {
      if (my === seq) previewing.value = false;
    }
  }, 600);
};
watch(() => JSON.stringify(d.value), () => loaded.value && refresh());
onUnmounted(() => { clearTimeout(timer); if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value); });

// ---- logo ----
const MAX_LOGO = 600 * 1024;
const logoInput = ref<HTMLInputElement | null>(null);
const pickLogo = () => logoInput.value?.click();
const onLogo = (e: Event) => {
  const f = (e.target as HTMLInputElement).files?.[0];
  (e.target as HTMLInputElement).value = "";
  if (!f) return;
  if (!/^image\/(png|jpeg|svg\+xml|webp|gif)$/.test(f.type)) return notify("Use a PNG, JPG, SVG or WebP image", "error");
  if (f.size > MAX_LOGO) return notify("Logo must be smaller than 600 KB", "error");
  const r = new FileReader();
  r.onload = () => { d.value.logo = String(r.result); };
  r.readAsDataURL(f);
};

// ---- options ----
const LAYOUTS = [
  { k: "classic", label: "Classic", hint: "Logo left, rule under the header" },
  { k: "banner", label: "Banner", hint: "Full-width colour header" },
  { k: "minimal", label: "Minimal", hint: "Light lines, no fills" },
];
const FONTS = [
  { k: "sans", label: "Sans (DejaVu)" }, { k: "arial", label: "Arial-like" },
  { k: "serif", label: "Serif (DejaVu)" }, { k: "times", label: "Times-like" },
];
const SHOW = [
  { k: "specs", label: "Glass and finish details" }, { k: "size", label: "Size column" },
  { k: "position", label: "Position (W1, D2…)" }, { k: "sketch", label: "Item sketches" },
  { k: "unitPrice", label: "Unit price column" }, { k: "salesPerson", label: "Contact person" },
  { k: "paymentTerms", label: "Payment terms" }, { k: "terms", label: "Terms & conditions" },
  { k: "bank", label: "Bank details" }, { k: "signature", label: "Signature lines" },
  { k: "pageNumbers", label: "Page numbers" },
];
const HEX = /^#[0-9a-fA-F]{6}$/;
const colorErr = computed(() => !HEX.test(d.value?.brandColor || "") || !HEX.test(d.value?.accentColor || ""));

const save = async () => {
  if (colorErr.value) return notify("Colours must look like #1F3864", "error");
  saving.value = true;
  try {
    await request("/api/quotes/catalog/pdfDesign", { method: "PUT", body: { value: d.value } });
    original.value = JSON.stringify(d.value);
    notify("PDF design saved. Every quote PDF uses it from now on.");
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    saving.value = false;
  }
};
const discard = async () => {
  if (await confirm({ title: "Discard changes?", message: "The design goes back to the last saved version.", confirmLabel: "Discard", danger: true })) {
    d.value = JSON.parse(original.value);
  }
};
const resetDefaults = async () => {
  if (await confirm({ title: "Reset to the default design?", message: "Company details, logo, colours and options go back to the defaults. Nothing is saved until you click Save.", confirmLabel: "Reset", danger: true })) {
    d.value = clone(defaults.value);
  }
};

// leaving with unsaved edits asks first
const router = useRouter();
const offGuard = router.beforeEach(async () =>
  !dirty.value || saving.value || (await confirm({ title: "Leave without saving?", message: "Your PDF design changes haven't been saved.", confirmLabel: "Leave without saving", cancelLabel: "Keep editing", danger: true }))
);
const onUnload = (e: BeforeUnloadEvent) => { if (dirty.value) { e.preventDefault(); e.returnValue = ""; } };
onMounted(() => window.addEventListener("beforeunload", onUnload));
onUnmounted(() => { offGuard(); window.removeEventListener("beforeunload", onUnload); });
</script>

<template>
  <div class="wrap">
    <div v-if="!isAdmin" class="alert" role="alert">Only platform admins can change the PDF design.</div>
    <template v-else>
      <div class="head">
        <div>
          <h1 class="title">PDF Design</h1>
          <p class="sub">How quotation PDFs look to your clients. The preview uses your latest quote; costs and markup never appear.</p>
        </div>
        <button class="btn btn-secondary" :disabled="!loaded" @click="resetDefaults">Reset to default</button>
      </div>

      <div v-if="!loaded" class="skel-card" aria-busy="true"><div class="skel" style="width: 40%" /><div class="skel" /><div class="skel" /></div>
      <div v-else class="cols">
        <!-- settings -->
        <div class="form">
          <section class="card">
            <h2 class="card-t">Company</h2>
            <div class="logo-row">
              <div class="logo-box" :class="{ empty: !d.logo }">
                <img v-if="d.logo" :src="d.logo" alt="Logo" />
                <span v-else>No logo</span>
              </div>
              <div class="logo-acts">
                <input ref="logoInput" type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp" hidden @change="onLogo" />
                <button class="btn btn-secondary btn-sm" @click="pickLogo"><UiIcon name="upload" :size="13" /> {{ d.logo ? "Replace logo" : "Upload logo" }}</button>
                <button v-if="d.logo" class="btn btn-ghost btn-sm" @click="d.logo = ''">Remove</button>
                <span class="hint">PNG, JPG or SVG, up to 600 KB</span>
              </div>
            </div>
            <label v-if="d.logo" class="f">
              <span>Logo height <span class="hint">{{ d.logoHeight }} px</span></span>
              <input v-model.number="d.logoHeight" type="range" min="20" max="120" step="2" />
            </label>
            <div class="g2">
              <label class="f"><span>Company name</span><input v-model="d.companyName" class="inp" /></label>
              <label class="f"><span>Tagline</span><input v-model="d.tagline" class="inp" placeholder="e.g. Aluminium & Glass Systems" /></label>
            </div>
            <label class="f"><span>Address</span><textarea v-model="d.address" class="inp" rows="2" placeholder="Street, city" /></label>
            <div class="g3">
              <label class="f"><span>Phone</span><input v-model="d.phone" class="inp" /></label>
              <label class="f"><span>Email</span><input v-model="d.email" class="inp" /></label>
              <label class="f"><span>Website</span><input v-model="d.website" class="inp" /></label>
            </div>
            <label class="f"><span>Registration / tax number <span class="hint">optional</span></span><input v-model="d.taxId" class="inp" placeholder="e.g. RC 123456 · TIN 0000-0000" /></label>
          </section>

          <section class="card">
            <h2 class="card-t">Look</h2>
            <span class="lbl">Header style</span>
            <div class="layouts" role="radiogroup" aria-label="Header style">
              <button
                v-for="l in LAYOUTS" :key="l.k" type="button" role="radio" class="lay" :aria-checked="d.layout === l.k"
                @click="d.layout = l.k"
              >
                <span class="lay-pic" :class="l.k">
                  <i class="h" :style="{ background: l.k === 'banner' ? d.brandColor : 'transparent', borderColor: d.brandColor }" />
                  <i class="t" :style="{ background: l.k === 'minimal' ? 'transparent' : d.brandColor, borderColor: d.brandColor }" />
                  <i class="r" /><i class="r" /><i class="r" />
                </span>
                <strong>{{ l.label }}</strong>
                <span class="hint">{{ l.hint }}</span>
              </button>
            </div>
            <div class="g2" style="margin-top: 12px">
              <label class="f"><span>Main colour</span>
                <span class="color"><input v-model="d.brandColor" type="color" aria-label="Main colour picker" /><input v-model="d.brandColor" class="inp" maxlength="7" :aria-invalid="!/^#[0-9a-fA-F]{6}$/.test(d.brandColor) || undefined" /></span>
              </label>
              <label class="f"><span>Accent colour</span>
                <span class="color"><input v-model="d.accentColor" type="color" aria-label="Accent colour picker" /><input v-model="d.accentColor" class="inp" maxlength="7" :aria-invalid="!/^#[0-9a-fA-F]{6}$/.test(d.accentColor) || undefined" /></span>
              </label>
              <label class="f"><span>Font</span>
                <select v-model="d.font" class="inp"><option v-for="f in FONTS" :key="f.k" :value="f.k">{{ f.label }}</option></select>
              </label>
              <label class="f"><span>Paper size</span>
                <select v-model="d.paper" class="inp"><option value="A4">A4</option><option value="Letter">US Letter</option></select>
              </label>
            </div>
          </section>

          <section class="card">
            <h2 class="card-t">Wording</h2>
            <label class="f"><span>Document title</span><input v-model="d.title" class="inp" placeholder="QUOTATION" /></label>
            <label class="f"><span>Opening line <span class="hint">above the items</span></span><textarea v-model="d.intro" class="inp" rows="2" /></label>
            <label class="f"><span>Footer <span class="hint">bottom of every page</span></span><input v-model="d.footerText" class="inp" maxlength="200" /></label>
            <label class="f"><span>Bank details</span><textarea v-model="d.bankDetails" class="inp" rows="3" placeholder="Bank name&#10;Account name&#10;Account number" /></label>
            <div class="g2">
              <label class="f"><span>Signed by</span><input v-model="d.signatureName" class="inp" placeholder="Name" /></label>
              <label class="f"><span>Their title</span><input v-model="d.signatureTitle" class="inp" placeholder="e.g. Sales Manager" /></label>
            </div>
            <p class="hint">Payment terms and terms &amp; conditions come from the Rate Card.</p>
          </section>

          <section class="card">
            <h2 class="card-t">Show on the PDF</h2>
            <div class="checks">
              <label v-for="o in SHOW" :key="o.k" class="chk"><input v-model="d.show[o.k]" type="checkbox" /> {{ o.label }}</label>
            </div>
          </section>
        </div>

        <!-- preview -->
        <div class="pv">
          <div class="pv-head">
            <span class="pv-t">Preview</span>
            <span v-if="previewing" class="pv-s">Updating…</span>
            <span v-else-if="dirty" class="pv-s warn">Unsaved: downloads still use the saved design</span>
            <span v-else class="pv-s">Matches what clients receive</span>
          </div>
          <div class="pv-frame" :class="{ busy: previewing }">
            <p v-if="previewErr" class="pv-err" role="alert">{{ previewErr }}</p>
            <iframe v-else-if="pdfUrl" :src="pdfUrl" title="PDF preview" />
            <div v-else class="pv-empty">Preparing preview…</div>
          </div>
          <a v-if="pdfUrl && !previewErr" class="pv-open" :href="pdfUrl.split('#')[0]" target="_blank" rel="noopener">Open preview in a new tab</a>
        </div>
      </div>

      <div v-if="dirty" class="savebar" role="region" aria-label="Unsaved changes">
        <span>Unsaved design changes</span>
        <div style="display: flex; gap: 8px">
          <button class="btn btn-secondary" :disabled="saving" @click="discard">Discard</button>
          <button class="btn btn-accent" :disabled="saving" @click="save">{{ saving ? "Saving…" : "Save design" }}</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.wrap { padding: 22px 22px 110px; max-width: 1400px; margin: 0 auto; }
.head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.title { font-size: 20px; font-weight: 800; color: #0f172a; }
.sub { font-size: 12.5px; color: #475569; margin-top: 4px; max-width: 620px; }
.alert { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; border-radius: 9px; padding: 12px 14px; font-size: 12.5px; font-weight: 600; }
.cols { display: grid; grid-template-columns: minmax(340px, 1fr) minmax(380px, 1.1fr); gap: 16px; align-items: start; }
.form { display: grid; gap: 12px; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; display: grid; gap: 12px; }
.card-t { font-size: 13px; font-weight: 800; color: #0f172a; text-transform: uppercase; letter-spacing: .6px; }
.f { display: flex; flex-direction: column; gap: 5px; font-size: 12px; font-weight: 700; color: #334155; }
.lbl { font-size: 12px; font-weight: 700; color: #334155; }
.hint { font-size: 11.5px; color: #64748b; font-weight: 500; }
.g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.g3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
textarea.inp { resize: vertical; }
.logo-row { display: flex; gap: 14px; align-items: center; }
.logo-box { width: 140px; height: 70px; border: 1px solid #e2e8f0; border-radius: 9px; display: flex; align-items: center; justify-content: center; background: #f8fafc; padding: 6px; flex-shrink: 0; }
.logo-box img { max-width: 100%; max-height: 100%; object-fit: contain; }
.logo-box.empty { border-style: dashed; color: #94a3b8; font-size: 12px; font-weight: 600; }
.logo-acts { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.logo-acts .hint { flex-basis: 100%; }
input[type="range"] { accent-color: #2563eb; }
.layouts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.lay {
  display: flex; flex-direction: column; gap: 4px; align-items: flex-start; text-align: left; padding: 10px; font: inherit; font-size: 12.5px;
  border: 1.5px solid #e2e8f0; border-radius: 10px; background: #fff; cursor: pointer; color: #0f172a;
}
.lay[aria-checked="true"] { border-color: #2563eb; box-shadow: 0 0 0 3px #dbeafe; }
.lay .hint { font-size: 11px; }
.lay-pic { width: 100%; height: 58px; border: 1px solid #e2e8f0; border-radius: 6px; padding: 0 6px 6px; display: flex; flex-direction: column; gap: 4px; background: #fff; overflow: hidden; }
.lay-pic i { display: block; }
.lay-pic .h { height: 14px; margin: 0 -6px; border-bottom: 2px solid; }
.lay-pic.banner .h { height: 16px; border: none; }
.lay-pic.minimal .h { border-bottom-width: 1px; border-color: #cbd5e1 !important; }
.lay-pic .t { height: 7px; border: 1px solid; border-radius: 2px; }
.lay-pic .r { height: 4px; background: #e2e8f0; border-radius: 2px; }
.color { display: flex; gap: 6px; }
.color input[type="color"] { width: 40px; height: 38px; padding: 2px; border: 1.5px solid #e2e8f0; border-radius: 8px; background: #fff; cursor: pointer; flex-shrink: 0; }
.color .inp[aria-invalid="true"] { border-color: #dc2626; }
.checks { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 14px; }
.chk { display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 600; color: #334155; cursor: pointer; min-height: 28px; }
.chk input { width: 16px; height: 16px; accent-color: #2563eb; }
.pv { position: sticky; top: 16px; display: flex; flex-direction: column; gap: 8px; }
.pv-head { display: flex; align-items: baseline; gap: 10px; }
.pv-t { font-size: 13px; font-weight: 800; color: #0f172a; text-transform: uppercase; letter-spacing: .6px; }
.pv-s { font-size: 12px; color: #64748b; font-weight: 600; }
.pv-s.warn { color: #b45309; }
.pv-frame { height: calc(100vh - 150px); min-height: 520px; background: #e2e8f0; border: 1px solid #cbd5e1; border-radius: 12px; overflow: hidden; transition: opacity .2s; }
.pv-frame.busy { opacity: .6; }
.pv-frame iframe { width: 100%; height: 100%; border: 0; background: #fff; }
.pv-empty, .pv-err { padding: 40px 20px; text-align: center; color: #64748b; font-size: 13px; }
.pv-err { color: #b91c1c; font-weight: 600; }
.pv-open { font-size: 12px; font-weight: 700; color: #2563eb; align-self: flex-end; }
.savebar {
  position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); z-index: 40; width: min(560px, calc(100% - 32px));
  display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px 10px 18px;
  background: #0f172a; color: #fff; border-radius: 12px; box-shadow: 0 16px 40px rgba(15,23,42,.3); font-size: 13.5px;
}
.savebar .btn-secondary { background: transparent; color: #fff; border-color: #475569; }
.skel-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; display: grid; gap: 10px; }
@media (max-width: 1100px) { .cols { grid-template-columns: 1fr; } .pv { position: static; } .pv-frame { height: 70vh; } }
@media (max-width: 560px) { .g2, .g3, .checks, .layouts { grid-template-columns: 1fr; } .logo-row { flex-direction: column; align-items: flex-start; } }
</style>
