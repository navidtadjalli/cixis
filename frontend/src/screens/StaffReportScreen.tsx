import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import DatePicker, { DateObject } from "react-multi-date-picker";
import persian from "react-date-object/calendars/persian";
import persian_fa from "react-date-object/locales/persian_fa";
import gregorian from "react-date-object/calendars/gregorian";
import gregorian_en from "react-date-object/locales/gregorian_en";
import { apiDelete, apiGet, apiPost } from "../lib/api";
import { faNum, money } from "../lib/format";
import {
  ChangePasswordForm,
  PasswordGate,
  useGate,
} from "../components/PasswordGate";
import { Badge, Button } from "../components/ui";

// Tab A (manager only): the month's per-person report — shifts, late/early/
// overtime, and the tab (gross, free allowance, net). Also the roster manager
// (add/remove names). Gated by the manager password, which forces a change on
// first use.

type Employee = { id: number; name: string };

type ReportRow = {
  employee_id: number;
  employee_name: string;
  shifts_count: number;
  late_minutes: number;
  early_minutes: number;
  overtime_minutes: number;
  gross_tab: number;
  free_value: number;
  free_coffee_units: number;
  free_shake_units: number;
  net_tab: number;
};

const inputClass =
  "min-h-11 rounded-xl border border-border bg-surface-2 px-4 text-base font-semibold text-text outline-none transition focus:border-accent";

function faDuration(minutes: number) {
  if (!minutes) {
    return faNum(0);
  }
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h && m) {
    return `${faNum(h)}س ${faNum(m)}د`;
  }
  return h ? `${faNum(h)} ساعت` : `${faNum(m)} دقیقه`;
}

function monthRange(value: DateObject) {
  const first = new DateObject(value).toFirstOfMonth();
  const last = new DateObject(value).toLastOfMonth();
  return {
    from: first.convert(gregorian, gregorian_en).format("YYYY-MM-DD"),
    to: last.convert(gregorian, gregorian_en).format("YYYY-MM-DD"),
  };
}

