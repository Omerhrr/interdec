<script setup lang="ts">
// Rate Card (admin): every price the quote engine uses, in collapsible sections.
// Lists (glass types and thicknesses, colours, ACP panels, extra charges) can be
// extended here; anything added flows straight into the quote editor.
const notify = inject<(m: string, t?: string) => void>("notify")!;
const { request } = useApi();
const { confirm } = useConfirm();
const user = useAuth().user;
const showImport = ref(false);
const PRICE_KINDS = [
  { k: "glass", label: "Glass prices", desc: "Type, thickness, price per m²", icon: "grid" },
  { k: "acp", label: "ACP panels", desc: "Panel name and price per m²", icon: "grid" },
  { k: "hardware", label: "Hardware", desc: "Item, unit and price", icon: "settings" },
];
const isAdmin = computed(() => user.value?.platformRole === "admin");

const values = ref<any>({});
const rates = ref<any>({});
const settings = ref<any>({});
const gc = ref<any>({ types: [], thicknesses: {}, basePrices: {}, colours: [] });
const mosqRates = ref<Record<string, number>>({});
const acp = ref<any[]>([]);
const hw = ref<any[]>([]);
const cur = ref<Record<string, string>>({}); // price path -> currency code (missing = NGN)
// products and their window/door types (pricing rules per type)
const prods = ref<any[]>([]);
const subs = ref<Record<string, any[]>>({});
const sf = ref<Record<string, number>>({});
const kits = ref<Record<string, { id: string; q: number }[]>>({});
// custom names for sections and fixed fields ({sections: {key: name}, fields: {key: name}})
const labels = ref<{ sections: Record<string, string>; fields: Record<string, string> }>({ sections: {}, fields: {} });
const SECTION_NAMES: Record<string, string> = {
  rates: "Materials and labour", settings: "Markup, VAT and terms", glass: "Glass prices", colours: "Glass colours",
  acp: "ACP cladding panels", extras: "Extra charges", types: "Products and types", hw: "Hardware", mosq: "Mosquito nets",
};
const SETTING_NAMES: Record<string, string> = {
  defaultMarkup: "Default markup", minMarkup: "Minimum markup", vatRate: "VAT", validity: "Quote validity",
  paymentTerms: "Payment terms", tcs: "Terms and conditions",
};
const secName = (k: string) => labels.value.sections[k] || SECTION_NAMES[k];
const fieldName = (k: string, dflt: string) => labels.value.fields[k] || dflt;
const setSection = (k: string, v: string) => { if (v && v !== SECTION_NAMES[k]) labels.value.sections[k] = v; else delete labels.value.sections[k]; };
const setField = (k: string, dflt: string, v: string) => { if (v && v !== dflt) labels.value.fields[k] = v; else delete labels.value.fields[k]; };
// renaming a mosquito-net row renames the type itself (same record as in Products and types)
const renameType = (stid: string, v: string) => {
  for (const pid of Object.keys(subs.value)) {
    const t = (subs.value[pid] || []).find((x: any) => x.id === stid);
    if (t) {
      if (!v) return notify("A type needs a name", "error");
      if ((subs.value[pid] || []).some((x: any) => x.id !== stid && x.label.toLowerCase() === v.toLowerCase())) return notify(`${v} already exists`, "error");
      t.label = v;
    }
  }
};
const renameProduct = (pid: string, v: string) => {
  if (!v) return notify("A product needs a name", "error");
  const p = prods.value.find((x: any) => x.id === pid);
  if (p) p.label = v;
};
const fx = ref<Record<string, number>>({ NGN: 1 }); // naira per 1 unit
const saving = ref(false);
const loaded = ref(false);
const query = ref("");
const tried = ref(false);
const original = ref("");

const clone = (v: any) => JSON.parse(JSON.stringify(v ?? null));
const state = () => ({ r: rates.value, s: settings.value, g: gc.value, m: mosqRates.value, a: acp.value, h: hw.value, k: cur.value,
  p: prods.value, t: subs.value, f: sf.value, w: kits.value, l: labels.value });
const snapshot = () => JSON.stringify(state());
const load = async () => {
  try {
    const cat = await request("/api/quotes/catalog");
    values.value = cat.values || {};
    fx.value = cat.fx || { NGN: 1 };
  } catch (e: any) {
    notify(e.message, "error");
    values.value = {};
  }
  const v = values.value;
  rates.value = clone(v.rates || {});
  rates.value.brandRates = rates.value.brandRates || { EUROTEC: 3400, CORTIZO: 3400, DEFAULT: 3400 };
  rates.value.extras = rates.value.extras || [];
  settings.value = clone(v.settings || {});
  gc.value = clone(v.gc || { types: [], thicknesses: {}, basePrices: {}, colours: [] });
  gc.value.thicknesses = gc.value.thicknesses || {};
  gc.value.basePrices = gc.value.basePrices || {};
  mosqRates.value = clone(v.mosqRates || {});
  acp.value = clone(v.acpPanels || []);
  hw.value = clone(v.hwItems || []);
  cur.value = clone(v.currencies || {});
  prods.value = clone(v.products || []);
  subs.value = clone(v.subs || {});
  sf.value = clone(v.sf || {});
  kits.value = clone(v.hwKits || {});
  labels.value = { sections: { ...(v.rateCardLabels?.sections || {}) }, fields: { ...(v.rateCardLabels?.fields || {}) } };
  original.value = snapshot();
  tried.value = false;
  adding.value = null;
  loaded.value = true;
};
onMounted(load);

// ---- what changed: compare every leaf value against the saved copy ----
const flat = (o: any, pre = "", out: Record<string, string> = {}) => {
  if (o && typeof o === "object") for (const k of Object.keys(o)) flat(o[k], pre ? `${pre}.${k}` : k, out);
  else out[pre] = JSON.stringify(o);
  return out;
};
const diff = computed(() => {
  const a = flat(original.value ? JSON.parse(original.value) : {});
  const b = flat(state());
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  return [...keys].filter((k) => a[k] !== b[k]);
});
const changedUnder = (prefix: string) => diff.value.some((k) => k === prefix || k.startsWith(prefix + "."));
const countUnder = (...prefixes: string[]) => {
  // count entries (not leaves): one edited row = one change
  const rows = new Set<string>();
  for (const k of diff.value) for (const p of prefixes) if (k === p || k.startsWith(p + ".")) rows.add(k.split(".").slice(0, p.split(".").length + 1).join("."));
  return rows.size;
};
const counts = computed(() => ({
  rates: countUnder("r.brandRates", ...RATE_DEFAULTS.map((f) => `r.${f.k}`)),
  settings: countUnder(...["defaultMarkup", "minMarkup", "vatRate", "validity", "paymentTerms", "tcs"].map((k) => `s.${k}`)),
  glass: countUnder("g.basePrices", "g.types", "g.thicknesses"),
  colours: countUnder("g.colours"),
  acp: countUnder("a"),
  hw: countUnder("h"),
  extras: countUnder("r.extras"),
  mosq: countUnder("m"),
  types: countUnder("p", "t", "f", "w"),
  labels: countUnder("l.sections", "l.fields"),
  cur: diff.value.filter((k) => k.startsWith("k.")).length,
}));
const unsaved = computed(() => Object.values(counts.value).reduce((a, b) => a + b, 0));

const RATE_DEFAULTS = [
  { k: "gasketRate", label: "Gasket", unit: "/m" },
  { k: "fabRate", label: "Fabrication", unit: "/m²" },
  { k: "installRate", label: "Installation", unit: "/m²" },
  { k: "subframeRate", label: "Sub-frame", unit: "/m" },
  { k: "sealantRate", label: "Sealant", unit: "/m" },
];
const RATE_FIELDS_C = computed(() => RATE_DEFAULTS.map((f) => ({ ...f, dflt: f.label, label: fieldName(`rate.${f.k}`, f.label) })));
// one profile rate per brand used by any product, plus "Other" for unbranded systems
const BRANDS_LIST = computed(() => {
  const brands = [...new Set(prods.value.map((p: any) => (p.brand || "").trim()).filter(Boolean))];
  return [...brands.map((b) => ({ k: b, dflt: `${b} profile` })), { k: "DEFAULT", dflt: "Other profiles" }]
    .map((b) => ({ ...b, label: fieldName(`brand.${b.k}`, b.dflt) }));
});
const BASES = [
  { k: "m2", label: "per m²", unit: "/m²" },
  { k: "lm", label: "per metre of frame edge", unit: "/m" },
  { k: "item", label: "per item", unit: "/item" },
  { k: "kg", label: "per kg of aluminium", unit: "/kg" },
];
const unitOf = (b: string) => BASES.find((x) => x.k === b)?.unit || "";
const products = computed(() => values.value.products || []);
const changed = {
  rate: (k: string) => changedUnder(`r.${k}`),
  brand: (k: string) => changedUnder(`r.brandRates.${k}`),
  setting: (k: string) => changedUnder(`s.${k}`),
  glass: (k: string) => changedUnder(`g.basePrices.${k}`),
  mosq: (k: string) => changedUnder(`m.${k}`),
};

