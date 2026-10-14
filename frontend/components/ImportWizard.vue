<script setup lang="ts">
// Import from Excel/CSV in three steps: pick what, upload (template provided),
// check the preview (new / update / errors per row), import the valid rows.
const props = defineProps<{ kinds: { k: string; label: string; desc: string; icon: string }[]; start?: string }>();
const emit = defineEmits<{ (e: "imported", kind: string, result: any): void }>();
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request, download, saveBlob } = useApi();
const { fileToBase64 } = useConstants();

const kind = ref(props.start || "");
const file = ref<any>(null);
const preview = ref<any>(null);
const busy = ref<"" | "tpl" | "read" | "import">("");
const err = ref("");
const result = ref<any>(null);
const onlyErrors = ref(false);
const current = computed(() => props.kinds.find((x) => x.k === kind.value));

const pick = (k: string) => { kind.value = k; reset(); };
const reset = () => { file.value = null; preview.value = null; err.value = ""; result.value = null; onlyErrors.value = false; };
const getTemplate = async () => {
  busy.value = "tpl";
  try {
    const { blob, filename } = await download(`/api/import/${kind.value}/template`);
    saveBlob(blob, filename);
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    busy.value = "";
  }
};
const onFile = async (files: File[]) => {
  const f = files[0];
  if (!f) return;
  err.value = "";
  if (!/\.(xlsx|xlsm|csv|txt)$/i.test(f.name)) { err.value = "Use an Excel (.xlsx) or CSV file"; return; }
  if (f.size > 5 * 1024 * 1024) { err.value = "File is larger than 5 MB"; return; }
  busy.value = "read";
  try {
    file.value = { name: f.name, data: await fileToBase64(f) };
    preview.value = await request(`/api/import/${kind.value}/preview`, { method: "POST", body: { file: file.value } });
  } catch (e: any) {
    err.value = e.message;
    file.value = null;
  } finally {
    busy.value = "";
  }
};
const valid = computed(() => (preview.value ? preview.value.summary.create + preview.value.summary.update : 0));
const rows = computed(() => (preview.value?.rows || []).filter((r: any) => !onlyErrors.value || r.errors.length));
const shownCols = computed(() => (preview.value?.columns || []).slice(0, 5));
const doImport = async () => {
  busy.value = "import";
  try {
    result.value = await request(`/api/import/${kind.value}/commit`, { method: "POST", body: { file: file.value } });
    emit("imported", kind.value, result.value);
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    busy.value = "";
  }
};
</script>

