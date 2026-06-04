import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { faNum, UNIT } from "../lib/format";
import { Badge, Button } from "../components/ui";
import { RevenueValue } from "../components/RevenueValue";

type EventOrderStatus = "open" | "partially_paid" | "paid" | "closed";

type EventOrder = {
  id: number;
  mode: string;
  event_customer_label: string | null;
  subtotal: number;
  status: EventOrderStatus;
};

type ActiveEventOrder = EventOrder & {
  status: Exclude<EventOrderStatus, "closed">;
};

type CreatedOrder = {
  id: number;
};

type EventScreenProps = {
  onOpenOrder: (orderId: number) => void;
  onBack: () => void;
};

const activeStatuses = new Set<EventOrderStatus>([
  "open",
  "partially_paid",
  "paid",
]);

const statusMeta: Record<
  Exclude<EventOrderStatus, "closed">,
  { label: string; tone: "good" | "warn" | "accent" }
> = {
  open: { label: "باز", tone: "accent" },
  partially_paid: { label: "پرداخت ناقص", tone: "warn" },
  paid: { label: "تسویه‌شده", tone: "good" },
};

function isActiveEventOrder(order: EventOrder): order is ActiveEventOrder {
  return order.mode === "event" && activeStatuses.has(order.status);
}

export function EventScreen({ onOpenOrder, onBack }: EventScreenProps) {
  const [orders, setOrders] = useState<EventOrder[]>([]);
  const [label, setLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    const nextOrders = await apiGet<EventOrder[]>("/orders/");
    setOrders(nextOrders);
  }, []);

  useEffect(() => {
    let ignore = false;

    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const nextOrders = await apiGet<EventOrder[]>("/orders/");

        if (!ignore) {
          setOrders(nextOrders);
        }
      } catch {
        if (!ignore) {
          setError("دریافت سفارش‌های رویداد ناموفق بود");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    };

    void load();

    return () => {
      ignore = true;
    };
  }, []);

  const activeEventOrders = useMemo(() => {
    return orders
      .filter(isActiveEventOrder)
      .sort((a, b) => b.id - a.id);
  }, [orders]);

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      setError("نام یا شماره شخص را وارد کنید");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await apiPost<CreatedOrder>("/orders/", {
        mode: "event",
        event_customer_label: trimmedLabel,
      });
      setLabel("");
      await refresh();
    } catch {
      setError("ایجاد سفارش رویداد ناموفق بود");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-full flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-3xl font-black text-text">سفارش‌های رویداد</h2>
          <p className="mt-2 text-base text-muted">
            سفارش بدون میز برای مهمان‌های بیرون‌بر یا رویداد ثبت می‌شود.
          </p>
        </div>
        <Button variant="ghost" onClick={onBack}>
          بازگشت به میزها
        </Button>
      </div>

      {error && (
        <div className="fixed left-8 top-16 z-[60] max-w-md rounded-xl border border-bad/30 bg-[#2a1518] px-4 py-3 text-base font-semibold text-bad shadow-xl shadow-black/30">
          {error}
        </div>
      )}

      <form
        className="rounded-2xl border border-border bg-surface p-5"
        onSubmit={(event) => void handleCreate(event)}
      >
        <label
          className="block text-sm font-semibold text-muted"
          htmlFor="event-customer-label"
        >
          نام یا شماره شخص
        </label>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row">
          <input
            id="event-customer-label"
            className="min-h-12 min-w-0 flex-1 rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition placeholder:text-muted focus:border-accent"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="مثلا مهمان ۱۲"
            autoComplete="off"
          />
          <Button className="min-h-12 px-6" type="submit" disabled={isSubmitting}>
            ایجاد سفارش
          </Button>
        </div>
      </form>

      <div className="rounded-2xl border border-border bg-surface">
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="text-base font-bold text-text">سفارش‌های فعال</div>
          <Badge tone="default">{faNum(activeEventOrders.length)} سفارش</Badge>
        </div>

        {isLoading ? (
          <div className="p-8 text-lg text-muted">
            در حال دریافت سفارش‌های رویداد...
          </div>
        ) : activeEventOrders.length === 0 ? (
          <div className="p-8 text-lg text-muted">
            هنوز سفارش رویداد فعالی ثبت نشده است.
          </div>
        ) : (
          <div className="divide-y divide-border">
            {activeEventOrders.map((order) => {
              const meta = statusMeta[order.status];
              const labelText = order.event_customer_label?.trim() || "بدون نام";

              return (
                <button
                  key={order.id}
                  type="button"
                  className="grid w-full grid-cols-1 items-center gap-4 px-5 py-4 text-right transition hover:bg-surface-2 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-accent md:grid-cols-[minmax(0,1fr)_auto_auto]"
                  onClick={() => onOpenOrder(order.id)}
                >
                  <div className="min-w-0">
                    <div className="truncate text-xl font-black text-text">
                      {labelText}
                    </div>
                    <div className="mt-1 text-sm font-semibold text-muted">
                      سفارش {faNum(order.id)}
                    </div>
                  </div>
                  <span className="inline-flex items-baseline gap-2 text-xl font-black text-text">
                    <RevenueValue value={order.subtotal} />
                    <span className="text-sm text-muted">{UNIT}</span>
                  </span>
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