// ---- rows, grouped and searchable ----
const q = computed(() => query.value.trim().toLowerCase());
const hit = (label: string) => !q.value || label.toLowerCase().includes(q.value);
const glassGroups = computed(() =>
  (gc.value.types || [])
    .map((t: any) => ({
      type: t.id, label: t.label, custom: !!t.custom, isDGU: !!t.isDGU,
      rows: ((gc.value.thicknesses || {})[t.id] || []).map((th: string) => ({ key: `${t.id}__${th}`, label: th })),
    }))
    .filter((g: any) => !q.value || hit(g.label) || g.rows.some((r: any) => hit(`${g.label} ${r.label}`)))
);
const mosqGroups = computed(() => {
  const groups: { pid: string; label: string; rows: { id: string; label: string }[] }[] = [];
  for (const p of prods.value) {
    const rows = (subs.value[p.id] || [])
      .filter((s: any) => s.id in mosqRates.value)
      .map((s: any) => ({ id: s.id, label: s.label }))
      .filter((r: any) => hit(`${p.label} ${r.label}`));
    if (rows.length) groups.push({ pid: p.id, label: p.label, rows });
  }
  return groups;
});
const showRates = computed(() => !q.value || [...BRANDS_LIST.value, ...RATE_FIELDS_C.value].some((f) => hit(f.label)));
const showSettings = computed(() => !q.value || hit("markup vat validity payment terms conditions"));
const showColours = computed(() => !q.value || hit("colour color tint") || gc.value.colours.some((c: any) => hit(c.label)));
const showAcp = computed(() => !q.value || hit("acp cladding panel") || acp.value.some((p) => hit(p.name)));
// ---- products & types ----
const showTypes = computed(() => !q.value || hit("product type window door system") || prods.value.some((p: any) => hit(p.label) || (subs.value[p.id] || []).some((t: any) => hit(t.label))));
const SPECIAL: Record<string, string> = { acp: "Priced by panel (ACP cladding rules)", balustrade: "Priced per metre run (balustrade rules)" };
const openKit = ref("");
const hwName = (id: string) => hw.value.find((h: any) => h.id === id)?.name || id;
const kitOf = (stid: string) => kits.value[stid] || (kits.value[stid] = []);
const kitSummary = (stid: string) => {
  const k = (kits.value[stid] || []).filter((x) => x.q > 0);
  return k.length ? k.map((x) => `${x.q}× ${hwName(x.id)}`).join(", ") : "No hardware";
};
const addKitLine = (stid: string, id: string) => { if (id && !kitOf(stid).some((x) => x.id === id)) kitOf(stid).push({ id, q: 1 }); };
const removeKitLine = (stid: string, i: number) => kitOf(stid).splice(i, 1);
const kgOf = (t: any) => sf.value[t.id] ?? t.kg ?? 0;
const setKg = (t: any, v: number | null) => { const n = Number(v) || 0; sf.value[t.id] = n; t.kg = n; };
const setFlag = (t: any, key: string, on: boolean) => {
  t[key] = on;
  if (key === "mosq" && on && !(t.id in mosqRates.value)) mosqRates.value[t.id] = 0;   // gets a net price row
  if (key === "mosq" && !on) t.sliding = false;
};
const allTypes = computed(() => prods.value.flatMap((p: any) => (subs.value[p.id] || []).map((t: any) => ({ id: t.id, label: `${p.label}: ${t.label}` }))));
const ensureBrandRate = (brand: string) => {
  const b = (brand || "").trim();
  if (b && rates.value.brandRates[b] == null) rates.value.brandRates[b] = rates.value.brandRates.DEFAULT ?? 3400;
};
const removeSubType = async (pid: string, i: number) => {
  const t = subs.value[pid][i];
  if (!(await askRemove(`the ${t.label} type`))) return;
  subs.value[pid].splice(i, 1);
  delete sf.value[t.id]; delete kits.value[t.id]; delete mosqRates.value[t.id];
};
const removeProduct = async (pid: string) => {
  const p = prods.value.find((x: any) => x.id === pid);
  if (!(await askRemove(p?.label || "this product"))) return;
  for (const t of subs.value[pid] || []) { delete sf.value[t.id]; delete kits.value[t.id]; delete mosqRates.value[t.id]; }
  delete subs.value[pid];
  prods.value = prods.value.filter((x: any) => x.id !== pid);
};
const commitType = (pid: string, d: any) => {
  const name = String(d.name || "").trim();
  if (!need(!!name, "Name the type, e.g. Tilt & Turn")) return false;
  if (!need(!(subs.value[pid] || []).some((t: any) => t.label.toLowerCase() === name.toLowerCase()), `${name} already exists`)) return false;
  if (!need(Number(d.kg) > 0, "Enter the aluminium weight in kg per m²")) return false;
  const id = newId("t", name);
  const from = Object.values(subs.value).flat().find((t: any) => t.id === d.copyFrom) as any;
  const t = { id, label: name, kg: Number(d.kg), mosq: from ? !!from.mosq : true, subframe: from ? !!from.subframe : true, sliding: from ? !!from.sliding : false, custom: true };
  (subs.value[pid] || (subs.value[pid] = [])).push(t);
  sf.value[id] = Number(d.kg);
  kits.value[id] = from ? clone(kits.value[from.id] || []) : [];
  if (t.mosq) mosqRates.value[id] = from ? (mosqRates.value[from.id] ?? 0) : 0;
  return true;
};
const showHw = computed(() => !q.value || hit("hardware") || hw.value.some((h) => hit(h.name)));
const showExtras = computed(() => !q.value || hit("extra charge") || rates.value.extras.some((x: any) => hit(x.name)));
const money = useMoney();
const colourHint = computed(() =>
  gc.value.colours.filter((c: any) => Number(c.premium) > 0).map((c: any) => `${c.label} +${money.fmt(c.premium, curOf(`gc.colours.${c.id}`))}`).join(", ")
);

// ---- currency of each price ----
const curOf = (path: string) => cur.value[path] || "NGN";
const setCur = (path: string, code: string) => {
  if (code === "NGN") delete cur.value[path];
  else cur.value[path] = code;
};

