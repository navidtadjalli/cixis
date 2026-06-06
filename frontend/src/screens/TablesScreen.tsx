import { useMemo, useState } from "react";
import { ApiError, apiPost } from "../lib/api";
import { faTime, money, UNIT } from "../lib/format";
import { Button } from "../components/ui";

type TableStatus =
  | "empty"
  | "occupied"
  | "partially_paid"
  | "paid"
  | "needs_attention";

export type Table = {
  id: number;
  name: string;
  sort_order: number;
  active_order_id: number | null;
  active_order_total: number | null;
  active_order_created_at: string | null;
  status: TableStatus;
};

type CreatedOrder = {
  id: number;
};

type TablesScreenProps = {
  tables: Table[];
  isLoading: boolean;
  loadError: string | null;
  refresh: () => Promise<void>;
  onOpenOrder: (orderId: number, tableId: number) => void;
  onEventMode: () => void;
};

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 409) {
    return "میز دارای سفارش باز است";
  }

  return "خطا در ارتباط با سرور";
}

export function TablesScreen({
  tables,
  isLoading,
  loadError,
  refresh,
  onOpenOrder,
  onEventMode,
}: TablesScreenProps) {
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const sortedTables = useMemo(() => {
    return [...tables].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
  }, [tables]);

  const handleTableClick = async (table: Table) => {
    if (isSubmitting) {
      return;
    }

    if (table.active_order_id !== null) {
      onOpenOrder(table.active_order_id, table.id);
      return;
    }

    if (table.status !== "empty") {
      setError("برای این میز سفارش فعالی پیدا نشد");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const order = await apiPost<CreatedOrder>("/orders/", {
        mode: "table",
        table_id: table.id,
      });
      await refresh();
      onOpenOrder(order.id, table.id);
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const shownError = error ?? loadError;

  return (
    <div className="flex min-h-full flex-col gap-6">
      <div className="flex flex-wrap items-center justify-end gap-3">
        <Button variant="ghost" onClick={onEventMode}>
          حالت رویداد
        </Button>
      </div>

      {shownError && (
        <div className="fixed left-8 top-16 z-[60] max-w-md rounded-xl border border-bad/30 bg-[#2a1518] px-4 py-3 text-base font-semibold text-bad shadow-xl shadow-black/30">
          {shownError}
        </div>
      )}

      {isLoading ? (
        <div className="rounded-xl border border-border bg-surface p-8 text-lg text-muted">
          در حال دریافت میزها...
        </div>
      ) : sortedTables.length === 0 ? (
        <div className="rounded-xl border border-border bg-surface p-8 text-lg text-muted">
          هنوز میزی ثبت نشده است.
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] items-start gap-4">
          {sortedTables.map((table) => {
            const hasOrder = table.active_order_id !== null;

            // Tables holding an order are drawn as circles; free tables stay as
            // plain rectangular cards. No status badge — shape carries it.
            if (hasOrder) {
              return (
                <div
                  key={table.id}
                  role="button"
                  tabIndex={0}
                  data-testid="table-card"
                  className="flex aspect-square flex-col items-center justify-center gap-1 rounded-full border border-accent/40 bg-surface p-4 text-center shadow-lg shadow-black/10 ring-1 ring-accent/10 transition hover:-translate-y-0.5 hover:bg-surface-2 focus:outline-none focus:ring-2 focus:ring-accent"
                  onClick={() => void handleTableClick(table)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      void handleTableClick(table);
                    }
                  }}
                >
                  <div className="max-w-full truncate text-lg font-black text-text">
                    {table.name}
                  </div>
                  {table.active_order_created_at && (
                    <div className="text-xs font-black text-muted">
                      {faTime(table.active_order_created_at)}
                    </div>
                  )}
                  <div className="inline-flex items-baseline gap-1 text-base font-black text-text">
                    <span>{money(table.active_order_total ?? 0)}</span>
                    <span className="text-xs text-muted">{UNIT}</span>
                  </div>
                </div>
              );
            }

            return (
              <div
                key={table.id}
                role="button"
                tabIndex={0}
                data-testid="table-card"
                className="flex aspect-square items-center justify-center rounded-xl border border-border bg-surface p-3 text-center shadow-md shadow-black/10 transition hover:-translate-y-0.5 hover:bg-surface-2 focus:outline-none focus:ring-2 focus:ring-accent"
                onClick={() => void handleTableClick(table)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    void handleTableClick(table);
                  }
                }}
              >
                <div className="truncate text-xl font-black text-text">
                  {table.name}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
