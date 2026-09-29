// Shared constants & helpers — mirrors the original app's constants
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

export const STATUS_ORDER = ["order_placed", "under_production", "in_transit", "completed"];

export const COMPANIES = [
  { id: "facade", name: "Facade", color: "#5B8EC9", logo: "/img/logo-facade.png" },
  { id: "davinci", name: "Davinci", color: "#D4684A", logo: "/img/logo-davinci.png" },
  { id: "doortec", name: "Doortec", color: "#5BBF3A", logo: "/img/logo-doortec.png" },
];

export const CATEGORIES = ["Electronics","Raw Materials","Textiles","Food & Beverage","Machinery","Packaging","Chemicals","Furniture","Auto Parts","Glass & Glazing","Hardware","Other"];

export const PAYMENT_TERMS = ["Before Shipment", "After Shipment"];

export const SHIP_METHODS = ["FCL", "LCL", "Air D2D"];

export const CURRENCIES = ["USD","EUR","GBP","JPY","CNY","ILS","AED"];

export const DEFAULT_RATES: Record<string, number> = {
  USD: 1, EUR: 1.08, GBP: 1.27, JPY: 0.0067, CNY: 0.14, ILS: 0.27, AED: 0.27,
};

export const COUNTRY_FLAGS: Record<string, string> = {
  China: "🇨🇳", Germany: "🇩🇪", "United Kingdom": "🇬🇧", India: "🇮🇳", Japan: "🇯🇵",
  UAE: "🇦🇪", Mexico: "🇲🇽", "United States": "🇺🇸", Turkey: "🇹🇷", Brazil: "🇧🇷",
  Italy: "🇮🇹", France: "🇫🇷", Israel: "🇮🇱", Netherlands: "🇳🇱", "South Korea": "🇰🇷",
  Singapore: "🇸🇬", Greece: "🇬🇷", Denmark: "🇩🇰", Switzerland: "🇨🇭", Nigeria: "🇳🇬",
};

export const fmtDate = (t?: number | null) =>
  t ? new Date(t).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "—";

export const fmtSize = (t?: number | null) =>
  !t ? "—" : t < 1024 ? t + " B" : t < 1048576 ? (t / 1024).toFixed(1) + " KB" : (t / 1048576).toFixed(1) + " MB";

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
  STATUS_ORDER,
  COMPANIES,
  CATEGORIES,
  PAYMENT_TERMS,
  SHIP_METHODS,
  CURRENCIES,
  DEFAULT_RATES,
  COUNTRY_FLAGS,
  fmtDate,
  fmtSize,
  uid,
  fileToBase64,
});
