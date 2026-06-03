const FA_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

export const UNIT = "هزار تومان";

export function faNum(n: number | string) {
  return String(n).replace(/\d/g, (digit) => FA_DIGITS[Number(digit)]);
}

export function faGroup(n: number) {
  return Math.round(n)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, "٬")
    .replace(/\d/g, (digit) => FA_DIGITS[Number(digit)]);
}

export function money(n: number) {
  return faGroup(n);
}
