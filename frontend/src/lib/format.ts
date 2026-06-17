import { DateObject } from "react-multi-date-picker";
import persian from "react-date-object/calendars/persian";
import persian_fa from "react-date-object/locales/persian_fa";
import gregorian from "react-date-object/calendars/gregorian";
import gregorian_en from "react-date-object/locales/gregorian_en";

const FA_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

export const UNIT = "هزار تومان";

// Gregorian ISO date (YYYY-MM-DD) -> Jalali date string with Persian digits,
// e.g. "2026-06-18" -> "۱۴۰۵/۰۳/۲۸". Empty in, empty out.
export function faJalaliDate(isoDate: string) {
  if (!isoDate) {
    return "";
  }
  return new DateObject({
    date: isoDate,
    format: "YYYY-MM-DD",
    calendar: gregorian,
    locale: gregorian_en,
  })
    .convert(persian, persian_fa)
    .format("YYYY/MM/DD");
}

export function faNum(n: number | string) {
  return String(n).replace(/\d/g, (digit) => FA_DIGITS[Number(digit)]);
}

// Persian/Arabic digits -> ASCII digits. For search/sort on user labels.
export function enNum(s: string) {
  return s
    .replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
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

// Clock time (HH:MM) of an ISO timestamp, with Persian digits.
export function faTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return faNum(`${hh}:${mm}`);
}