<template>
  <div class="iw">
    <!-- 1. what -->
    <div class="kinds" role="radiogroup" aria-label="What to import">
      <button v-for="x in kinds" :key="x.k" type="button" role="radio" class="kind" :aria-checked="kind === x.k" @click="pick(x.k)">
        <span class="k-ic"><UiIcon :name="x.icon" :size="16" /></span>
        <span><strong>{{ x.label }}</strong><small>{{ x.desc }}</small></span>
      </button>
    </div>

    <template v-if="current">
      <!-- result -->
      <div v-if="result" class="done" role="status">
        <UiIcon name="check" :size="18" :stroke="3" />
        <div>
          <strong>{{ current.label }} imported</strong>
          <p>{{ result.created }} added · {{ result.updated }} updated<template v-if="result.skipped"> · {{ result.skipped }} skipped (had errors)</template></p>
        </div>
        <button class="btn btn-secondary btn-sm" @click="reset">Import another file</button>
      </div>

      <!-- 2. upload -->
      <div v-else-if="!preview" class="step">
        <div class="st-row">
          <span class="num">1</span>
          <div style="flex: 1">
            <strong>Fill in the template</strong>
            <p>It has the right column headers and an example row. Your own spreadsheet works too if its headers match.</p>
          </div>
          <button class="btn btn-secondary btn-sm" :disabled="busy === 'tpl'" @click="getTemplate"><UiIcon name="download" :size="13" /> {{ busy === "tpl" ? "Preparing…" : "Download template" }}</button>
        </div>
        <div class="st-row">
          <span class="num">2</span>
          <div style="flex: 1">
            <strong>Upload it</strong>
            <p>Excel (.xlsx) or CSV, up to 5,000 rows. Nothing is saved until you confirm the preview.</p>
          </div>
        </div>
        <UiUploadBox :label="busy === 'read' ? 'Reading file…' : `Upload ${current.label.toLowerCase()} file`" accept=".xlsx,.xlsm,.csv,text/csv" @files="onFile" />
        <p v-if="err" class="fe" role="alert">{{ err }}</p>
      </div>

      <!-- 3. preview -->
      <div v-else class="step">
        <div class="pv-head">
          <strong>{{ file?.name }}</strong>
          <span class="b new">{{ preview.summary.create }} new</span>
          <span class="b upd">{{ preview.summary.update }} update{{ preview.summary.update === 1 ? "" : "s" }}</span>
          <span v-if="preview.summary.errors" class="b bad">{{ preview.summary.errors }} with errors</span>
          <label v-if="preview.summary.errors" class="only"><input v-model="onlyErrors" type="checkbox" /> Only rows with errors</label>
        </div>
        <p v-if="preview.summary.errors" class="hint">Rows with errors are skipped. Fix them in your file and upload again, or import the rest now.</p>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead><tr><th>Row</th><th v-for="c in shownCols" :key="c">{{ c }}</th><th>Result</th></tr></thead>
            <tbody>
              <tr v-for="r in rows.slice(0, 300)" :key="r.row" :class="{ err: r.errors.length }">
                <td class="mono">{{ r.row }}</td>
                <td v-for="c in shownCols" :key="c">{{ r.values[c] }}</td>
                <td>
                  <span v-if="r.errors.length" class="errs">{{ r.errors.join(" · ") }}</span>
                  <span v-else class="b" :class="r.action === 'create' ? 'new' : 'upd'">{{ r.action === "create" ? "New" : "Update" }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="rows.length > 300" class="hint" style="padding: 8px">Showing the first 300 of {{ rows.length }} rows.</p>
          <p v-if="!rows.length" class="hint" style="padding: 12px">No rows to show.</p>
        </div>
        <div class="acts">
          <button class="btn btn-secondary" :disabled="!!busy" @click="reset">Choose another file</button>
          <button class="btn btn-accent" :disabled="!valid || !!busy" @click="doImport">
            {{ busy === "import" ? "Importing…" : valid ? `Import ${valid} row${valid === 1 ? "" : "s"}` : "Nothing to import" }}
          </button>
        </div>
      </div>
    </template>
    <p v-else class="hint">Choose what you want to bring in.</p>
  </div>
</template>

<style scoped>
.iw { display: grid; gap: 14px; }
.kinds { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }
.kind { display: flex; gap: 10px; align-items: flex-start; text-align: left; font: inherit; padding: 11px 12px; border: 1.5px solid #e2e8f0; border-radius: 10px; background: #fff; cursor: pointer; color: #0f172a; }
.kind[aria-checked="true"] { border-color: #2563eb; box-shadow: 0 0 0 3px #dbeafe; }
.kind span:last-child { display: flex; flex-direction: column; gap: 2px; }
.kind strong { font-size: 13.5px; }
.kind small { font-size: 11.5px; color: #64748b; line-height: 1.35; }
.k-ic { width: 30px; height: 30px; border-radius: 8px; background: #eff6ff; color: #2563eb; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.step { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; display: grid; gap: 12px; }
.st-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.st-row strong { font-size: 13.5px; }
.st-row p { font-size: 12.5px; color: #64748b; margin-top: 2px; }
.num { width: 26px; height: 26px; border-radius: 50%; background: #1d4ed8; color: #fff; font-size: 12px; font-weight: 800; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.fe { font-size: 12.5px; color: #b91c1c; font-weight: 600; }
.hint { font-size: 12px; color: #64748b; }
.pv-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.b { font-size: 11px; font-weight: 800; border-radius: 20px; padding: 2px 9px; white-space: nowrap; }
.b.new { background: #dcfce7; color: #166534; }
.b.upd { background: #dbeafe; color: #1e40af; }
.b.bad { background: #fee2e2; color: #b91c1c; }
.only { margin-left: auto; display: flex; gap: 6px; align-items: center; font-size: 12.5px; font-weight: 600; color: #334155; }
.tbl-wrap { overflow: auto; max-height: 420px; border: 1px solid #e2e8f0; border-radius: 9px; }
.tbl { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.tbl th { position: sticky; top: 0; background: #f8fafc; text-align: left; padding: 7px 9px; font-size: 11px; text-transform: uppercase; letter-spacing: .4px; color: #475569; border-bottom: 1px solid #e2e8f0; white-space: nowrap; }
.tbl td { padding: 6px 9px; border-bottom: 1px solid #f1f5f9; vertical-align: top; max-width: 240px; overflow: hidden; text-overflow: ellipsis; }
.tbl tr.err td { background: #fff7f7; }
.errs { color: #b91c1c; font-weight: 600; font-size: 12px; white-space: normal; }
.acts { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.done { display: flex; gap: 12px; align-items: center; background: #f0fdf4; border: 1px solid #86efac; border-radius: 12px; padding: 14px 16px; color: #166534; flex-wrap: wrap; }
.done div { flex: 1; }
.done strong { font-size: 14px; color: #14532d; }
.done p { font-size: 12.5px; margin-top: 2px; }
</style>