// ---- adding new entries ----
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 24) || "x";
const newId = (prefix: string, name: string) => `${prefix}_${slug(name)}_${Math.random().toString(36).slice(2, 6)}`;
const adding = ref<null | { kind: string; type?: string }>(null);
const draft = ref<any>({});
const draftErr = ref("");
const startAdd = (kind: string, type?: string) => {
  adding.value = { kind, type };
  draftErr.value = "";
  draft.value = kind === "extra" ? { name: "", rate: null, basis: "m2", products: [], optional: false, cur: "NGN" }
    : kind === "type" ? { name: "", isDGU: false, size: "", price: null, cur: "NGN" }
    : kind === "subtype" ? { name: "", kg: null, copyFrom: "" }
    : kind === "product" ? { name: "", brand: "", newBrand: "", isLm: false, typeName: "", kg: null, copyFrom: "" }
    : { name: "", price: null, cur: "NGN" };
  nextTick(() => document.querySelector<HTMLInputElement>(".addrow input")?.focus());
};
const isAdding = (kind: string, type?: string) => adding.value?.kind === kind && adding.value?.type === type;
const cancelAdd = () => { adding.value = null; };
const need = (ok: boolean, msg: string) => { if (!ok) draftErr.value = msg; return ok; };
const price = (v: any) => v !== null && v !== undefined && v !== "" && !isNaN(Number(v)) && Number(v) >= 0;
const commitAdd = () => {
  const d = draft.value; const a = adding.value!; const name = String(d.name || "").trim();
  draftErr.value = "";
  if (a.kind === "subtype") {
    if (!commitType(a.type!, d)) return;
  } else if (a.kind === "product") {
    const brand = (d.brand === "__new" ? d.newBrand : d.brand || "").trim().toUpperCase();
    if (!need(!!name, "Name the product, e.g. Schüco AWS 70 Window")) return;
    if (!need(!prods.value.some((p: any) => p.label.toLowerCase() === name.toLowerCase()), `${name} already exists`)) return;
    if (!need(d.brand !== "__new" || !!brand, "Type the new brand name")) return;
    const pid = newId("p", name);
    prods.value.push({ id: pid, label: name, unit: d.isLm ? "lm" : "m2", isLm: !!d.isLm, brand: brand || undefined, icon: d.isLm ? "shield" : "window", custom: true });
    subs.value[pid] = [];
    if (!commitType(pid, { name: d.typeName || "Standard", kg: d.kg, copyFrom: d.copyFrom })) {
      prods.value.pop(); delete subs.value[pid]; return;
    }
    ensureBrandRate(brand);
  } else if (a.kind === "thickness") {
    const list = gc.value.thicknesses[a.type!] || (gc.value.thicknesses[a.type!] = []);
    if (!need(!!name, "Enter the thickness, e.g. 15mm") || !need(!list.includes(name), `${name} is already listed`) || !need(price(d.price), "Enter the price per m²")) return;
    list.push(name);
    gc.value.basePrices[`${a.type}__${name}`] = Number(d.price);
    setCur(`gc.basePrices.${a.type}__${name}`, d.cur);
  } else if (a.kind === "type") {
    const size = String(d.size || "").trim();
    if (!need(!!name, "Enter the glass type name") || !need(!gc.value.types.some((t: any) => t.label.toLowerCase() === name.toLowerCase()), `${name} already exists`)
      || !need(!!size, "Enter its first thickness") || !need(price(d.price), "Enter the price per m²")) return;
    const id = newId("g", name);
    gc.value.types.push({ id, label: name, isDGU: !!d.isDGU, custom: true });
    gc.value.thicknesses[id] = [size];
    gc.value.basePrices[`${id}__${size}`] = Number(d.price);
    setCur(`gc.basePrices.${id}__${size}`, d.cur);
  } else if (a.kind === "colour") {
    if (!need(!!name, "Enter the colour name") || !need(!gc.value.colours.some((c: any) => c.label.toLowerCase() === name.toLowerCase()), `${name} already exists`) || !need(price(d.price), "Enter the extra cost per m² (0 for none)")) return;
    const id = newId("c", name);
    gc.value.colours.push({ id, label: name, premium: Number(d.price), custom: true });
    setCur(`gc.colours.${id}`, d.cur);
  } else if (a.kind === "acp") {
    if (!need(!!name, "Enter the panel name") || !need(price(d.price), "Enter the price per m²")) return;
    const id = newId("ap", name);
    acp.value.push({ id, name, p: Number(d.price), custom: true });
    setCur(`acpPanels.${id}`, d.cur);
  } else if (a.kind === "extra") {
    if (!need(!!name, "Give the charge a name") || !need(price(d.rate), "Enter the rate")) return;
    const id = newId("x", name);
    setCur(`rates.extras.${id}`, d.cur);
    rates.value.extras.push({ id, name, rate: Number(d.rate), basis: d.basis, products: [...(d.products || [])], optional: !!d.optional });
  }
  adding.value = null;
};
const askRemove = async (what: string) =>
  confirm({ title: `Remove ${what}?`, message: "Quotes already saved keep the prices they were created with. Draft items using it will need a new choice.", confirmLabel: "Remove", danger: true });
const removeThickness = async (type: string, th: string) => {
  if (!(await askRemove(th))) return;
  gc.value.thicknesses[type] = gc.value.thicknesses[type].filter((x: string) => x !== th);
  delete gc.value.basePrices[`${type}__${th}`];
};
const removeType = async (type: string, label: string) => {
  if (gc.value.types.length <= 1) return notify("Keep at least one glass type", "error");
  if (!(await askRemove(`${label} glass`))) return;
  gc.value.types = gc.value.types.filter((t: any) => t.id !== type);
  for (const th of gc.value.thicknesses[type] || []) delete gc.value.basePrices[`${type}__${th}`];
  delete gc.value.thicknesses[type];
};
const removeColour = async (i: number) => {
  if (gc.value.colours.length <= 1) return notify("Keep at least one colour", "error"); if (await askRemove(gc.value.colours[i].label)) gc.value.colours.splice(i, 1);
};
const removeAcp = async (i: number) => { if (await askRemove(acp.value[i].name)) acp.value.splice(i, 1); };
const removeExtra = async (i: number) => { if (await askRemove(rates.value.extras[i].name)) rates.value.extras.splice(i, 1); };
// ---- renaming any entry (built-in or added) ----
const ren = ref<null | { k: string; v: string }>(null);
const isRen = (k: string) => ren.value?.k === k;
const startRename = (k: string, current: string) => {
  ren.value = { k, v: current };
  nextTick(() => document.querySelector<HTMLInputElement>(".ren-inp")?.select());
};
const doRename = () => {
  if (!ren.value) return;
  const { k, v } = ren.value; const name = v.trim();
  ren.value = null;
  if (!name) return notify("Name can't be empty", "error");
  const [kind, a, b] = k.split("|");
  if (kind === "t") {
    if (gc.value.types.some((t: any) => t.id !== a && t.label.toLowerCase() === name.toLowerCase())) return notify(`${name} already exists`, "error");
    gc.value.types.find((t: any) => t.id === a).label = name;
  } else if (kind === "th") {
    const list: string[] = gc.value.thicknesses[a];
    if (name === b) return;
    if (list.includes(name)) return notify(`${name} is already listed`, "error");
    list.splice(list.indexOf(b), 1, name);
    gc.value.basePrices[`${a}__${name}`] = gc.value.basePrices[`${a}__${b}`];
    delete gc.value.basePrices[`${a}__${b}`];
    const c0 = cur.value[`gc.basePrices.${a}__${b}`];
    delete cur.value[`gc.basePrices.${a}__${b}`];
    if (c0) cur.value[`gc.basePrices.${a}__${name}`] = c0;
  } else if (kind === "c") gc.value.colours[+a].label = name;
  else if (kind === "a") acp.value[+a].name = name;
  else if (kind === "h") hw.value[+a].name = name;
  else if (kind === "p") prods.value.find((p: any) => p.id === a).label = name;
  else if (kind === "st") subs.value[a][+b].label = name;
};
const toggleProduct = (x: any, pid: string) => {
  const s = new Set(x.products || []);
  s.has(pid) ? s.delete(pid) : s.add(pid);
  x.products = [...s];
};
const appliesTo = (x: any) =>
  !x.products?.length ? "All products" : x.products.map((p: string) => products.value.find((pp: any) => pp.id === p)?.label || p).join(", ");

// ---- field-level validation ----
const bad = (v: any) => v === null || v === undefined || v === "" || isNaN(Number(v)) || Number(v) < 0;
const errors = computed(() => {
  const e: Record<string, string> = {};
  const s = settings.value;
  if (bad(s.minMarkup)) e.minMarkup = "Enter a number of 0 or more";
  if (bad(s.defaultMarkup)) e.defaultMarkup = "Enter a number of 0 or more";
  else if (Number(s.defaultMarkup) < Number(s.minMarkup)) e.defaultMarkup = `Must be at least the ${s.minMarkup}% minimum`;
  if (bad(s.vatRate)) e.vatRate = "Enter a number of 0 or more";
  if (!(Number(s.validity) >= 1)) e.validity = "At least 1 day";
  for (const b of BRANDS_LIST.value) if (bad(rates.value.brandRates?.[b.k])) e[`b_${b.k}`] = "Required";
  for (const f of RATE_DEFAULTS) if (bad(rates.value[f.k])) e[f.k] = "Required";
  for (const [k, v] of Object.entries(gc.value.basePrices)) if (bad(v)) e[`g_${k}`] = "Required";
  gc.value.colours.forEach((c: any, i: number) => { if (bad(c.premium)) e[`c_${i}`] = "Required"; if (!String(c.label || "").trim()) e[`cn_${i}`] = "Name required"; });
  acp.value.forEach((p, i) => { if (bad(p.p)) e[`a_${i}`] = "Required"; if (!String(p.name || "").trim()) e[`an_${i}`] = "Name required"; });
  hw.value.forEach((h, i) => { if (bad(h.p)) e[`h_${i}`] = "Required"; });
  rates.value.extras.forEach((x: any, i: number) => { if (bad(x.rate)) e[`x_${i}`] = "Required"; if (!String(x.name || "").trim()) e[`xn_${i}`] = "Name required"; });
  for (const [k, v] of Object.entries(mosqRates.value)) if (bad(v)) e[`m_${k}`] = "Required";
  for (const p of prods.value) for (const t of subs.value[p.id] || []) if (!(Number(kgOf(t)) >= 0)) e[`kg_${t.id}`] = "Required";
  return e;
});
const err = (k: string) => (tried.value || unsaved.value) && errors.value[k];

