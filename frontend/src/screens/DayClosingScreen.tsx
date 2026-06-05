import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import camelIcon from "../assets/camel.png";
import { ApiError, apiGet, apiPost } from "../lib/api";
import { faNum, money, UNIT } from "../lib/format";
import { Badge, Button, Modal } from "../components/ui";

type ResourceSuggestion = {
  resource_name: string;
  reason: string;
  suggested_quantity: number;
};

type UnresolvedOrder = {
  id: number;
  order_number: string;
  table_name: string | null;
  status: string;
  remaining_amount: number;
};

type ClosingPreview = {
  total_sales: number;
  cash_total: number;
  card_total: number;
  bank_transfer_total: number;
  orders_count: number;
  closed_orders_count: number;
  open_orders_count: number;
  table_usage_count: number;
  purchases_total: number;
  resource_suggestions: ResourceSuggestion[];
  unresolved_orders: UnresolvedOrder[];
};

type Purchase = {
  id: number;
  name: string;
  quantity: number;
  unit: string;
  cost: number;
  note?: string | null;
  created_at?: string;
};

type PurchaseForm = {
  name: string;
  quantity: string;
  unit: string;
  cost: string;
};

type ClosingResult = ClosingPreview & {
  id: number;
  business_date: string;
  sync_status: SyncStatus;
  synced_at: string | null;
  backup_path: string | null;
};

type SyncStatus = "synced" | "pending" | "failed" | string;

type SyncRetryResult = {
  synced: number;
  failed: number;
  total: number;
};

type MonthlyDaily = {
  business_date: string;
  total_sales: number;
  orders_count: number;
  cash_total?: number;
  card_total?: number;
  bank_transfer_total?: number;
  purchases_total?: number;
};

type MonthlyReport = {
  year: number;
  month: number;
  total_sales: number;
  cash_total: number;
  card_total: number;
  bank_transfer_total: number;
  purchases_total: number;
  days_count: number;
  daily: MonthlyDaily[];
};

type Toast = {
  tone: "good" | "bad" | "warn";
  message: string;
};

const emptyPurchaseForm: PurchaseForm = {
  name: "",
  quantity: "",
  unit: "",
  cost: "",
};

const syncMeta: Partial<
  Record<string, { label: string; tone: "good" | "warn" | "bad" }>
> = {
  synced: { label: "همگام‌شده", tone: "good" },
  pending: { label: "در انتظار همگام‌سازی", tone: "warn" },
  failed: { label: "ناموفق", tone: "bad" },
};

function todayLocalDate() {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function defaultMonth() {
  const now = new Date();
  return {
    year: String(now.getFullYear()),
    month: String(now.getMonth() + 1),
  };
}

function basename(path: string | null) {
  if (!path) {
    return "ثبت نشده";
  }

  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;
}

function apiMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const body = error.body;

    if (
      body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      return body.detail;
    }
  }

  return fallback;
}

function parsePositiveNumber(value: string) {
  const normalized = value
    .trim()
    .replace(/[۰-۹]/g, (digit) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)))
    .replace(/[٠-٩]/g, (digit) => String("٠١٢٣٤٥٦٧٨٩".indexOf(digit)))
    .replace(/[,٬]/g, "");
  const parsed = Number(normalized);

  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function parseInteger(value: string) {
  const parsed = parsePositiveNumber(value);
  return parsed === null ? null : Math.trunc(parsed);
}

function statusBadge(status: SyncStatus) {
  return syncMeta[status] ?? { label: status || "نامشخص", tone: "default" as const };
}

function StatCard({
  label,
  children,
  sub,
}: {
  label: string;
  children: ReactNode;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface px-5 py-4">
      <div className="text-sm font-semibold text-muted">{label}</div>
      <div className="mt-2 text-3xl font-black text-text">{children}</div>
      {sub && <div className="mt-2 text-sm font-semibold text-muted">{sub}</div>}
    </div>
  );
}

function CamelEatingGrassIcon({ className = "" }: { className?: string }) {
  return (
    <img src={camelIcon} alt="" aria-hidden="true" className={className} />
  );
}

function RevenueWithUnit({
  value,
  className = "",
}: {
  value: number | null | undefined;
  className?: string;
}) {
  return (
    <span className={["inline-flex items-baseline gap-2", className].join(" ")}>
      <span>{money(value ?? 0)}</span>
      <span className="text-sm text-muted">{UNIT}</span>
    </span>
  );
}

