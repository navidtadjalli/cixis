import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiDelete, apiGet, apiPatch, apiPost } from "../lib/api";
import { enNum, faNum } from "../lib/format";
import { Badge, Button } from "../components/ui";

// Majaz door list (Story 2): generate a range of invite codes, then record the
// guest party against each — name, headcount, men/women split, entry paid.

type GuestCode = {
  id: number;
  code: string;
  guest_name: string;
  guest_count: number;
  men_count: number;
  women_count: number;
  paid_entry: boolean;
};

type Row = {
  id: number;
  code: string;
  guest_name: string;
  guest_count: string;
  men_count: string;
  women_count: string;
  paid_entry: boolean;
};

type BulkResult = { created: number; skipped: number };

const toRow = (c: GuestCode): Row => ({
  id: c.id,
  code: c.code,
  guest_name: c.guest_name,
  guest_count: c.guest_count ? String(c.guest_count) : "",
  men_count: c.men_count ? String(c.men_count) : "",
  women_count: c.women_count ? String(c.women_count) : "",
  paid_entry: c.paid_entry,
});

const num = (value: string) => Number(enNum(value.trim())) || 0;

const inputClass =
  "min-h-10 w-full rounded-lg border border-border bg-surface-2 px-3 text-base text-text outline-none transition focus:border-accent";
const cellNumClass =
  "min-h-10 w-16 rounded-lg border border-border bg-surface-2 px-2 text-center text-base text-text outline-none transition focus:border-accent";

function detail(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const body = error.body as { detail?: string } | null;
    if (body?.detail) {
      return body.detail;
    }
  }
  return fallback;
}