const save = async () => {
  tried.value = true;
  const n = Object.keys(errors.value).length;
  if (n) {
    notify(`Fix ${n} field${n === 1 ? "" : "s"} marked in red before saving`, "error");
    await nextTick();
    document.querySelector<HTMLElement>(".rc [aria-invalid=true]")?.focus();
    return;
  }
  saving.value = true;
  try {
    const put = (key: string, value: any) => request(`/api/quotes/catalog/${key}`, { method: "PUT", body: { value } });

    if (changedUnder("s")) await put("settings", settings.value);
    if (changedUnder("g")) await put("gc", gc.value);

    if (changedUnder("a")) await put("acpPanels", acp.value);
    if (changedUnder("h")) await put("hwItems", hw.value);
    // products before their types; kg factors and kits after, so every type exists
    if (changedUnder("p")) await put("products", prods.value);
    if (changedUnder("t")) await put("subs", subs.value);
    if (changedUnder("f")) await put("sf", sf.value);
    if (changedUnder("w")) await put("hwKits", kits.value);
    if (changedUnder("m")) await put("mosqRates", mosqRates.value);
    if (changedUnder("r")) await put("rates", rates.value);
    if (changedUnder("l")) await put("rateCardLabels", labels.value);
    if (changedUnder("k")) await put("currencies", Object.fromEntries(Object.entries(cur.value).filter(([, c]) => c && c !== "NGN")));
    await load();
    notify("Rate card saved. New quotes use these rates now; saved quotes keep their prices.");
  } catch (e: any) {
    notify(e.message, "error");
  } finally {
    saving.value = false;
  }
};
const discard = async () => {
  if (await confirm({ title: `Discard ${unsaved.value} change${unsaved.value === 1 ? "" : "s"}?`, message: "The rate card goes back to the saved values.", confirmLabel: "Discard", danger: true })) load();
};

// leaving with unsaved edits asks first (sidebar, Back, closing the tab)
const router = useRouter();
const offGuard = router.beforeEach(async () =>
  !unsaved.value || saving.value || (await confirm({ title: "Leave without saving?", message: `${unsaved.value} rate change(s) haven't been saved.`, confirmLabel: "Leave without saving", cancelLabel: "Keep editing", danger: true }))
);
const onUnload = (e: BeforeUnloadEvent) => { if (unsaved.value) { e.preventDefault(); e.returnValue = ""; } };
onMounted(() => window.addEventListener("beforeunload", onUnload));
onUnmounted(() => { offGuard(); window.removeEventListener("beforeunload", onUnload); });
</script>

