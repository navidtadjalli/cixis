import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../lib/api";
import { enNum, faNum, money, UNIT } from "../lib/format";
import { brand } from "../brand.generated";
import { Badge, Button } from "../components/ui";

// CiXiS calls these event orders; Majaz calls them invite codes. Same flow,
// brand-supplied wording.
const t = brand.events;

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
  const [search, setSearch] = useState("");
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
          setError(t.loadError);
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
    const collator = new Intl.Collator("fa", { numeric: true });
    const query = enNum(search.trim()).toLowerCase();

    return orders
      .filter(isActiveEventOrder)
      .filter((order) => {
        if (!query) {
          return true;
        }
        const labelText = enNum(order.event_customer_label?.trim() ?? "").toLowerCase();
        return labelText.includes(query);
      })
      .sort((a, b) => {
        const aLabel = a.event_customer_label?.trim() ?? "";
        const bLabel = b.event_customer_label?.trim() ?? "";
        return collator.compare(enNum(aLabel), enNum(bLabel));
      });
  }, [orders, search]);

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      setError(t.identifierMissing);
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
      setError(t.createError);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-full flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-3xl font-black text-text">{t.title}</h2>
          <p className="mt-2 text-base text-muted">{t.subtitle}</p>
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
          {t.identifierLabel}
        </label>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row">
          <input
            id="event-customer-label"
            className="min-h-12 min-w-0 flex-1 rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition placeholder:text-muted focus:border-accent"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            placeholder={t.identifierPlaceholder}
            autoComplete="off"
          />
          <Button className="min-h-12 px-6" type="submit" disabled={isSubmitting}>
            {t.createAction}
          </Button>
        </div>
      </form>

      <div className="rounded-2xl border border-border bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="text-base font-bold text-text">{t.activeTitle}</div>
          <div className="flex items-center gap-3">
            <input
              type="search"
              className="min-h-10 w-44 rounded-xl border border-border bg-surface-2 px-3 py-2 text-base font-semibold text-text outline-none transition placeholder:text-muted focus:border-accent"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t.searchPlaceholder}
              autoComplete="off"
            />
            <Badge tone="default">
              {faNum(activeEventOrders.length)} {t.countUnit}
            </Badge>
          </div>
        </div>

        {isLoading ? (
          <div className="p-8 text-lg text-muted">{t.loading}</div>
        ) : activeEventOrders.length === 0 ? (
          <div className="p-8 text-lg text-muted">
            {search.trim() ? t.notFound : t.empty}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-4">
            {activeEventOrders.map((order) => {
              const meta = statusMeta[order.status];
              const labelText = order.event_customer_label?.trim() || "بدون نام";

              return (
                <button
                  key={order.id}
                  type="button"
                  className="flex flex-col gap-2 rounded-xl border border-border bg-surface-2 p-3 text-right transition hover:border-accent focus:outline-none focus:ring-2 focus:ring-accent"
                  onClick={() => onOpenOrder(order.id)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="truncate text-lg font-black text-text">
                      {labelText}
                    </div>
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                  </div>
                  <div className="text-xs font-semibold text-muted">
                    سفارش {faNum(order.id)}
                  </div>
                  <span className="mt-auto inline-flex items-baseline gap-1 text-base font-black text-text">
                    <span>{money(order.subtotal)}</span>
                    <span className="text-xs text-muted">{UNIT}</span>
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
