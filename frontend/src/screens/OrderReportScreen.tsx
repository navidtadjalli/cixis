import { FormEvent, useCallback, useEffect, useState } from "react";
import { JalaliDateInput } from "../components/JalaliDateInput";
import { Badge, Button } from "../components/ui";
import { apiGet } from "../lib/api";
import { faNum, faTime, money, UNIT } from "../lib/format";

type Table = { id: number; name: string; sort_order: number };
type OrderItem = { product_name: string; quantity: number; unit_price: number; line_total: number };
type Payment = { amount: number; method: string; payer_label: string | null };
type PaidOrder = {
  id: number;
  order_number: number;
  table_name: string | null;
  status: string;
  subtotal: number;
  paid_amount: number;
  remaining_amount: number;
  closed_at: string | null;
  items: OrderItem[];
  payments: Payment[];
};
type PaidOrdersReport = { business_date: string; table_id: number | null; orders: PaidOrder[] };

const paymentMethodLabels: Record<string, string> = {
  cash: "نقدی",
  card: "کارت",
  bank_transfer: "کارت‌به‌کارت",
};
const orderStatusLabels: Record<string, string> = { paid: "پرداخت‌شده", closed: "بسته‌شده" };

function todayLocalDate() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10);
}

function Receipt({ order }: { order: PaidOrder }) {
  const columns = "grid grid-cols-[1.6fr_0.5fr_1fr_1fr] gap-2";
  return (
    <article data-testid={`paid-order-${order.id}`} className="rounded-xl border border-border bg-surface px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="font-bold text-text">سفارش {faNum(order.order_number)}{order.table_name ? ` · ${order.table_name}` : ""}</div>
        <div className="flex items-center gap-3">
          {order.closed_at && <span className="text-sm font-semibold text-muted">{faTime(order.closed_at)}</span>}
          <Badge tone="good">{orderStatusLabels[order.status] ?? order.status}</Badge>
        </div>
      </div>
      <div className="mt-3 overflow-hidden rounded-lg border border-border/70">
        <div className={`${columns} bg-surface-2 px-3 py-2 text-xs font-black text-muted`}>
          <div>نام</div><div>تعداد</div><div>قیمت واحد</div><div className="text-left">جمع</div>
        </div>
        {order.items.length === 0 ? (
          <div className="px-3 py-2 text-sm font-semibold text-muted">بدون آیتم</div>
        ) : order.items.map((item, index) => (
          <div key={index} className={`${columns} border-t border-border/50 px-3 py-2 text-sm font-semibold`}>
            <div className="text-text">{item.product_name}</div><div className="text-muted">×{faNum(item.quantity)}</div>
            <div className="text-muted">{money(item.unit_price)}</div><div className="text-left font-black text-text">{money(item.line_total)}</div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border/70 pt-3 text-sm font-semibold">
        <span className="text-muted">جمع فیش</span><Money value={order.subtotal} className="font-black text-text" />
        <span className="text-muted">پرداخت‌شده</span><Money value={order.paid_amount} className="font-black text-good" />
      </div>
      {order.payments.length > 0 && <div className="mt-2 flex flex-wrap gap-2">
        {order.payments.map((payment, index) => (
          <span key={index} className="rounded-lg border border-border bg-surface-2 px-3 py-1 text-sm font-semibold text-text">
            {paymentMethodLabels[payment.method] ?? payment.method} {money(payment.amount)}{payment.payer_label ? ` · ${payment.payer_label}` : ""}
          </span>
        ))}
      </div>}
    </article>
  );
}

function Money({ value, className }: { value: number; className?: string }) {
  return <span className={["inline-flex items-baseline gap-2", className].filter(Boolean).join(" ")}><span>{money(value)}</span><span className="text-sm text-muted">{UNIT}</span></span>;
}

export function OrderReportScreen() {
  const [businessDate, setBusinessDate] = useState(todayLocalDate);
  const [tableId, setTableId] = useState("");
  const [tables, setTables] = useState<Table[]>([]);
  const [orders, setOrders] = useState<PaidOrder[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrders = useCallback(async (date: string, selectedTableId: string) => {
    const params = new URLSearchParams({ business_date: date });
    if (selectedTableId) params.set("table_id", selectedTableId);
    setIsLoading(true);
    setError(null);
    try {
      const report = await apiGet<PaidOrdersReport>(`/reports/orders/?${params}`);
      setOrders(report.orders);
    } catch {
      setOrders([]);
      setError("دریافت گزارش سفارش‌ها ناموفق بود");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void apiGet<Table[]>("/tables/").then(setTables).catch(() => setTables([]));
    void loadOrders(businessDate, tableId);
    // Filters are applied only when the form is submitted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadOrders]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void loadOrders(businessDate, tableId);
  };

  return (
    <div className="flex min-h-full flex-col gap-6">
      <section className="rounded-2xl border border-border bg-surface p-6">
        <h2 className="text-2xl font-black text-text">گزارش سفارش‌ها</h2>
        <p className="mt-1 text-sm font-semibold text-muted">فقط سفارش‌های تسویه‌شده، از جدید به قدیم</p>
        <form onSubmit={submit} className="mt-5 flex flex-wrap items-end gap-4">
          <label className="grid gap-1 text-sm font-bold text-muted"><span>روز</span><JalaliDateInput value={businessDate} onChange={setBusinessDate} /></label>
          <label htmlFor="orders-report-table" className="grid gap-1 text-sm font-bold text-muted">
            <span>میز</span>
            <select id="orders-report-table" value={tableId} onChange={(event) => setTableId(event.target.value)} className="w-44 rounded-xl border border-border bg-surface-2 px-3 py-2 text-base font-semibold text-text outline-none focus:border-accent">
              <option value="">همهٔ میزها</option>
              {tables.map((table) => <option key={table.id} value={table.id}>{table.name}</option>)}
            </select>
          </label>
          <Button type="submit" disabled={!businessDate || isLoading}>اعمال فیلتر</Button>
        </form>
      </section>
      {error ? <div className="rounded-xl border border-bad/30 bg-[#2a1518] p-5 text-sm font-semibold text-bad">{error}</div>
      : isLoading ? <div className="rounded-xl border border-border bg-surface p-6 text-muted">در حال دریافت سفارش‌ها...</div>
      : orders.length === 0 ? <div className="rounded-xl border border-border bg-surface p-6 text-muted">سفارش تسویه‌شده‌ای برای این فیلتر پیدا نشد.</div>
      : <section className="grid gap-3"><div className="text-sm font-bold text-muted">{faNum(orders.length)} فیش</div>{orders.map((order) => <Receipt key={order.id} order={order} />)}</section>}
    </div>
  );
}