export function GuestCodesScreen() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [prefix, setPrefix] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await apiGet<GuestCode[]>("/guest-codes/");
      setRows(list.map(toRow));
      setLoadError(null);
    } catch {
      setLoadError("دریافت کدها ناموفق بود");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const generate = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await apiPost<BulkResult>("/guest-codes/bulk/", {
        prefix: prefix.trim(),
        start: enNum(start.trim()),
        end: enNum(end.trim()),
      });
      setMessage(
        `${faNum(result.created)} کد ساخته شد` +
          (result.skipped ? ` — ${faNum(result.skipped)} کد از قبل وجود داشت.` : "."),
      );
      setStart("");
      setEnd("");
      await refresh();
    } catch (caught) {
      setError(detail(caught, "ساخت کدها ناموفق بود"));
    } finally {
      setBusy(false);
    }
  };

  const setField = (id: number, patch: Partial<Row>) => {
    setRows((current) =>
      current.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    );
  };

  const persist = async (row: Row) => {
    try {
      await apiPatch(`/guest-codes/${row.id}/`, {
        guest_name: row.guest_name.trim(),
        guest_count: num(row.guest_count),
        men_count: num(row.men_count),
        women_count: num(row.women_count),
        paid_entry: row.paid_entry,
      });
    } catch {
      setError("ذخیره تغییرات این کد ناموفق بود");
    }
  };

  const togglePaid = async (row: Row) => {
    const next = { ...row, paid_entry: !row.paid_entry };
    setField(row.id, { paid_entry: next.paid_entry });
    await persist(next);
  };

  const remove = async (id: number) => {
    try {
      await apiDelete(`/guest-codes/${id}/`);
      setRows((current) => current.filter((row) => row.id !== id));
    } catch {
      setError("حذف کد ناموفق بود");
    }
  };

  const totals = useMemo(
    () =>
      rows.reduce(
        (acc, row) => {
          acc.guests += num(row.guest_count);
          acc.men += num(row.men_count);
          acc.women += num(row.women_count);
          if (row.paid_entry) {
            acc.paid += 1;
          }
          return acc;
        },
        { guests: 0, men: 0, women: 0, paid: 0 },
      ),
    [rows],
  );

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h2 className="text-3xl font-black text-text">کدهای مهمان</h2>
        <p className="mt-2 text-base text-muted">
          یک بازه کد بسازید و برای هر کد نام مهمان، تعداد همراهان، تفکیک زن/مرد و
          پرداخت ورودی را ثبت کنید.
        </p>
      </div>

      <form
        onSubmit={generate}
        className="rounded-2xl border border-border bg-surface p-5"
      >
        <h3 className="text-lg font-black text-text">ساخت کد</h3>
        <p className="mt-1.5 text-sm leading-6 text-muted">
          برای هر شماره از شروع تا پایان (هر دو شامل) یک کد ساخته می‌شود؛ مثلا «الف»
          از ۱ تا ۳ یعنی الف۱، الف۲ و الف۳.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-[1.4fr_1fr_1fr_auto]">
          <input
            className={inputClass}
            value={prefix}
            onChange={(e) => setPrefix(e.target.value)}
            placeholder="پیشوند"
            aria-label="پیشوند"
            autoComplete="off"
          />
          <input
            className={inputClass}
            inputMode="numeric"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            placeholder="از شماره"
            aria-label="از شماره"
            autoComplete="off"
          />
          <input
            className={inputClass}
            inputMode="numeric"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            placeholder="تا شماره"
            aria-label="تا شماره"
            autoComplete="off"
          />
          <Button
            type="submit"
            className="min-h-10 whitespace-nowrap px-6"
            disabled={busy || !start.trim() || !end.trim()}
          >
            {busy ? "در حال ساخت..." : "ساخت کدها"}
          </Button>
        </div>
        {error && (
          <div className="mt-3 text-sm font-semibold text-bad">{error}</div>
        )}
        {message && (
          <div className="mt-3 text-sm font-semibold text-good">{message}</div>
        )}
      </form>

      <section className="rounded-2xl border border-border bg-surface p-5">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <h3 className="text-lg font-black text-text">فهرست کدها</h3>
          <Badge tone="accent">{`${faNum(rows.length)} کد`}</Badge>
          <Badge>{`مهمان‌ها: ${faNum(totals.guests)}`}</Badge>
          <Badge>{`مرد: ${faNum(totals.men)}`}</Badge>
          <Badge>{`زن: ${faNum(totals.women)}`}</Badge>
          <Badge tone="good">{`پرداخت‌شده: ${faNum(totals.paid)}`}</Badge>
        </div>

        {loadError && (
          <div className="text-sm font-semibold text-bad">{loadError}</div>
        )}

        {loading ? (
          <div className="text-sm text-muted">در حال دریافت کدها...</div>
        ) : rows.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface-2 px-4 py-3 text-sm text-muted">
            هنوز کدی ساخته نشده است.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-right">
              <thead>
                <tr className="text-xs font-bold text-muted">
                  <th className="px-2 py-2">کد</th>
                  <th className="px-2 py-2">نام مهمان</th>
                  <th className="px-2 py-2">تعداد همراه</th>
                  <th className="px-2 py-2">مرد</th>
                  <th className="px-2 py-2">زن</th>
                  <th className="px-2 py-2">ورودی</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t border-border">
                    <td className="px-2 py-2 font-black text-text" dir="ltr">
                      {row.code}
                    </td>
                    <td className="px-2 py-2">
                      <input
                        className={inputClass}
                        value={row.guest_name}
                        onChange={(e) =>
                          setField(row.id, { guest_name: e.target.value })
                        }
                        onBlur={() => void persist(row)}
                        placeholder="نام"
                      />
                    </td>
                    <td className="px-2 py-2">
                      <input
                        className={cellNumClass}
                        inputMode="numeric"
                        value={row.guest_count}
                        onChange={(e) =>
                          setField(row.id, { guest_count: e.target.value })
                        }
                        onBlur={() => void persist(row)}
                        aria-label={`تعداد همراه ${row.code}`}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <input
                        className={cellNumClass}
                        inputMode="numeric"
                        value={row.men_count}
                        onChange={(e) =>
                          setField(row.id, { men_count: e.target.value })
                        }
                        onBlur={() => void persist(row)}
                        aria-label={`مرد ${row.code}`}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <input
                        className={cellNumClass}
                        inputMode="numeric"
                        value={row.women_count}
                        onChange={(e) =>
                          setField(row.id, { women_count: e.target.value })
                        }
                        onBlur={() => void persist(row)}
                        aria-label={`زن ${row.code}`}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <button
                        type="button"
                        onClick={() => void togglePaid(row)}
                        className={[
                          "rounded-lg border px-3 py-1.5 text-xs font-bold transition",
                          row.paid_entry
                            ? "border-good/30 bg-good/10 text-good"
                            : "border-border bg-surface-2 text-muted hover:text-text",
                        ].join(" ")}
                      >
                        {row.paid_entry ? "پرداخت‌شده" : "پرداخت‌نشده"}
                      </button>
                    </td>
                    <td className="px-2 py-2 text-left">
                      <button
                        type="button"
                        onClick={() => void remove(row.id)}
                        className="rounded-lg border border-bad/40 px-3 py-1.5 text-xs font-bold text-bad transition hover:bg-bad/10"
                      >
                        حذف
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