export function StaffReportScreen() {
  const gate = useGate("/manager/unlock/");
  const [changed, setChanged] = useState(false);
  const [changing, setChanging] = useState(false);

  const [monthValue, setMonthValue] = useState<DateObject>(
    () => new DateObject({ calendar: persian, locale: persian_fa }),
  );
  const [report, setReport] = useState<ReportRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [newName, setNewName] = useState("");
  const [rosterError, setRosterError] = useState<string | null>(null);

  const range = useMemo(() => monthRange(monthValue), [monthValue]);

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet<{ employees: ReportRow[] }>(
        `/reports/staff-monthly/?from=${range.from}&to=${range.to}`,
      );
      setReport(data.employees);
    } catch {
      setError("دریافت گزارش ناموفق بود");
    } finally {
      setLoading(false);
    }
  }, [range.from, range.to]);

  const loadRoster = useCallback(async () => {
    setEmployees(await apiGet<Employee[]>("/employees/"));
  }, []);

  const ready = gate.unlocked && (!gate.response?.must_change || changed);

  useEffect(() => {
    if (ready) {
      void loadReport();
      void loadRoster().catch(() => undefined);
    }
  }, [ready, loadReport, loadRoster]);

  const addEmployee = async (event: FormEvent) => {
    event.preventDefault();
    const name = newName.trim();
    if (!name) {
      return;
    }
    setRosterError(null);
    try {
      await apiPost("/employees/", { name });
      setNewName("");
      await loadRoster();
      await loadReport();
    } catch {
      setRosterError("افزودن پرسنل ناموفق بود");
    }
  };

  const removeEmployee = async (id: number) => {
    setRosterError(null);
    try {
      await apiDelete(`/employees/${id}/`);
      await loadRoster();
      await loadReport();
    } catch {
      setRosterError("حذف پرسنل ناموفق بود");
    }
  };

  if (!gate.unlocked) {
    return (
      <PasswordGate
        title="گزارش ماهانه پرسنل"
        prompt="این بخش فقط برای مدیر است. رمز مدیر را وارد کنید."
        onSubmit={gate.unlock}
      />
    );
  }

  if (gate.response?.must_change && !changed) {
    return (
      <ChangePasswordForm
        changePath="/manager/password/"
        title="تغییر رمز مدیر"
        intro="برای اولین ورود، رمز پیش‌فرض را به یک رمز دلخواه تغییر دهید."
        onDone={() => setChanged(true)}
      />
    );
  }

  if (changing) {
    return (
      <ChangePasswordForm
        changePath="/manager/password/"
        title="تغییر رمز مدیر"
        onDone={() => setChanging(false)}
        onCancel={() => setChanging(false)}
      />
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-3xl font-black text-text">گزارش ماهانه پرسنل</h2>
          <p className="mt-2 text-base text-muted">
            برای هر پرسنل: تعداد شیفت، تأخیر، زودتر آمدن، اضافه‌کاری و حساب ماه.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setChanging(true)}
          className="text-sm text-muted underline-offset-4 hover:text-text hover:underline"
        >
          تغییر رمز مدیر
        </button>
      </div>

      <section className="rounded-2xl border border-border bg-surface p-5">
        <label className="block">
          <span className="text-sm font-bold text-text">ماه (تقویم جلالی)</span>
          <div className="mt-1.5">
            <DatePicker
              onlyMonthPicker
              calendar={persian}
              locale={persian_fa}
              calendarPosition="bottom-right"
              inputClass={inputClass}
              value={monthValue}
              onChange={(date) => {
                if (date) {
                  setMonthValue(date as DateObject);
                }
              }}
            />
          </div>
        </label>

        {error && (
          <div className="mt-4 text-sm font-semibold text-bad">{error}</div>
        )}

        <div className="mt-5 overflow-x-auto">
          {loading ? (
            <div className="text-sm text-muted">در حال دریافت گزارش...</div>
          ) : report.length === 0 ? (
            <div className="rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm text-muted">
              برای این ماه داده‌ای ثبت نشده است.
            </div>
          ) : (
            <table className="w-full border-collapse text-right">
              <thead>
                <tr className="text-xs font-bold text-muted">
                  <th className="px-2 py-2">پرسنل</th>
                  <th className="px-2 py-2">شیفت</th>
                  <th className="px-2 py-2">تأخیر</th>
                  <th className="px-2 py-2">زودتر</th>
                  <th className="px-2 py-2">اضافه‌کاری</th>
                  <th className="px-2 py-2">حساب</th>
                  <th className="px-2 py-2">رایگان</th>
                  <th className="px-2 py-2">خالص</th>
                </tr>
              </thead>
              <tbody>
                {report.map((row) => (
                  <tr key={row.employee_id} className="border-t border-border">
                    <td className="px-2 py-2 font-bold text-text">
                      {row.employee_name}
                    </td>
                    <td className="px-2 py-2 text-text">
                      {faNum(row.shifts_count)}
                    </td>
                    <td className="px-2 py-2 text-warn">
                      {faDuration(row.late_minutes)}
                    </td>
                    <td className="px-2 py-2 text-muted">
                      {faDuration(row.early_minutes)}
                    </td>
                    <td className="px-2 py-2 text-good">
                      {faDuration(row.overtime_minutes)}
                    </td>
                    <td className="px-2 py-2 text-text">{money(row.gross_tab)}</td>
                    <td className="px-2 py-2 text-muted">
                      {money(row.free_value)}
                      {row.free_coffee_units + row.free_shake_units > 0 && (
                        <span className="mr-1 text-xs">
                          ({faNum(row.free_coffee_units)} قهوه،{" "}
                          {faNum(row.free_shake_units)} شیک)
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-2 font-black text-text">
                      {money(row.net_tab)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-surface p-5">
        <h3 className="text-lg font-black text-text">مدیریت پرسنل</h3>
        <p className="mt-1.5 text-sm leading-6 text-muted">
          افزودن یا حذف نام پرسنل. حذف، سابقهٔ ماه‌های گذشتهٔ فرد را نگه می‌دارد.
        </p>

        <form onSubmit={addEmployee} className="mt-4 flex gap-3">
          <input
            className={`${inputClass} flex-1`}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="نام پرسنل"
            aria-label="نام پرسنل"
          />
          <Button type="submit" className="min-h-11 px-6" disabled={!newName.trim()}>
            افزودن
          </Button>
        </form>
        {rosterError && (
          <div className="mt-3 text-sm font-semibold text-bad">{rosterError}</div>
        )}

        {employees.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {employees.map((emp) => (
              <Badge key={emp.id} className="gap-2 py-1.5">
                <span className="text-text">{emp.name}</span>
                <button
                  type="button"
                  onClick={() => void removeEmployee(emp.id)}
                  className="text-bad hover:text-bad/80"
                  aria-label={`حذف ${emp.name}`}
                >
                  ✕
                </button>
              </Badge>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