<template>
  <div class="wrap rc">
    <div v-if="!isAdmin" class="alert" role="alert">Only platform admins can edit the rate card.</div>
    <template v-else>
      <div class="head">
        <div>
          <h1 class="title">Rate Card</h1>
          <p class="sub">
            Prices used for every new quote. Saved quotes keep the prices they were created with.
            Each price can be in any currency; it's converted with the exchange rates in Import Flow.
          </p>
        </div>
        <div class="head-acts">
        <button class="btn btn-secondary btn-sm" :disabled="!!unsaved" :title="unsaved ? 'Save or discard your changes first' : ''" @click="showImport = true"><UiIcon name="upload" :size="13" /> Import prices</button>
        <label class="search">
          <UiIcon name="search" :size="14" class="s-ic" />
          <input v-model="query" class="inp" placeholder="Find a rate, e.g. laminated or sliding" aria-label="Find a rate" />
        </label>
        </div>
      </div>

      <div v-if="!loaded" class="skel-wrap" aria-busy="true" aria-label="Loading rate card">
        <div v-for="n in 3" :key="n" class="skel-card"><div class="skel" style="width: 30%" /><div class="skel" /><div class="skel" /><div class="skel" style="width: 70%" /></div>
      </div>
      <template v-else>
        <details v-show="showRates" class="sec" open>
          <summary>
            <span class="sec-t"><QuoteEditLabel :text="secName('rates')" what="this section" @save="setSection('rates', $event)" /></span>
            <span v-if="counts.rates" class="badge">{{ counts.rates }} changed</span>
          </summary>
          <div class="grid3">
            <label v-for="b in BRANDS_LIST" v-show="hit(b.label)" :key="b.k" class="f" :class="{ ch: changed.brand(b.k) }">
              <span><QuoteEditLabel :text="b.label" @save="setField(`brand.${b.k}`, b.dflt, $event)" /></span>
              <QuotePriceInput v-model="rates.brandRates[b.k]" :currency="curOf(`rates.brandRates.${b.k}`)" :fx="fx" suffix="/kg" :invalid="!!err(`b_${b.k}`)" @update:currency="setCur(`rates.brandRates.${b.k}`, $event)" />
              <span v-if="err(`b_${b.k}`)" class="fe">{{ err(`b_${b.k}`) }}</span>
            </label>
            <label v-for="f in RATE_FIELDS_C" v-show="hit(f.label)" :key="f.k" class="f" :class="{ ch: changed.rate(f.k) }">
              <span><QuoteEditLabel :text="f.label" @save="setField(`rate.${f.k}`, f.dflt, $event)" /></span>
              <QuotePriceInput v-model="rates[f.k]" :currency="curOf(`rates.${f.k}`)" :fx="fx" :suffix="f.unit" :invalid="!!err(f.k)" @update:currency="setCur(`rates.${f.k}`, $event)" />
              <span v-if="err(f.k)" class="fe">{{ err(f.k) }}</span>
            </label>
          </div>
        </details>

        <details v-show="showSettings" class="sec" open>
          <summary>
            <span class="sec-t"><QuoteEditLabel :text="secName('settings')" what="this section" @save="setSection('settings', $event)" /></span>
            <span v-if="counts.settings" class="badge">{{ counts.settings }} changed</span>
          </summary>
          <div class="grid4">
            <label class="f" :class="{ ch: changed.setting('defaultMarkup') }">
              <span><QuoteEditLabel :text="fieldName('setting.defaultMarkup', SETTING_NAMES.defaultMarkup)" @save="setField('setting.defaultMarkup', SETTING_NAMES.defaultMarkup, $event)" /></span>
              <UiNumberInput v-model="settings.defaultMarkup" suffix="%" :invalid="!!err('defaultMarkup')" />
              <span v-if="err('defaultMarkup')" class="fe">{{ err("defaultMarkup") }}</span>
            </label>
            <label class="f" :class="{ ch: changed.setting('minMarkup') }">
              <span><QuoteEditLabel :text="fieldName('setting.minMarkup', SETTING_NAMES.minMarkup)" @save="setField('setting.minMarkup', SETTING_NAMES.minMarkup, $event)" /></span>
              <UiNumberInput v-model="settings.minMarkup" suffix="%" :invalid="!!err('minMarkup')" />
              <span v-if="err('minMarkup')" class="fe">{{ err("minMarkup") }}</span>
              <span v-else class="hint">Quotes can't go below this</span>
            </label>
            <label class="f" :class="{ ch: changed.setting('vatRate') }">
              <span><QuoteEditLabel :text="fieldName('setting.vatRate', SETTING_NAMES.vatRate)" @save="setField('setting.vatRate', SETTING_NAMES.vatRate, $event)" /></span>
              <UiNumberInput v-model="settings.vatRate" suffix="%" :decimals="2" :invalid="!!err('vatRate')" />
              <span v-if="err('vatRate')" class="fe">{{ err("vatRate") }}</span>
            </label>
            <label class="f" :class="{ ch: changed.setting('validity') }">
              <span><QuoteEditLabel :text="fieldName('setting.validity', SETTING_NAMES.validity)" @save="setField('setting.validity', SETTING_NAMES.validity, $event)" /></span>
              <UiNumberInput v-model="settings.validity" suffix="days" :decimals="0" :invalid="!!err('validity')" />
              <span v-if="err('validity')" class="fe">{{ err("validity") }}</span>
            </label>
          </div>
          <div class="grid2" style="margin-top: 12px">
            <label class="f" :class="{ ch: changed.setting('paymentTerms') }">
              <span><QuoteEditLabel :text="fieldName('setting.paymentTerms', SETTING_NAMES.paymentTerms)" @save="setField('setting.paymentTerms', SETTING_NAMES.paymentTerms, $event)" /></span>
              <textarea v-model="settings.paymentTerms" class="inp" rows="3"></textarea>
            </label>
            <label class="f" :class="{ ch: changed.setting('tcs') }">
              <span><QuoteEditLabel :text="fieldName('setting.tcs', SETTING_NAMES.tcs)" @save="setField('setting.tcs', SETTING_NAMES.tcs, $event)" /> <span class="hint">(printed on quotes, one per line)</span></span>
              <textarea v-model="settings.tcs" class="inp" rows="5"></textarea>
            </label>
          </div>
        </details>

        <details v-show="glassGroups.length || !q" class="sec" :open="!!q || undefined">
          <summary>
            <span class="sec-t"><QuoteEditLabel :text="secName('glass')" what="this section" @save="setSection('glass', $event)" /></span>
            <span class="cnt">{{ Object.keys(gc.basePrices).length }} prices</span>
            <span v-if="counts.glass" class="badge">{{ counts.glass }} changed</span>
          </summary>
          <p class="hint" style="margin: -2px 0 12px">Per m², before colour extras{{ colourHint ? ` (${colourHint})` : "" }}. Double-glazed units add both panes' colour extras.</p>
          <fieldset v-for="g in glassGroups" :key="g.type" class="grp">
            <legend>
              <span class="lab-row">
                <input v-if="isRen(`t|${g.type}`)" v-model="ren.v" class="inp name ren-inp" aria-label="New name" @click.prevent @keydown.enter.prevent="doRename" @keydown.esc.prevent="ren = null" @blur="doRename" />
                <template v-else>{{ g.label }}</template>
                <button v-if="!isRen(`t|${g.type}`)" type="button" class="x pen" :aria-label="`Rename ${g.label}`" @click.prevent="startRename(`t|${g.type}`, g.label)"><UiIcon name="edit" :size="12" /></button>
                <span v-if="g.isDGU" class="tag">double glazed</span><span v-if="g.custom" class="tag new">added</span>
                <button class="lnk danger" @click="removeType(g.type, g.label)">Remove type</button>
              </span>
            </legend>
            <div class="grid4">
              <label v-for="r in g.rows" :key="r.key" class="f" :class="{ ch: changed.glass(r.key) }">
                <span class="lab-row">
                  <input v-if="isRen(`th|${g.type}|${r.label}`)" v-model="ren.v" class="inp name ren-inp" aria-label="New name" @click.prevent @keydown.enter.prevent="doRename" @keydown.esc.prevent="ren = null" @blur="doRename" />
                <template v-else>{{ r.label }}</template>
                <button v-if="!isRen(`th|${g.type}|${r.label}`)" type="button" class="x pen" :aria-label="`Rename ${r.label}`" @click.prevent="startRename(`th|${g.type}|${r.label}`, r.label)"><UiIcon name="edit" :size="12" /></button>
                  <button v-if="g.rows.length > 1" type="button" class="x" :aria-label="`Remove ${g.label} ${r.label}`" @click.prevent="removeThickness(g.type, r.label)"><UiIcon name="trash" :size="12" /></button>
                </span>
                <QuotePriceInput v-model="gc.basePrices[r.key]" :currency="curOf(`gc.basePrices.${r.key}`)" :fx="fx" suffix="/m²" :invalid="!!err(`g_${r.key}`)" @update:currency="setCur(`gc.basePrices.${r.key}`, $event)" />
              </label>
              <div v-if="isAdding('thickness', g.type)" class="addrow f">
                <input v-model="draft.name" class="inp" placeholder="Thickness, e.g. 15mm" aria-label="New thickness" @keydown.enter="commitAdd" />
                <QuotePriceInput v-model="draft.price" v-model:currency="draft.cur" :fx="fx" suffix="/m²" label="Price per m²" />
                <div class="add-acts"><button class="btn btn-accent btn-sm" @click="commitAdd">Add</button><button class="btn btn-secondary btn-sm" @click="cancelAdd">Cancel</button></div>
                <span v-if="draftErr" class="fe">{{ draftErr }}</span>
              </div>
              <button v-else class="addbtn" @click="startAdd('thickness', g.type)"><UiIcon name="plus" :size="13" /> Add thickness</button>
            </div>
          </fieldset>
          <div v-if="isAdding('type')" class="addrow addcard">
            <div class="grid4">
              <label class="f"><span>Glass type name</span><input v-model="draft.name" class="inp" placeholder="e.g. Reflective" /></label>
              <label class="f"><span>First thickness</span><input v-model="draft.size" class="inp" placeholder="e.g. 6mm" /></label>
              <label class="f"><span>Price</span><QuotePriceInput v-model="draft.price" v-model:currency="draft.cur" :fx="fx" suffix="/m²" /></label>
              <label class="chk"><input v-model="draft.isDGU" type="checkbox" /> Double glazed (two panes, two colours)</label>
            </div>
            <span v-if="draftErr" class="fe">{{ draftErr }}</span>
            <div class="add-acts"><button class="btn btn-accent btn-sm" @click="commitAdd">Add glass type</button><button class="btn btn-secondary btn-sm" @click="cancelAdd">Cancel</button></div>
          </div>
          <button v-else class="addbtn wide" @click="startAdd('type')"><UiIcon name="plus" :size="13" /> Add glass type</button>
        </details>

        <details v-show="showColours" class="sec" :open="!!q || undefined">
          <summary>
            <span class="sec-t"><QuoteEditLabel :text="secName('colours')" what="this section" @save="setSection('colours', $event)" /></span>
            <span class="cnt">{{ gc.colours.length }} colours</span>
            <span v-if="counts.colours" class="badge">{{ counts.colours }} changed</span>
          </summary>
          <p class="hint" style="margin: -2px 0 12px">Extra cost per m² on top of the glass price. ₦0 means no extra.</p>
          <div class="grid4">
            <label v-for="(c, i) in gc.colours" v-show="hit(c.label + ' colour')" :key="c.id" class="f" :class="{ ch: changedUnder(`g.colours.${i}`) }">
              <span class="lab-row">
                <input v-if="isRen(`c|${i}`)" v-model="ren.v" class="inp name ren-inp" aria-label="New name" @click.prevent @keydown.enter.prevent="doRename" @keydown.esc.prevent="ren = null" @blur="doRename" />
                <template v-else>{{ c.label }}</template>
                <button v-if="!isRen(`c|${i}`)" type="button" class="x pen" :aria-label="`Rename ${c.label}`" @click.prevent="startRename(`c|${i}`, c.label)"><UiIcon name="edit" :size="12" /></button>
                <button type="button" class="x" :aria-label="`Remove ${c.label}`" @click.prevent="removeColour(i)"><UiIcon name="trash" :size="12" /></button>
              </span>
              <QuotePriceInput v-model="c.premium" :currency="curOf(`gc.colours.${c.id}`)" :fx="fx" suffix="/m²" plus :invalid="!!err(`c_${i}`)" @update:currency="setCur(`gc.colours.${c.id}`, $event)" />
            </label>
            <div v-if="isAdding('colour')" class="addrow f">
              <input v-model="draft.name" class="inp" placeholder="Colour, e.g. Bronze" aria-label="New colour" @keydown.enter="commitAdd" />
              <QuotePriceInput v-model="draft.price" v-model:currency="draft.cur" :fx="fx" suffix="/m²" plus label="Extra per m²" />
              <div class="add-acts"><button class="btn btn-accent btn-sm" @click="commitAdd">Add</button><button class="btn btn-secondary btn-sm" @click="cancelAdd">Cancel</button></div>
              <span v-if="draftErr" class="fe">{{ draftErr }}</span>
            </div>
            <button v-else class="addbtn" @click="startAdd('colour')"><UiIcon name="plus" :size="13" /> Add colour</button>
          </div>
        </details>

        <details v-show="showAcp" class="sec" :open="!!q || undefined">
          <summary>
            <span class="sec-t"><QuoteEditLabel :text="secName('acp')" what="this section" @save="setSection('acp', $event)" /></span>
            <span class="cnt">{{ acp.length }} panels</span>
            <span v-if="counts.acp" class="badge">{{ counts.acp }} changed</span>
          </summary>
          <div class="grid4">
            <label v-for="(pnl, i) in acp" v-show="hit(pnl.name + ' acp')" :key="pnl.id" class="f" :class="{ ch: changedUnder(`a.${i}`) }">
              <span class="lab-row">
                <input v-if="isRen(`a|${i}`)" v-model="ren.v" class="inp name ren-inp" aria-label="New name" @click.prevent @keydown.enter.prevent="doRename" @keydown.esc.prevent="ren = null" @blur="doRename" />
                <template v-else>{{ pnl.name }}</template>
                <button v-if="!isRen(`a|${i}`)" type="button" class="x pen" :aria-label="`Rename ${pnl.name}`" @click.prevent="startRename(`a|${i}`, pnl.name)"><UiIcon name="edit" :size="12" /></button>
                <button type="button" class="x" :aria-label="`Remove ${pnl.name}`" @click.prevent="removeAcp(i)"><UiIcon name="trash" :size="12" /></button>
              </span>
              <QuotePriceInput v-model="pnl.p" :currency="curOf(`acpPanels.${pnl.id}`)" :fx="fx" suffix="/m²" :invalid="!!err(`a_${i}`)" @update:currency="setCur(`acpPanels.${pnl.id}`, $event)" />
            </label>
            <div v-if="isAdding('acp')" class="addrow f">
              <input v-model="draft.name" class="inp" placeholder="Panel, e.g. 4mm Brushed Gold" aria-label="New panel" @keydown.enter="commitAdd" />
              <QuotePriceInput v-model="draft.price" v-model:currency="draft.cur" :fx="fx" suffix="/m²" label="Price per m²" />
              <div class="add-acts"><button class="btn btn-accent btn-sm" @click="commitAdd">Add</button><button class="btn btn-secondary btn-sm" @click="cancelAdd">Cancel</button></div>
              <span v-if="draftErr" class="fe">{{ draftErr }}</span>
            </div>
            <button v-else class="addbtn" @click="startAdd('acp')"><UiIcon name="plus" :size="13" /> Add panel</button>
          </div>
        </details>

        <details v-show="showExtras" class="sec" :open="!!rates.extras?.length || !!q || undefined">
          <summary>
            <span class="sec-t"><QuoteEditLabel :text="secName('extras')" what="this section" @save="setSection('extras', $event)" /></span>
            <span class="cnt">{{ rates.extras.length }} added</span>
            <span v-if="counts.extras" class="badge">{{ counts.extras }} changed</span>
          </summary>
          <p class="hint" style="margin: -2px 0 12px">
            Your own cost lines, e.g. scaffolding, transport, powder coating. "Always" charges are added to every matching item;
            "Optional" ones appear as a tick box on quote items.
          </p>
          <div v-for="(x, i) in rates.extras" v-show="hit(x.name)" :key="x.id" class="xrow" :class="{ ch: changedUnder(`r.extras.${i}`) }">
            <label class="f"><span>Name</span><input v-model="x.name" class="inp" :aria-invalid="!!err(`xn_${i}`) || undefined" /></label>
            <label class="f"><span>Rate</span><QuotePriceInput v-model="x.rate" :currency="curOf(`rates.extras.${x.id}`)" :fx="fx" :suffix="unitOf(x.basis)" :invalid="!!err(`x_${i}`)" @update:currency="setCur(`rates.extras.${x.id}`, $event)" /></label>
            <label class="f"><span>Charged</span>
              <select v-model="x.basis" class="inp"><option v-for="b in BASES" :key="b.k" :value="b.k">{{ b.label }}</option></select>
            </label>
            <label class="f"><span>When</span>
              <select v-model="x.optional" class="inp"><option :value="false">Always</option><option :value="true">Optional (tick per item)</option></select>
            </label>
            <div class="f prods">
              <span>Applies to <span class="hint">{{ appliesTo(x) }}</span></span>
              <div class="pchips">
                <button v-for="p in products" :key="p.id" type="button" class="pchip" :aria-pressed="x.products.includes(p.id)" @click="toggleProduct(x, p.id)">{{ p.label }}</button>
              </div>
            </div>
            <button class="x xdel" :aria-label="`Remove ${x.name}`" @click="removeExtra(i)"><UiIcon name="trash" :size="14" /></button>
          </div>
          <div v-if="isAdding('extra')" class="addrow addcard">
            <div class="grid4">
              <label class="f"><span>Name</span><input v-model="draft.name" class="inp" placeholder="e.g. Scaffolding" /></label>
              <label class="f"><span>Rate</span><QuotePriceInput v-model="draft.rate" v-model:currency="draft.cur" :fx="fx" :suffix="unitOf(draft.basis)" /></label>
              <label class="f"><span>Charged</span>
                <select v-model="draft.basis" class="inp"><option v-for="b in BASES" :key="b.k" :value="b.k">{{ b.label }}</option></select>
              </label>
              <label class="f"><span>When</span>
                <select v-model="draft.optional" class="inp"><option :value="false">Always</option><option :value="true">Optional (tick per item)</option></select>
              </label>
            </div>
            <div class="f prods" style="margin-top: 10px">
              <span>Applies to <span class="hint">{{ appliesTo(draft) }} (pick none for all)</span></span>
              <div class="pchips">
                <button v-for="p in products" :key="p.id" type="button" class="pchip" :aria-pressed="draft.products.includes(p.id)" @click="toggleProduct(draft, p.id)">{{ p.label }}</button>
              </div>
            </div>
            <span v-if="draftErr" class="fe">{{ draftErr }}</span>
            <div class="add-acts"><button class="btn btn-accent btn-sm" @click="commitAdd">Add charge</button><button class="btn btn-secondary btn-sm" @click="cancelAdd">Cancel</button></div>
          </div>
          <button v-else class="addbtn wide" @click="startAdd('extra')"><UiIcon name="plus" :size="13" /> Add extra charge</button>
        </details>

        <details v-show="showTypes" class="sec" :open="!!q || undefined">
          <summary>
            <span class="sec-t"><QuoteEditLabel :text="secName('types')" what="this section" @save="setSection('types', $event)" /></span>
            <span class="cnt">{{ prods.length }} products · {{ Object.values(subs).flat().length }} types</span>
            <span v-if="counts.types" class="badge">{{ counts.types }} changed</span>
          </summary>
          <p class="hint" style="margin: -2px 0 12px">
            The systems you sell and their window/door types. Each type sets its aluminium weight (priced at the brand's profile rate),
            its hardware kit, and whether a mosquito net or sub-frame can be added.
          </p>
          <fieldset v-for="pr in prods" v-show="!q || hit(pr.label) || (subs[pr.id] || []).some((t) => hit(t.label))" :key="pr.id" class="grp prod">
            <legend>
              <span class="lab-row">
                <input v-if="isRen(`p|${pr.id}`)" v-model="ren.v" class="inp name ren-inp" aria-label="New name" @keydown.enter.prevent="doRename" @keydown.esc.prevent="ren = null" @blur="doRename" />
                <template v-else>{{ pr.label }}</template>
                <button v-if="!isRen(`p|${pr.id}`)" type="button" class="x pen" :aria-label="`Rename ${pr.label}`" @click.prevent="startRename(`p|${pr.id}`, pr.label)"><UiIcon name="edit" :size="12" /></button>
                <span v-if="pr.brand" class="tag">{{ pr.brand }}</span>
                <span class="tag">{{ pr.isLm ? "per metre" : "per m²" }}</span>
                <span v-if="pr.custom" class="tag new">added</span>
                <button v-if="pr.custom" class="lnk danger" @click="removeProduct(pr.id)">Remove product</button>
              </span>
            </legend>
            <p v-if="SPECIAL[pr.id]" class="hint" style="margin: 0 0 6px">{{ SPECIAL[pr.id] }}</p>
            <div class="tt" role="table" :aria-label="`${pr.label} types`">
              <div class="tt-h" role="row">
                <span role="columnheader">Type</span><span role="columnheader">Aluminium</span><span role="columnheader">Hardware kit</span>
                <span role="columnheader" class="c">Net</span><span role="columnheader" class="c">Sub-frame</span><span role="columnheader" class="c">Sliding</span><span />
              </div>
              <template v-for="(t, i) in subs[pr.id] || []" :key="t.id">
                <div class="tt-r" role="row" :class="{ ch: changedUnder(`t.${pr.id}.${i}`) || changedUnder(`f.${t.id}`) || changedUnder(`w.${t.id}`) }">
                  <span class="lab-row" role="cell">
                    <input v-if="isRen(`st|${pr.id}|${i}`)" v-model="ren.v" class="inp name ren-inp" aria-label="New name" @keydown.enter.prevent="doRename" @keydown.esc.prevent="ren = null" @blur="doRename" />
                    <template v-else>{{ t.label }}</template>
                    <button v-if="!isRen(`st|${pr.id}|${i}`)" type="button" class="x pen" :aria-label="`Rename ${t.label}`" @click.prevent="startRename(`st|${pr.id}|${i}`, t.label)"><UiIcon name="edit" :size="12" /></button>
                  </span>
                  <span role="cell"><UiNumberInput :model-value="kgOf(t)" suffix="kg/m²" :decimals="2" :label="`${t.label} aluminium kg per m²`" :invalid="!!err(`kg_${t.id}`)" @update:model-value="setKg(t, $event)" /></span>
                  <span role="cell"><button type="button" class="kit-btn" :aria-expanded="openKit === t.id" @click="openKit = openKit === t.id ? '' : t.id">{{ kitSummary(t.id) }}</button></span>
                  <span role="cell" class="c"><input type="checkbox" :checked="!!t.mosq" :aria-label="`${t.label}: mosquito net allowed`" @change="setFlag(t, 'mosq', ($event.target as HTMLInputElement).checked)" /></span>
                  <span role="cell" class="c"><input type="checkbox" :checked="!!t.subframe" :aria-label="`${t.label}: sub-frame allowed`" @change="setFlag(t, 'subframe', ($event.target as HTMLInputElement).checked)" /></span>
                  <span role="cell" class="c"><input type="checkbox" :checked="!!t.sliding" :disabled="!t.mosq" :aria-label="`${t.label}: sliding (net on half the area)`" @change="setFlag(t, 'sliding', ($event.target as HTMLInputElement).checked)" /></span>
                  <span role="cell"><button v-if="t.custom && (subs[pr.id] || []).length > 1" type="button" class="x" :aria-label="`Remove ${t.label}`" @click="removeSubType(pr.id, i)"><UiIcon name="trash" :size="13" /></button></span>
                </div>
                <div v-if="openKit === t.id" class="kit">
                  <div v-for="(k, j) in kitOf(t.id)" :key="k.id" class="kit-l">
                    <span>{{ hwName(k.id) }}</span>
                    <UiNumberInput v-model="k.q" :decimals="0" suffix="pcs" :label="`${hwName(k.id)} quantity`" />
                    <button type="button" class="x" :aria-label="`Remove ${hwName(k.id)}`" @click="removeKitLine(t.id, j)"><UiIcon name="trash" :size="12" /></button>
                  </div>
                  <select class="inp" aria-label="Add hardware to this kit" @change="addKitLine(t.id, ($event.target as HTMLSelectElement).value); ($event.target as HTMLSelectElement).value = ''">
                    <option value="">+ Add hardware…</option>
                    <option v-for="h in hw.filter((h) => !kitOf(t.id).some((k) => k.id === h.id))" :key="h.id" :value="h.id">{{ h.name }} ({{ h.unit }})</option>
                  </select>
                </div>
              </template>
            </div>
            <div v-if="isAdding('subtype', pr.id)" class="addrow addcard">
              <div class="grid4">
                <label class="f"><span>Type name</span><input v-model="draft.name" class="inp" placeholder="e.g. Tilt & Turn" /></label>
                <label class="f"><span>Aluminium</span><UiNumberInput v-model="draft.kg" suffix="kg/m²" :decimals="2" /></label>
                <label class="f" style="grid-column: span 2"><span>Copy hardware and options from</span>
                  <select v-model="draft.copyFrom" class="inp"><option value="">Start empty</option><option v-for="x in allTypes" :key="x.id" :value="x.id">{{ x.label }}</option></select>
                </label>
              </div>
              <span v-if="draftErr" class="fe">{{ draftErr }}</span>
              <div class="add-acts"><button class="btn btn-accent btn-sm" @click="commitAdd">Add type</button><button class="btn btn-secondary btn-sm" @click="cancelAdd">Cancel</button></div>
            </div>
            <button v-else-if="!SPECIAL[pr.id]" class="addbtn" style="margin-top: 6px" @click="startAdd('subtype', pr.id)"><UiIcon name="plus" :size="13" /> Add type</button>
          </fieldset>

          <div v-if="isAdding('product')" class="addrow addcard">
            <div class="grid4">
              <label class="f" style="grid-column: span 2"><span>Product / system name</span><input v-model="draft.name" class="inp" placeholder="e.g. Schüco AWS 70 Window" /></label>
              <label class="f"><span>Brand</span>
                <select v-model="draft.brand" class="inp">
                  <option value="">No brand (Other profiles rate)</option>
                  <option v-for="b in BRANDS_LIST.filter((x) => x.k !== 'DEFAULT')" :key="b.k" :value="b.k">{{ b.k }}</option>
                  <option value="__new">New brand…</option>
                </select>
              </label>
              <label v-if="draft.brand === '__new'" class="f"><span>New brand</span><input v-model="draft.newBrand" class="inp" placeholder="e.g. SCHUCO" /></label>
              <label class="f"><span>Measured</span>
                <select v-model="draft.isLm" class="inp"><option :value="false">per m² (width × height)</option><option :value="true">per metre run (like balustrades)</option></select>
              </label>
              <label class="f"><span>First type</span><input v-model="draft.typeName" class="inp" placeholder="e.g. Casement" /></label>
              <label class="f"><span>Aluminium</span><UiNumberInput v-model="draft.kg" suffix="kg/m²" :decimals="2" /></label>
              <label class="f"><span>Copy hardware and options from</span>
                <select v-model="draft.copyFrom" class="inp"><option value="">Start empty</option><option v-for="x in allTypes" :key="x.id" :value="x.id">{{ x.label }}</option></select>
              </label>
            </div>
            <p class="hint">A new brand gets its own profile rate under Materials and labour (starting at the "Other profiles" rate).</p>
            <span v-if="draftErr" class="fe">{{ draftErr }}</span>
            <div class="add-acts"><button class="btn btn-accent btn-sm" @click="commitAdd">Add product</button><button class="btn btn-secondary btn-sm" @click="cancelAdd">Cancel</button></div>
          </div>
          <button v-else class="addbtn wide" @click="startAdd('product')"><UiIcon name="plus" :size="13" /> Add product</button>
        </details>

        <details v-show="showHw" class="sec" :open="!!q || undefined">
          <summary>
            <span class="sec-t"><QuoteEditLabel :text="secName('hw')" what="this section" @save="setSection('hw', $event)" /></span>
            <span class="cnt">{{ hw.length }} items</span>
            <span v-if="counts.hw" class="badge">{{ counts.hw }} changed</span>
          </summary>
          <p class="hint" style="margin: -2px 0 12px">Unit prices. Each window or door type uses a fixed kit of these (e.g. a single casement = 1 handle, 2 stays, 1 lock).</p>
          <div class="grid4">
            <label v-for="(h, i) in hw" v-show="hit(h.name + ' hardware')" :key="h.id" class="f" :class="{ ch: changedUnder(`h.${i}`) }">
              <span class="lab-row">
                <input v-if="isRen(`h|${i}`)" v-model="ren.v" class="inp name ren-inp" aria-label="New name" @click.prevent @keydown.enter.prevent="doRename" @keydown.esc.prevent="ren = null" @blur="doRename" />
                <template v-else>{{ h.name }}</template>
                <button v-if="!isRen(`h|${i}`)" type="button" class="x pen" :aria-label="`Rename ${h.name}`" @click.prevent="startRename(`h|${i}`, h.name)"><UiIcon name="edit" :size="12" /></button>
              </span>
              <QuotePriceInput v-model="h.p" :currency="curOf(`hwItems.${h.id}`)" :fx="fx" :suffix="`/${h.unit}`" :invalid="!!err(`h_${i}`)" @update:currency="setCur(`hwItems.${h.id}`, $event)" />
            </label>
          </div>
        </details>

        <details v-show="mosqGroups.length" class="sec" :open="!!q || undefined">
          <summary>
            <span class="sec-t"><QuoteEditLabel :text="secName('mosq')" what="this section" @save="setSection('mosq', $event)" /></span>
            <span class="cnt">{{ Object.keys(mosqRates).length }} prices</span>
            <span v-if="counts.mosq" class="badge">{{ counts.mosq }} changed</span>
          </summary>
          <p class="hint" style="margin: -2px 0 12px">Per m² of the item when "Mosquito net" is ticked. Sliding types are charged on half the area. ₦0 means free.</p>
          <fieldset v-for="g in mosqGroups" :key="g.pid" class="grp">
            <legend><QuoteEditLabel :text="g.label" what="this product" @save="renameProduct(g.pid, $event)" /></legend>
            <div class="grid4">
              <label v-for="r in g.rows" :key="r.id" class="f" :class="{ ch: changed.mosq(r.id) }">
                <span><QuoteEditLabel :text="r.label" what="this type" @save="renameType(r.id, $event)" /></span>
                <QuotePriceInput v-model="mosqRates[r.id]" :currency="curOf(`mosqRates.${r.id}`)" :fx="fx" suffix="/m²" :invalid="!!err(`m_${r.id}`)" @update:currency="setCur(`mosqRates.${r.id}`, $event)" />
              </label>
            </div>
          </fieldset>
        </details>

        <p v-if="q && !showRates && !showSettings && !glassGroups.length && !mosqGroups.length && !showColours && !showAcp && !showExtras && !showHw && !showTypes" class="empty">No rates match "{{ query }}"</p>
      </template>

      <UiAppModal :open="showImport" title="Import prices" :width="760" @close="showImport = false">
        <ImportWizard :kinds="PRICE_KINDS" @imported="(k: string, r: any) => { load(); notify(`${r.created} added, ${r.updated} updated`); }" />
      </UiAppModal>

      <!-- sticky save bar: only when something changed -->
      <div v-if="unsaved" class="savebar" role="region" aria-label="Unsaved changes">
        <span><strong>{{ unsaved }}</strong> unsaved change{{ unsaved === 1 ? "" : "s" }}</span>
        <div style="display: flex; gap: 8px">
          <button class="btn btn-secondary" :disabled="saving" @click="discard">Discard</button>
          <button class="btn btn-accent" :disabled="saving" @click="save">{{ saving ? "Saving…" : "Save rate card" }}</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.wrap { padding: 22px 22px 110px; max-width: 1200px; margin: 0 auto; }
.head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.title { font-size: 20px; font-weight: 800; color: #0f172a; }
.sub { font-size: 12.5px; color: #475569; margin-top: 4px; max-width: 560px; }
.search { position: relative; width: 320px; max-width: 100%; display: block; }
.s-ic { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #64748b; }
.search .inp { padding-left: 32px; }
.alert { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; border-radius: 9px; padding: 12px 14px; font-size: 12.5px; font-weight: 600; }
.sec { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0 16px; margin-bottom: 12px; }
.sec[open] { padding-bottom: 16px; }
.sec summary { display: flex; align-items: center; gap: 10px; padding: 14px 0; cursor: pointer; list-style: none; min-height: 44px; }
.sec summary::-webkit-details-marker { display: none; }
.sec summary::before { content: "›"; color: #64748b; font-size: 18px; transition: transform .15s; display: inline-block; width: 12px; }
.sec[open] summary::before { transform: rotate(90deg); }
.sec-t { font-size: 13px; font-weight: 800; color: #0f172a; text-transform: uppercase; letter-spacing: .6px; }
.cnt { font-size: 12px; color: #64748b; font-weight: 600; }
.badge { font-size: 11px; font-weight: 800; color: #92400e; background: #fef3c7; border-radius: 20px; padding: 2px 9px; }
.grp { border: none; padding: 0; margin: 0 0 14px; }
.grp legend { font-size: 12px; font-weight: 800; color: #334155; margin-bottom: 8px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.grid3 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px 12px; }
.f { font-size: 12px; font-weight: 700; color: #334155; display: flex; flex-direction: column; gap: 5px; position: relative; }
.f.ch > span:first-child:not(.lab-row)::after { content: " • edited"; color: #b45309; font-weight: 700; }
.f.ch :deep(.inp) { background: #fffbeb; border-color: #f59e0b; }
.fe { font-size: 11.5px; color: #b91c1c; font-weight: 600; }
.hint { font-size: 11.5px; color: #64748b; font-weight: 500; }
.inp { width: 100%; resize: vertical; }
.empty { text-align: center; color: #64748b; padding: 30px; }
.savebar {
  position: fixed; left: 50%; bottom: 18px; transform: translateX(-50%); z-index: 40; width: min(640px, calc(100% - 32px));
  display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px 10px 18px;
  background: #0f172a; color: #fff; border-radius: 12px; box-shadow: 0 16px 40px rgba(15,23,42,.3); font-size: 13.5px;
}
.savebar .btn-secondary { background: transparent; color: #fff; border-color: #475569; }
.skel-wrap { display: grid; gap: 12px; }
.skel-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; display: grid; gap: 10px; }
.tag { font-size: 10.5px; font-weight: 700; color: #475569; background: #f1f5f9; border-radius: 20px; padding: 1px 8px; margin-left: 8px; }
.tag.new { color: #047857; background: #ecfdf5; }
.lnk { background: none; border: none; font: inherit; font-size: 11.5px; font-weight: 700; color: #2563eb; cursor: pointer; margin-left: 10px; padding: 0; }
.lnk.danger { color: #b91c1c; }
.lab-row { display: flex; align-items: center; gap: 6px; min-height: 18px; }
.lab-row .name { padding: 3px 7px; font-size: 12px; font-weight: 700; }
.x { margin-left: auto; background: none; border: none; color: #94a3b8; cursor: pointer; padding: 2px; border-radius: 5px; display: inline-flex; }
.x:hover { color: #b91c1c; background: #fef2f2; }
.x.pen { margin-left: 0; opacity: .55; }
.x.pen:hover { color: #2563eb; background: #eff6ff; opacity: 1; }
.pen + .x { margin-left: auto; }
.lab-row .x:not(.pen):only-of-type { margin-left: auto; }
legend .lab-row { gap: 4px; }
.addbtn {
  display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 38px; align-self: end;
  border: 1.5px dashed #cbd5e1; border-radius: 8px; background: #fff; color: #334155; font: inherit; font-size: 12.5px; font-weight: 700; cursor: pointer;
}
.addbtn:hover { border-color: #2563eb; color: #2563eb; background: #eff6ff; }
.addbtn.wide { width: 100%; margin-top: 4px; }
.addrow { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 9px; padding: 10px; gap: 7px; }
.addcard { display: grid; gap: 10px; margin-top: 4px; }
.add-acts { display: flex; gap: 6px; }
.chk { display: flex; align-items: center; gap: 8px; font-size: 12.5px; font-weight: 600; color: #334155; align-self: end; min-height: 38px; }
.xrow { display: grid; grid-template-columns: 1.3fr 1fr 1fr 1fr 32px; gap: 10px 12px; padding: 12px; border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 10px; align-items: start; }
.xrow.ch { border-color: #f59e0b; background: #fffbeb; }
.xrow .prods { grid-column: 1 / 5; }
.xdel { grid-column: 5; grid-row: 1; margin-top: 22px; }
.pchips { display: flex; flex-wrap: wrap; gap: 6px; }
.pchip { font: inherit; font-size: 11.5px; font-weight: 600; color: #475569; background: #fff; border: 1px solid #cbd5e1; border-radius: 20px; padding: 4px 10px; cursor: pointer; }
.pchip[aria-pressed="true"] { background: #1d4ed8; border-color: #1d4ed8; color: #fff; }
.prod { border-top: 1px solid #f1f5f9; padding-top: 10px; min-width: 0; }
.grp { min-width: 0; }
.tt-r > span { min-width: 0; }
.tt { display: grid; gap: 4px; }
.tt-h, .tt-r { display: grid; grid-template-columns: minmax(140px, 1.3fr) 150px minmax(150px, 1.6fr) 56px 70px 58px 28px; gap: 8px; align-items: center; }
.tt-h { font-size: 11px; font-weight: 800; color: #64748b; text-transform: uppercase; letter-spacing: .4px; padding: 0 4px; }
.tt-r { padding: 4px; border-radius: 8px; font-size: 12.5px; font-weight: 600; color: #0f172a; }
.tt-r.ch { background: #fffbeb; }
.tt .c { text-align: center; justify-self: center; }
.tt input[type="checkbox"] { width: 16px; height: 16px; accent-color: #2563eb; }
.kit-btn { width: 100%; text-align: left; font: inherit; font-size: 12px; color: #334155; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 7px; padding: 6px 8px; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kit-btn[aria-expanded="true"] { border-color: #93c5fd; background: #eff6ff; }
.kit { margin: 0 0 6px 12px; padding: 8px 10px; border-left: 3px solid #bfdbfe; display: grid; gap: 6px; max-width: 520px; }
.kit-l { display: grid; grid-template-columns: 1fr 110px 26px; gap: 8px; align-items: center; font-size: 12.5px; }
@media (max-width: 960px) { .grid3, .grid4 { grid-template-columns: 1fr 1fr; } }
@media (max-width: 900px) {
  .tt-h { display: none; }
  .tt-r { grid-template-columns: 1fr 1fr; border: 1px solid #e2e8f0; padding: 8px; }
  .tt-r .c { justify-self: start; display: flex; align-items: center; gap: 6px; }
  .tt-r .c::after { font-size: 11.5px; color: #475569; }
  .tt-r .c:nth-child(4)::after { content: "Net"; }
  .tt-r .c:nth-child(5)::after { content: "Sub-frame"; }
  .tt-r .c:nth-child(6)::after { content: "Sliding"; }
}
@media (max-width: 760px) { .xrow { grid-template-columns: 1fr 1fr; } .xrow .prods { grid-column: 1 / -1; } .xdel { grid-column: 2; justify-self: end; margin-top: 0; } }
@media (max-width: 560px) { .grid2, .grid3, .grid4, .xrow { grid-template-columns: 1fr; } .xdel { grid-column: 1; grid-row: auto; } .search { width: 100%; } }
</style>
