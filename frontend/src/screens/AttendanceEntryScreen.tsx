import { useCallback, useEffect, useMemo, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../lib/api";
import { enNum, faNum, money } from "../lib/format";
import { JalaliDateInput } from "../components/JalaliDateInput";
import { PasswordGate, useGate } from "../components/PasswordGate";
import { Badge, Button } from "../components/ui";

// Tab B (supervisor + manager): log each person's come/go per shift and put
// menu items on their bill. Gated by the day-closing (revenue) password, which
// the manager code and god code also satisfy.

type Employee = { id: number; name: string };
type Category = { id: number; name: string };
type Product = { id: number; name: string; price: number; is_available: boolean };

type Shift = "morning" | "evening";

type AttendanceRow = {
  id: number;
  employee: number;
  shift: Shift;
  check_in: string;
  check_out: string;
  is_full_day: boolean;
};

type Consumption = {
  id: number;
  employee: number;
  employee_name: string;
  shift: Shift;
  product_name_snapshot: string;
  quantity: number;
  line_total: number;
};

type RowState = {
  present: boolean;
  checkIn: string;
  checkOut: string;
  fullDay: boolean;
  existingId: number | null;
};

const SHIFT_LABEL: Record<Shift, string> = {
  morning: "۹ تا ۱۷",
  evening: "۱۶ تا ۲۴",
};

// Default clock times prefilled when a person is marked present.
const SHIFT_DEFAULTS: Record<Shift, { in: string; out: string }> = {
  morning: { in: "09:00", out: "17:00" },
  evening: { in: "16:00", out: "00:00" },
};

const FULL_DAY_TIMES = { in: "09:00", out: "00:00" };

function todayIso() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

const timeClass =
  "min-h-10 rounded-lg border border-border bg-surface-2 px-2 text-center text-base text-text outline-none transition focus:border-accent disabled:opacity-40";
const selectClass =
  "min-h-11 rounded-xl border border-border bg-surface-2 px-3 text-base font-semibold text-text outline-none transition focus:border-accent";

export function AttendanceEntryScreen() {
  const gate = useGate("/revenue/unlock/");

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [date, setDate] = useState(todayIso());
  const [shift, setShift] = useState<Shift>("morning");
  const [rows, setRows] = useState<Record<number, RowState>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Consumption entry
  const [categories, setCategories] = useState<Category[]>([]);
  const [consEmployee, setConsEmployee] = useState("");
  const [consCategory, setConsCategory] = useState("");
  const [consProducts, setConsProducts] = useState<Product[]>([]);
  const [consProduct, setConsProduct] = useState("");
  const [consQty, setConsQty] = useState("1");
  const [consumptions, setConsumptions] = useState<Consumption[]>([]);
  const [consError, setConsError] = useState<string | null>(null);

  const loadRoster = useCallback(async () => {
    const [emps, cats] = await Promise.all([
      apiGet<Employee[]>("/employees/"),
      apiGet<Category[]>("/categories/"),
    ]);
    setEmployees(emps);
    setCategories(cats);
  }, []);

  useEffect(() => {
    if (gate.unlocked) {
      void loadRoster().catch(() => setError("دریافت اطلاعات ناموفق بود"));
    }
  }, [gate.unlocked, loadRoster]);

  // Rebuild the attendance grid whenever date/shift/roster change: prefill from
  // any rows already saved for this date + shift.
  const loadAttendance = useCallback(async () => {
    if (employees.length === 0) {
      setRows({});
      return;
    }
    const existing = await apiGet<AttendanceRow[]>(
      `/attendance/?date=${date}&shift=${shift}`,
    );
    const byEmployee = new Map(existing.map((r) => [r.employee, r]));
    const next: Record<number, RowState> = {};
    for (const emp of employees) {
      const row = byEmployee.get(emp.id);
      if (row) {
        next[emp.id] = {
          present: true,
          checkIn: row.check_in.slice(0, 5),
          checkOut: row.check_out.slice(0, 5),
          fullDay: row.is_full_day,
          existingId: row.id,
        };
      } else {
        next[emp.id] = {
          present: false,
          checkIn: SHIFT_DEFAULTS[shift].in,
          checkOut: SHIFT_DEFAULTS[shift].out,
          fullDay: false,
          existingId: null,
        };
      }
    }
    setRows(next);
  }, [employees, date, shift]);

  useEffect(() => {
    if (gate.unlocked) {
      void loadAttendance().catch(() => setError("دریافت حضور ناموفق بود"));
    }
  }, [gate.unlocked, loadAttendance]);

  const loadConsumptions = useCallback(async () => {
    const list = await apiGet<Consumption[]>(
      `/staff-consumption/?date=${date}&shift=${shift}`,
    );
    setConsumptions(list);
  }, [date, shift]);

  useEffect(() => {
    if (gate.unlocked) {
      void loadConsumptions().catch(() => undefined);
    }
  }, [gate.unlocked, loadConsumptions]);

  const setRow = (employeeId: number, patch: Partial<RowState>) => {
    setRows((current) => ({
      ...current,
      [employeeId]: { ...current[employeeId], ...patch },
    }));
  };

  const togglePresent = (employeeId: number) => {
    const row = rows[employeeId];
    setRow(employeeId, { present: !row.present });
  };

  const toggleFullDay = (employeeId: number) => {
    const row = rows[employeeId];
    const fullDay = !row.fullDay;
    setRow(employeeId, {
      fullDay,
      // Prefill the spanning times for convenience when turning full day on.
      ...(fullDay
        ? { checkIn: FULL_DAY_TIMES.in, checkOut: FULL_DAY_TIMES.out }
        : {}),
    });
  };

  const saveAttendance = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      for (const emp of employees) {
        const row = rows[emp.id];
        if (row.present) {
          await apiPost("/attendance/", {
            employee: emp.id,
            business_date: date,
            shift,
            check_in: row.checkIn,
            check_out: row.checkOut,
            is_full_day: row.fullDay,
          });
        } else if (row.existingId !== null) {
          // Was saved before, now unchecked — remove it.
          await apiDelete(`/attendance/${row.existingId}/`);
        }
      }
      setMessage("حضور ذخیره شد.");
      await loadAttendance();
    } catch {
      setError("ذخیره حضور ناموفق بود");
    } finally {
      setSaving(false);
    }
  };

  const onSelectConsCategory = async (categoryId: string) => {
    setConsCategory(categoryId);
    setConsProduct("");
    setConsProducts([]);
    if (!categoryId) {
      return;
    }
    try {
      setConsProducts(await apiGet<Product[]>(`/products/?category=${categoryId}`));
    } catch {
      setConsError("دریافت محصولات ناموفق بود");
    }
  };

  const addConsumption = async () => {
    setConsError(null);
    if (!consEmployee || !consProduct) {
      setConsError("پرسنل و محصول را انتخاب کنید");
      return;
    }
    const quantity = Number(enNum(consQty).replace(/[٫٬،,]/g, "."));
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setConsError("تعداد باید عددی بزرگ‌تر از صفر باشد");
      return;
    }
    try {
      await apiPost("/staff-consumption/", {
        employee: Number(consEmployee),
        product: Number(consProduct),
        quantity,
        business_date: date,
        shift,
      });
      setConsProduct("");
      setConsQty("1");
      await loadConsumptions();
    } catch {
      setConsError("افزودن به فیش ناموفق بود");
    }
  };

  const removeConsumption = async (id: number) => {
    try {
      await apiDelete(`/staff-consumption/${id}/`);
      setConsumptions((current) => current.filter((c) => c.id !== id));
    } catch {
      setConsError("حذف ناموفق بود");
    }
  };

  const dayTabTotal = useMemo(
    () => consumptions.reduce((sum, c) => sum + c.line_total, 0),
    [consumptions],
  );

  if (!gate.unlocked) {
    return (
      <PasswordGate
        title="ثبت حضور و مصرف"
        prompt="برای ثبت حضور و غیاب و فیش پرسنل، رمز عبور بستن روز را وارد کنید."
        onSubmit={gate.unlock}
      />
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h2 className="text-3xl font-black text-text">ثبت حضور و مصرف</h2>
        <p className="mt-2 text-base text-muted">
          آمد و رفت هر پرسنل را در هر شیفت و آنچه از منو مصرف می‌کند ثبت کنید.
        </p>
      </div>

      <section className="rounded-2xl border border-border bg-surface p-5">
        <div className="flex flex-wrap items-end gap-4">
          <label className="block">
            <span className="text-sm font-bold text-text">تاریخ</span>
            <div className="mt-1.5">
              <JalaliDateInput value={date} onChange={(iso) => setDate(iso || todayIso())} />
            </div>
          </label>
          <label className="block">
            <span className="text-sm font-bold text-text">شیفت</span>
            <select
              className={`${selectClass} mt-1.5 block`}
              value={shift}
              onChange={(e) => setShift(e.target.value as Shift)}
              aria-label="شیفت"
            >
              <option value="morning">شیفت {SHIFT_LABEL.morning}</option>
              <option value="evening">شیفت {SHIFT_LABEL.evening}</option>
            </select>
          </label>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-bad/30 bg-[#2a1518] px-4 py-3 text-sm font-semibold text-bad">
            {error}
          </div>
        )}
        {message && (
          <div className="mt-4 rounded-xl border border-good/30 bg-good/10 px-4 py-3 text-sm font-semibold text-good">
            {message}
          </div>
        )}

        {employees.length === 0 ? (
          <div className="mt-4 rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm text-muted">
            هنوز پرسنلی ثبت نشده است. از تب «گزارش ماهانه پرسنل» می‌توانید نام‌ها را
            اضافه کنید.
          </div>
        ) : (
          <>
            <div className="mt-5 overflow-x-auto">
              <table className="w-full border-collapse text-right">
                <thead>
                  <tr className="text-xs font-bold text-muted">
                    <th className="px-2 py-2">حاضر</th>
                    <th className="px-2 py-2">پرسنل</th>
                    <th className="px-2 py-2">ورود</th>
                    <th className="px-2 py-2">خروج</th>
                    <th className="px-2 py-2">تمام‌وقت (۲ شیفت)</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map((emp) => {
                    const row = rows[emp.id];
                    if (!row) {
                      return null;
                    }
                    return (
                      <tr key={emp.id} className="border-t border-border">
                        <td className="px-2 py-2">
                          <input
                            type="checkbox"
                            className="h-5 w-5 accent-[var(--accent)]"
                            checked={row.present}
                            onChange={() => togglePresent(emp.id)}
                            aria-label={`حاضر ${emp.name}`}
                          />
                        </td>
                        <td className="px-2 py-2 font-bold text-text">{emp.name}</td>
                        <td className="px-2 py-2">
                          <input
                            type="time"
                            dir="ltr"
                            className={timeClass}
                            value={row.checkIn}
                            disabled={!row.present}
                            onChange={(e) =>
                              setRow(emp.id, { checkIn: e.target.value })
                            }
                          />
                        </td>
                        <td className="px-2 py-2">
                          <input
                            type="time"
                            dir="ltr"
                            className={timeClass}
                            value={row.checkOut}
                            disabled={!row.present}
                            onChange={(e) =>
                              setRow(emp.id, { checkOut: e.target.value })
                            }
                          />
                        </td>
                        <td className="px-2 py-2">
                          <input
                            type="checkbox"
                            className="h-5 w-5 accent-[var(--accent)]"
                            checked={row.fullDay}
                            disabled={!row.present}
                            onChange={() => toggleFullDay(emp.id)}
                            aria-label={`تمام‌وقت ${emp.name}`}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Button
              className="mt-5 min-h-11 px-6"
              disabled={saving}
              onClick={() => void saveAttendance()}
            >
              {saving ? "در حال ذخیره..." : "ذخیره حضور"}
            </Button>
          </>
        )}
      </section>

      <section className="rounded-2xl border border-border bg-surface p-5">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <h3 className="text-lg font-black text-text">
            فیش پرسنل (شیفت {SHIFT_LABEL[shift]})
          </h3>
          <Badge tone="accent">جمع: {money(dayTabTotal)}</Badge>
        </div>

        <div className="grid gap-3 sm:grid-cols-[1.2fr_1.2fr_1.4fr_0.7fr_auto]">
          <select
            className={selectClass}
            value={consEmployee}
            onChange={(e) => setConsEmployee(e.target.value)}
            aria-label="پرسنل"
          >
            <option value="">پرسنل...</option>
            {employees.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.name}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            value={consCategory}
            onChange={(e) => void onSelectConsCategory(e.target.value)}
            aria-label="دسته‌بندی"
          >
            <option value="">دسته‌بندی...</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            value={consProduct}
            onChange={(e) => setConsProduct(e.target.value)}
            aria-label="محصول"
            disabled={consProducts.length === 0}
          >
            <option value="">محصول...</option>
            {consProducts.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <input
            className={`${selectClass} text-center`}
            inputMode="decimal"
            dir="ltr"
            value={consQty}
            onChange={(e) => setConsQty(e.target.value)}
            onFocus={(e) => e.currentTarget.select()}
            aria-label="تعداد"
            placeholder="مثلاً ۰٫۵"
          />
          <Button
            className="min-h-11 whitespace-nowrap px-6"
            onClick={() => void addConsumption()}
          >
            افزودن به فیش
          </Button>
        </div>
        {consError && (
          <div className="mt-3 text-sm font-semibold text-bad">{consError}</div>
        )}

        {consumptions.length > 0 && (
          <div className="mt-5 flex flex-col gap-2">
            {consumptions.map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between rounded-xl border border-border bg-surface-2 px-4 py-2"
              >
                <div className="flex items-center gap-3">
                  <span className="font-bold text-text">{c.employee_name}</span>
                  <span className="text-muted">
                    {c.product_name_snapshot} × {faNum(c.quantity)}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="font-semibold text-text">{money(c.line_total)}</span>
                  <button
                    type="button"
                    onClick={() => void removeConsumption(c.id)}
                    className="text-xs font-bold text-bad hover:underline"
                  >
                    حذف
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
