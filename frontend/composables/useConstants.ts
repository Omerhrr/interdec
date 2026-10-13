// Shared constants & helpers - mirrors the original app's constants
export const STATUS_LABELS: Record<string, string> = {
  order_placed: "Order Placed",
  under_production: "Under Production",
  in_transit: "In Transit",
  completed: "Completed",
};

export const STATUS_COLORS: Record<string, string> = {
  order_placed: "#3b82f6",
  under_production: "#f59e0b",
  in_transit: "#8b5cf6",
  completed: "#10b981",
};

// Darker shades for status TEXT on tinted chips (>= 4.5:1 contrast)
export const STATUS_TEXT: Record<string, string> = {
  order_placed: "#1d4ed8",
  under_production: "#b45309",
  in_transit: "#6d28d9",
  completed: "#047857",
};

export const STATUS_ORDER = ["order_placed", "under_production", "in_transit", "completed"];

export const COMPANIES = [
  { id: "facade", name: "Facade", color: "#5B8EC9", text: "#2f5f94", logo: "/img/logo-facade.png" },
  { id: "davinci", name: "Davinci", color: "#D4684A", text: "#a53f24", logo: "/img/logo-davinci.png" },
  { id: "doortec", name: "Doortec", color: "#5BBF3A", text: "#2f7a17", logo: "/img/logo-doortec.png" },
];

export const CATEGORIES = ["Electronics","Raw Materials","Textiles","Food & Beverage","Machinery","Packaging","Chemicals","Furniture","Auto Parts","Glass & Glazing","Hardware","Other"];

export const PAYMENT_TERMS = ["Before Shipment", "After Shipment"];

export const SHIP_METHODS = ["FCL", "LCL", "Air D2D"];

export const CURRENCIES = ["USD","EUR","GBP","JPY","CNY","ILS","AED","NGN"];

export const DEFAULT_RATES: Record<string, number> = {
  USD: 1, EUR: 1.08, GBP: 1.27, JPY: 0.0067, CNY: 0.14, ILS: 0.27, AED: 0.27, NGN: 0.00065,
};

export const COUNTRY_FLAGS: Record<string, string> = {
  China: "🇨🇳", Germany: "🇩🇪", "United Kingdom": "🇬🇧", India: "🇮🇳", Japan: "🇯🇵",
  UAE: "🇦🇪", Mexico: "🇲🇽", "United States": "🇺🇸", Turkey: "🇹🇷", Brazil: "🇧🇷",
  Italy: "🇮🇹", France: "🇫🇷", Israel: "🇮🇱", Netherlands: "🇳🇱", "South Korea": "🇰🇷",
  Singapore: "🇸🇬", Greece: "🇬🇷", Denmark: "🇩🇰", Switzerland: "🇨🇭", Nigeria: "🇳🇬",
};

export const fmtDate = (t?: number | null) =>
  t ? new Date(t).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "N/A";

// ETA: new records store ISO "YYYY-MM-DD" (date picker); older ones hold free text "dd/mm/yy"
export const etaToIso = (v?: string | null): string => {
  if (!v) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v;
  const m = v.trim().match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$/);
  if (!m) return "";
  const y = m[3].length === 2 ? 2000 + Number(m[3]) : Number(m[3]);
  return `${y}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
};
export const fmtEta = (v?: string | null) => {
  const iso = etaToIso(v);
  if (!iso) return v || "";
  const [y, mo, d] = iso.split("-").map(Number);
  return fmtDate(new Date(y, mo - 1, d).getTime());
};

export const fmtSize = (t?: number | null) =>
  !t ? "N/A" : t < 1024 ? t + " B" : t < 1048576 ? (t / 1024).toFixed(1) + " KB" : (t / 1048576).toFixed(1) + " MB";

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);

export const fileToBase64 = (f: File): Promise<string> =>
  new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(",")[1] || "");
    r.onerror = rej;
    r.readAsDataURL(f);
  });

// Aggregate accessor so components can do `const { X, Y } = useConstants()`
export const useConstants = () => ({
  STATUS_LABELS,
  STATUS_COLORS,
  STATUS_TEXT,
  STATUS_ORDER,
  COMPANIES,
  CATEGORIES,
  PAYMENT_TERMS,
  SHIP_METHODS,
  CURRENCIES,
  DEFAULT_RATES,
  COUNTRY_FLAGS,
  fmtDate,
  fmtEta,
  etaToIso,
  fmtSize,
  uid,
  fileToBase64,
});
