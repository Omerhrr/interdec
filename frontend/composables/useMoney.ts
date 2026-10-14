// Currency symbols and formatting shared by the quote screens.
export const CURRENCY_SYMBOLS: Record<string, string> = {
  NGN: "₦", USD: "$", EUR: "€", GBP: "£", JPY: "¥", CNY: "¥", ILS: "₪", AED: "AED ", GHS: "GH₵", ZAR: "R", KES: "KSh ",
};
export const CURRENCY_NAMES: Record<string, string> = {
  NGN: "Naira", USD: "US dollar", EUR: "Euro", GBP: "British pound", JPY: "Japanese yen", CNY: "Chinese yuan",
  ILS: "Israeli shekel", AED: "UAE dirham", GHS: "Ghana cedi", ZAR: "South African rand", KES: "Kenyan shilling",
};

export const useMoney = () => {
  const sym = (code?: string) => CURRENCY_SYMBOLS[(code || "NGN").toUpperCase()] ?? `${(code || "").toUpperCase()} `;
  // whole units for naira and yen; cents for the rest only when there are any
  const fmt = (n: number | null | undefined, code = "NGN") => {
    const v = Number(n) || 0;
    const whole = ["NGN", "JPY"].includes(code.toUpperCase()) || Math.abs(v) >= 1000;
    const cents = !whole && Math.round(v * 100) % 100 !== 0;
    return sym(code) + v.toLocaleString("en-NG", { maximumFractionDigits: cents ? 2 : 0, minimumFractionDigits: cents ? 2 : 0 });
  };
  const rateText = (code: string, rate: number) =>
    code === "NGN" ? "" : `1 ${code} = ₦${Number(rate || 0).toLocaleString("en-NG", { maximumFractionDigits: 2 })}`;
  return { sym, fmt, rateText };
};
