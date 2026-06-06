import DatePicker, { DateObject } from "react-multi-date-picker";
import persian from "react-date-object/calendars/persian";
import persian_fa from "react-date-object/locales/persian_fa";
import gregorian from "react-date-object/calendars/gregorian";
import gregorian_en from "react-date-object/locales/gregorian_en";

type Props = {
  /** Gregorian ISO date string, e.g. "2026-06-06" (empty string for none). */
  value: string;
  /** Receives a gregorian ISO date string (or "" when cleared). */
  onChange: (isoDate: string) => void;
  className?: string;
};

const inputClass =
  "mt-2 w-44 rounded-xl border border-border bg-surface-2 px-3 py-2 text-base " +
  "font-semibold text-text outline-none transition focus:border-accent";

/**
 * Persian (Jalali) calendar date picker. The UI shows Jalali dates, but the
 * value in/out is always a gregorian ISO string so the backend (which filters
 * on gregorian business_date) needs no changes.
 */
export function JalaliDateInput({ value, onChange, className }: Props) {
  const shownValue = value
    ? new DateObject({
        date: value,
        format: "YYYY-MM-DD",
        calendar: gregorian,
        locale: gregorian_en,
      }).convert(persian, persian_fa)
    : "";

  return (
    <DatePicker
      calendar={persian}
      locale={persian_fa}
      calendarPosition="bottom-right"
      inputClass={className ?? inputClass}
      value={shownValue}
      onChange={(date) => {
        if (!date) {
          onChange("");
          return;
        }
        const iso = (date as DateObject)
          .convert(gregorian, gregorian_en)
          .format("YYYY-MM-DD");
        onChange(iso);
      }}
    />
  );
}