export function DayClosingScreen() {
  const [preview, setPreview] = useState<ClosingPreview | null>(null);
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [purchaseForm, setPurchaseForm] = useState<PurchaseForm>(emptyPurchaseForm);
  const [closingResult, setClosingResult] = useState<ClosingResult | null>(null);
  const [confirmClose, setConfirmClose] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmittingPurchase, setIsSubmittingPurchase] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [isRetryingSync, setIsRetryingSync] = useState(false);
  const [monthForm, setMonthForm] = useState(defaultMonth);
  const [monthlyReport, setMonthlyReport] = useState<MonthlyReport | null>(null);
  const [isMonthlyLoading, setIsMonthlyLoading] = useState(false);

  const today = useMemo(() => todayLocalDate(), []);

  const showToast = useCallback((nextToast: Toast) => {
    setToast(nextToast);
    window.setTimeout(() => setToast(null), 4_000);
  }, []);

  const loadPreview = useCallback(async () => {
    const nextPreview = await apiGet<ClosingPreview>("/day-closing/preview/");
    setPreview(nextPreview);
  }, []);

  const loadPurchases = useCallback(async () => {
    const nextPurchases = await apiGet<Purchase[]>(
      `/resources/purchases/?date=${today}`,
    );
    setPurchases(nextPurchases);
  }, [today]);

  const loadInitial = useCallback(async () => {
    setIsLoading(true);

    try {
      await Promise.all([loadPreview(), loadPurchases()]);
      setToast(null);
    } catch {
      showToast({ tone: "bad", message: "دریافت اطلاعات بستن روز ناموفق بود" });
    } finally {
      setIsLoading(false);
    }
  }, [loadPreview, loadPurchases, showToast]);

  const loadMonthlyReport = useCallback(async (yearValue: string, monthValue: string) => {
    const year = parseInteger(yearValue);
    const month = parseInteger(monthValue);

    if (year === null || month === null || month < 1 || month > 12) {
      showToast({ tone: "warn", message: "سال و ماه گزارش را درست وارد کنید" });
      return;
    }

    setIsMonthlyLoading(true);

    try {
      const report = await apiGet<MonthlyReport>(
        `/reports/monthly/?year=${year}&month=${month}`,
      );
      setMonthlyReport(report);
    } catch {
      showToast({ tone: "bad", message: "دریافت گزارش ماهانه ناموفق بود" });
    } finally {
      setIsMonthlyLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    void loadMonthlyReport(monthForm.year, monthForm.month);
    // Load the default current-month report once; form submits handle later reloads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadMonthlyReport]);

  const submitPurchase = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const name = purchaseForm.name.trim();
    const unit = purchaseForm.unit.trim();
    const quantity = parsePositiveNumber(purchaseForm.quantity);
    const cost = parsePositiveNumber(purchaseForm.cost);

    if (!name || !unit || quantity === null || cost === null) {
      showToast({ tone: "warn", message: "نام، تعداد، واحد و هزینه را کامل وارد کنید" });
      return;
    }

    setIsSubmittingPurchase(true);

    try {
      await apiPost<Purchase>("/resources/purchases/", {
        name,
        quantity,
        unit,
        cost,
      });
      setPurchaseForm(emptyPurchaseForm);
      await Promise.all([loadPurchases(), loadPreview()]);
      showToast({ tone: "good", message: "خرید ثبت شد" });
    } catch {
      showToast({ tone: "bad", message: "ثبت خرید ناموفق بود" });
    } finally {
      setIsSubmittingPurchase(false);
    }
  };

  const closeDay = async (confirm: boolean) => {
    setIsClosing(true);

    try {
      const result = await apiPost<ClosingResult>("/day-closing/close/", { confirm });
      setClosingResult(result);
      setConfirmClose(false);
      await loadPreview();
      showToast({ tone: "good", message: "روز بسته شد" });
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 400) {
        const body = caughtError.body as Partial<ClosingPreview> | null;

        if (body?.unresolved_orders && body.unresolved_orders.length > 0) {
          setPreview((current) =>
            current
              ? { ...current, unresolved_orders: body.unresolved_orders ?? [] }
              : current,
          );
        }
      }

      showToast({
        tone: "bad",
        message: apiMessage(caughtError, "بستن روز ناموفق بود"),
      });
    } finally {
      setIsClosing(false);
    }
  };

  const handleCloseClick = () => {
    if ((preview?.open_orders_count ?? 0) > 0) {
      setConfirmClose(true);
      return;
    }

    void closeDay(true);
  };

  const retrySync = async () => {
    if (!closingResult) {
      return;
    }

    setIsRetryingSync(true);

    try {
      const result = await apiPost<SyncRetryResult>("/sync/retry/");
      const sync_status =
        result.failed > 0 ? "failed" : result.synced > 0 ? "synced" : "pending";

      setClosingResult({ ...closingResult, sync_status });
      showToast({
        tone: result.failed > 0 ? "warn" : "good",
        message: `نتیجه همگام‌سازی: ${faNum(result.synced)} موفق از ${faNum(result.total)}`,
      });
    } catch {
      showToast({ tone: "bad", message: "تلاش مجدد همگام‌سازی ناموفق بود" });
    } finally {
      setIsRetryingSync(false);
    }
  };

  const currentSync = closingResult ? statusBadge(closingResult.sync_status) : null;
  const showRetry =
    closingResult?.sync_status === "pending" || closingResult?.sync_status === "failed";

  return (
    <>
      <div className="flex min-h-full flex-col gap-6">
        {toast && (
          <div
            className={[
              "fixed left-8 top-16 z-[60] max-w-md rounded-xl border px-4 py-3 text-base font-semibold shadow-xl shadow-black/30",
              toast.tone === "good"
                ? "border-good/30 bg-good/10 text-good"
                : toast.tone === "warn"
                  ? "border-warn/30 bg-warn/10 text-warn"
                  : "border-bad/30 bg-[#2a1518] text-bad",
            ].join(" ")}
          >
            {toast.message}
          </div>
        )}

        {isLoading ? (
          <div className="rounded-xl border border-border bg-surface p-8 text-lg text-muted">
            در حال دریافت اطلاعات بستن روز...
          </div>
        ) : (
          <>
            <section className="rounded-2xl border border-border bg-surface p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-black text-text">پیش‌نمایش بستن روز</h2>
                  <p className="mt-1 text-sm font-semibold text-muted">
                    وضعیت سفارش‌ها، پرداخت‌ها و استفاده از میزها برای امروز
                  </p>
                </div>
                <Button onClick={handleCloseClick} disabled={isClosing || !preview}>
                  {isClosing ? "در حال بستن..." : "بستن روز"}
                </Button>
              </div>

              <div className="mt-5 grid grid-cols-[repeat(auto-fit,minmax(12rem,1fr))] gap-4">
                <StatCard label="فروش کل">
                  <RevenueWithUnit value={preview?.total_sales} />
                </StatCard>
                <StatCard label="نقدی">
                  <RevenueWithUnit value={preview?.cash_total} />
                </StatCard>
                <StatCard label="کارت">
                  <RevenueWithUnit value={preview?.card_total} />
                </StatCard>
                <StatCard label="انتقال بانکی">
                  <RevenueWithUnit value={preview?.bank_transfer_total} />
                </StatCard>
                <StatCard label="تعداد فیش‌ها">
                  {faNum(preview?.orders_count ?? 0)}
                </StatCard>
                <StatCard label="سفارش بسته">
                  {faNum(preview?.closed_orders_count ?? 0)}
                </StatCard>
                <div className="flex items-center gap-4 rounded-xl border border-border bg-surface px-5 py-4">
                  <CamelEatingGrassIcon className="h-14 w-14 shrink-0 object-contain" />
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-muted">
                      سفارش باز
                    </span>
                    <span className="mt-2 text-3xl font-black text-text">
                      {faNum(preview?.open_orders_count ?? 0)}
                    </span>
                  </div>
                </div>
                <StatCard label="استفاده از میز">
                  {faNum(preview?.table_usage_count ?? 0)}
                </StatCard>
              </div>

              {preview && preview.unresolved_orders.length > 0 && (
                <div className="mt-5 rounded-xl border border-warn/30 bg-warn/10 p-4">
                  <div className="text-base font-black text-warn">
                    سفارش‌های باز پیش از بستن روز
                  </div>
                  <div className="mt-3 grid gap-2">
                    {preview.unresolved_orders.map((order) => (
                      <div
                        key={order.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warn/20 bg-surface/60 px-4 py-3"
                      >
                        <div>
                          <div className="font-bold text-text">
                            سفارش {order.table_name ?? "بدون میز"}
                          </div>
                          <div className="mt-1 text-sm font-semibold text-muted">
                            {order.status}
                          </div>
                        </div>
                        <RevenueWithUnit
                          value={order.remaining_amount}
                          className="text-lg font-black text-warn"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {closingResult && currentSync && (
                <div className="mt-5 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-surface-2 px-5 py-4">
                  <div>
                    <div className="text-sm font-semibold text-muted">پشتیبان روزانه</div>
                    <div className="mt-1 text-lg font-black text-text">
                      {basename(closingResult.backup_path)}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <Badge tone={currentSync.tone}>{currentSync.label}</Badge>
                    {showRetry && (
                      <Button
                        variant="ghost"
                        onClick={() => void retrySync()}
                        disabled={isRetryingSync}
                      >
                        {isRetryingSync ? "در حال تلاش..." : "تلاش مجدد همگام‌سازی"}
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </section>

            <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-2xl border border-border bg-surface p-6">
                <h2 className="text-2xl font-black text-text">خرید منابع</h2>
                <form
                  className="mt-5 grid gap-3 md:grid-cols-4"
                  onSubmit={(event) => void submitPurchase(event)}
                >
                  <input
                    className="rounded-xl border border-border bg-surface-2 px-4 py-3 text-base font-semibold text-text outline-none transition focus:border-accent"
                    placeholder="نام"
                    value={purchaseForm.name}
                    onChange={(event) =>
                      setPurchaseForm({ ...purchaseForm, name: event.target.value })
                    }
                  />
                  <input
                    className="rounded-xl border border-border bg-surface-2 px-4 py-3 text-base font-semibold text-text outline-none transition focus:border-accent"
                    inputMode="decimal"
                    placeholder="تعداد"
                    value={purchaseForm.quantity}
                    onChange={(event) =>
                      setPurchaseForm({ ...purchaseForm, quantity: event.target.value })
                    }
                  />
                  <input
                    className="rounded-xl border border-border bg-surface-2 px-4 py-3 text-base font-semibold text-text outline-none transition focus:border-accent"
                    placeholder="واحد"
                    value={purchaseForm.unit}
                    onChange={(event) =>
                      setPurchaseForm({ ...purchaseForm, unit: event.target.value })
                    }
                  />
                  <input
                    className="rounded-xl border border-border bg-surface-2 px-4 py-3 text-base font-semibold text-text outline-none transition focus:border-accent"
                    inputMode="decimal"
                    placeholder="هزینه"
                    value={purchaseForm.cost}
                    onChange={(event) =>
                      setPurchaseForm({ ...purchaseForm, cost: event.target.value })
                    }
                  />
                  <Button
                    className="md:col-span-4"
                    type="submit"
                    disabled={isSubmittingPurchase}
                  >
                    {isSubmittingPurchase ? "در حال ثبت..." : "ثبت خرید"}
                  </Button>
                </form>

                <div className="mt-5 grid gap-2">
                  {purchases.length === 0 ? (
                    <div className="rounded-xl border border-border bg-surface-2 px-4 py-4 text-sm font-semibold text-muted">
                      امروز خریدی ثبت نشده است.
                    </div>
                  ) : (
                    purchases.map((purchase) => (
                      <div
                        key={purchase.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 px-4 py-3"
                      >
                        <div>
                          <div className="font-bold text-text">{purchase.name}</div>
                          <div className="mt-1 text-sm font-semibold text-muted">
                            {faNum(purchase.quantity)} {purchase.unit}
                          </div>
                        </div>
                        <RevenueWithUnit
                          value={purchase.cost}
                          className="text-lg font-black text-text"
                        />
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-border bg-surface p-6">
                <h2 className="text-2xl font-black text-text">پیشنهادهای منابع</h2>
                <div className="mt-5 grid gap-3">
                  {!preview || preview.resource_suggestions.length === 0 ? (
                    <div className="rounded-xl border border-border bg-surface-2 px-4 py-4 text-sm font-semibold text-muted">
                      پیشنهادی برای امروز ثبت نشده است.
                    </div>
                  ) : (
                    preview.resource_suggestions.map((suggestion) => (
                      <div
                        key={`${suggestion.resource_name}-${suggestion.reason}`}
                        className="rounded-xl border border-border bg-surface-2 px-4 py-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="font-black text-text">
                            {suggestion.resource_name}
                          </div>
                          <Badge tone="accent">
                            {faNum(suggestion.suggested_quantity)} پیشنهادی
                          </Badge>
                        </div>
                        <div className="mt-2 text-sm font-semibold leading-7 text-muted">
                          {suggestion.reason}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>

            <details className="rounded-2xl border border-border bg-surface p-6" open>
              <summary className="cursor-pointer list-none text-2xl font-black text-text">
                گزارش ماهانه
              </summary>
              <div className="mt-5 flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="mt-1 text-sm font-semibold text-muted">
                    جمع‌بندی فروش، پرداخت‌ها و روزهای کاری ماه
                  </p>
                </div>
                <form
                  className="flex flex-wrap items-end gap-3"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void loadMonthlyReport(monthForm.year, monthForm.month);
                  }}
                >
                  <label className="block text-sm font-semibold text-muted">
                    سال
                    <input
                      className="mt-2 w-28 rounded-xl border border-border bg-surface-2 px-3 py-2 text-base font-semibold text-text outline-none transition focus:border-accent"
                      inputMode="numeric"
                      value={monthForm.year}
                      onChange={(event) =>
                        setMonthForm({ ...monthForm, year: event.target.value })
                      }
                    />
                  </label>
                  <label className="block text-sm font-semibold text-muted">
                    ماه
                    <input
                      className="mt-2 w-20 rounded-xl border border-border bg-surface-2 px-3 py-2 text-base font-semibold text-text outline-none transition focus:border-accent"
                      inputMode="numeric"
                      value={monthForm.month}
                      onChange={(event) =>
                        setMonthForm({ ...monthForm, month: event.target.value })
                      }
                    />
                  </label>
                  <Button type="submit" disabled={isMonthlyLoading}>
                    {isMonthlyLoading ? "در حال دریافت..." : "نمایش"}
                  </Button>
                </form>
              </div>

              <div className="mt-5 grid grid-cols-[repeat(auto-fit,minmax(12rem,1fr))] gap-4">
                <StatCard label="فروش ماه">
                  <RevenueWithUnit value={monthlyReport?.total_sales} />
                </StatCard>
                <StatCard label="نقدی">
                  <RevenueWithUnit value={monthlyReport?.cash_total} />
                </StatCard>
                <StatCard label="کارت">
                  <RevenueWithUnit value={monthlyReport?.card_total} />
                </StatCard>
                <StatCard label="انتقال بانکی">
                  <RevenueWithUnit value={monthlyReport?.bank_transfer_total} />
                </StatCard>
                <StatCard label="خرید ماه">
                  <RevenueWithUnit value={monthlyReport?.purchases_total} />
                </StatCard>
                <StatCard label="روز کاری">
                  {faNum(monthlyReport?.days_count ?? 0)}
                </StatCard>
              </div>

              <div className="mt-5 overflow-hidden rounded-xl border border-border">
                <div className="grid grid-cols-[1fr_0.8fr_0.8fr] gap-3 border-b border-border bg-surface-2 px-4 py-3 text-sm font-black text-muted">
                  <div>تاریخ</div>
                  <div>سفارش</div>
                  <div className="text-left">فروش</div>
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {isMonthlyLoading ? (
                    <div className="px-4 py-6 text-center text-sm font-semibold text-muted">
                      در حال دریافت گزارش...
                    </div>
                  ) : !monthlyReport || monthlyReport.daily.length === 0 ? (
                    <div className="px-4 py-6 text-center text-sm font-semibold text-muted">
                      گزارشی برای این ماه ثبت نشده است.
                    </div>
                  ) : (
                    monthlyReport.daily.map((day) => (
                      <div
                        key={day.business_date}
                        className="grid grid-cols-[1fr_0.8fr_0.8fr] gap-3 border-b border-border/70 px-4 py-3 text-sm font-semibold last:border-b-0"
                      >
                        <div className="text-text">{faNum(day.business_date)}</div>
                        <div className="text-muted">{faNum(day.orders_count)}</div>
                        <RevenueWithUnit
                          value={day.total_sales}
                          className="justify-end text-left font-black text-text"
                        />
                      </div>
                    ))
                  )}
                </div>
              </div>
            </details>
          </>
        )}
      </div>

      {confirmClose && (
        <Modal onClose={() => setConfirmClose(false)}>
          <div className="mb-5">
            <h2 className="text-2xl font-black text-text">بستن روز با سفارش باز</h2>
          </div>
          <p className="rounded-xl border border-warn/30 bg-warn/10 px-4 py-3 text-base font-semibold leading-8 text-warn">
            <CamelEatingGrassIcon className="ml-1 inline-block h-5 w-5 align-text-bottom" />
            {faNum(preview?.open_orders_count ?? 0)} سفارش هنوز باز است. ادامه دادن
            روز را با تایید مدیر می‌بندد.
          </p>
          <div className="mt-6 flex gap-3">
            <Button
              className="flex-1"
              variant="ghost"
              onClick={() => setConfirmClose(false)}
              disabled={isClosing}
            >
              انصراف
            </Button>
            <Button
              className="flex-1"
              onClick={() => void closeDay(true)}
              disabled={isClosing}
            >
              {isClosing ? "در حال بستن..." : "تایید و بستن روز"}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}
