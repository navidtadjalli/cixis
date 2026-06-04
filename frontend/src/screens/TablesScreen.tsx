import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiDelete, apiGet, apiPatch, apiPost } from "../lib/api";
import { faNum, money, UNIT } from "../lib/format";
import { Badge, Button, Modal } from "../components/ui";

type TableStatus =
  | "empty"
  | "occupied"
  | "partially_paid"
  | "paid"
  | "needs_attention";

type Table = {
  id: number;
  name: string;
  sort_order: number;
  active_order_id: number | null;
  active_order_total: number | null;
  status: TableStatus;
};

type CreatedOrder = {
  id: number;
};

type ClosingPreview = {
  total_sales: number;
};

type TablesScreenProps = {
  onOpenOrder: (orderId: number, tableId: number) => void;
  onEventMode: () => void;
};

type DialogState =
  | { type: "add"; name: string }
  | { type: "rename"; table: Table; name: string }
  | { type: "delete"; table: Table }
  | null;

const statusMeta: Record<
  TableStatus,
  { label: string; tone: "default" | "good" | "warn" | "bad" | "accent" }
> = {
  empty: { label: "خالی", tone: "default" },
  occupied: { label: "در حال سرویس", tone: "accent" },
  partially_paid: { label: "پرداخت ناقص", tone: "warn" },
  paid: { label: "پرداخت‌شده", tone: "good" },
  needs_attention: { label: "نیازمند بررسی", tone: "bad" },
};

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 409) {
    return "میز دارای سفارش باز است";
  }

  return "خطا در ارتباط با سرور";
}

export function TablesScreen({ onOpenOrder, onEventMode }: TablesScreenProps) {
  const [tables, setTables] = useState<Table[]>([]);
  const [preview, setPreview] = useState<ClosingPreview | null>(null);
  const [dialog, setDialog] = useState<DialogState>(null);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    const [tableList, nextPreview] = await Promise.all([
      apiGet<Table[]>("/tables/"),
      apiGet<ClosingPreview>("/day-closing/preview/"),
    ]);

    setTables(tableList);
    setPreview(nextPreview);
  }, []);

  useEffect(() => {
    let ignore = false;

    const load = async () => {
      try {
        const [tableList, nextPreview] = await Promise.all([
          apiGet<Table[]>("/tables/"),
          apiGet<ClosingPreview>("/day-closing/preview/"),
        ]);

        if (!ignore) {
          setTables(tableList);
          setPreview(nextPreview);
          setError(null);
        }
      } catch {
        if (!ignore) {
          setError("دریافت اطلاعات میزها ناموفق بود");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    };

    void load();
    const intervalId = window.setInterval(() => {
      void load();
    }, 30_000);

    return () => {
      ignore = true;
      window.clearInterval(intervalId);
    };
  }, []);

  const counts = useMemo(() => {
    return tables.reduce(
      (acc, table) => {
        if (table.status === "empty") {
          acc.empty += 1;
        } else {
          acc.occupied += 1;
        }

        return acc;
      },
      { empty: 0, occupied: 0 },
    );
  }, [tables]);

  const sortedTables = useMemo(() => {
    return [...tables].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
  }, [tables]);

  const runMutation = async (mutation: () => Promise<void>) => {
    setIsSubmitting(true);
    setError(null);

    try {
      await mutation();
      await refresh();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTableClick = async (table: Table) => {
    if (openMenuId !== null || isSubmitting) {
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

  const submitAdd = () => {
    if (dialog?.type !== "add") {
      return;
    }

    const name = dialog.name.trim();
    if (!name) {
      setError("نام میز را وارد کنید");
      return;
    }

    void runMutation(async () => {
      await apiPost<Table>("/tables/", { name });
      setDialog(null);
    });
  };

  const submitRename = () => {
    if (dialog?.type !== "rename") {
      return;
    }

    const name = dialog.name.trim();
    if (!name) {
      setError("نام میز را وارد کنید");
      return;
    }

    void runMutation(async () => {
      await apiPatch<Table>(`/tables/${dialog.table.id}/`, { name });
      setDialog(null);
    });
  };

  const submitDelete = () => {
    if (dialog?.type !== "delete") {
      return;
    }

    void runMutation(async () => {
      await apiDelete<null>(`/tables/${dialog.table.id}/`);
      setDialog(null);
    });
  };

  const closeDialog = () => {
    if (!isSubmitting) {
      setDialog(null);
    }
  };

  return (
    <>
      <div className="flex min-h-full flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap gap-3">
            <div className="rounded-xl border border-border bg-surface px-5 py-4">
              <div className="text-sm font-semibold text-muted">در حال سرویس</div>
              <div className="mt-1 text-3xl font-black text-text">
                {faNum(counts.occupied)}
              </div>
            </div>
            <div className="rounded-xl border border-border bg-surface px-5 py-4">
              <div className="text-sm font-semibold text-muted">خالی</div>
              <div className="mt-1 text-3xl font-black text-text">
                {faNum(counts.empty)}
              </div>
            </div>
            <div className="rounded-xl border border-border bg-surface px-5 py-4">
              <div className="text-sm font-semibold text-muted">فروش امروز</div>
              <div className="mt-1 inline-flex items-baseline gap-2 text-3xl font-black text-text">
                <span>{money(preview?.total_sales ?? 0)}</span>
                <span className="text-sm text-muted">{UNIT}</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button variant="ghost" onClick={onEventMode}>
              حالت رویداد
            </Button>
            <Button onClick={() => setDialog({ type: "add", name: "" })}>
              افزودن میز
            </Button>
          </div>
        </div>

        {error && (
          <div className="fixed left-8 top-16 z-[60] max-w-md rounded-xl border border-bad/30 bg-[#2a1518] px-4 py-3 text-base font-semibold text-bad shadow-xl shadow-black/30">
            {error}
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
          <div className="grid grid-cols-[repeat(auto-fit,minmax(13rem,1fr))] gap-4">
            {sortedTables.map((table) => {
              const meta = statusMeta[table.status];
              const isEmpty = table.status === "empty";

              return (
                <div
                  key={table.id}
                  role="button"
                  tabIndex={0}
                  className={[
                    "relative min-h-48 rounded-2xl border bg-surface p-5 text-right shadow-lg shadow-black/10 transition hover:-translate-y-0.5 hover:bg-surface-2 focus:outline-none focus:ring-2 focus:ring-accent",
                    isEmpty
                      ? "border-border"
                      : "border-accent/40 ring-1 ring-accent/10",
                  ].join(" ")}
                  onClick={() => void handleTableClick(table)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      void handleTableClick(table);
                    }
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-3xl font-black text-text">
                        {table.name}
                      </div>
                      <div className="mt-3">
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                      </div>
                    </div>

                    <div
                      className="relative"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <button
                        type="button"
                        className="grid h-10 w-10 place-items-center rounded-xl border border-border bg-surface-2 text-xl font-black text-muted transition hover:bg-[var(--surface-3)] hover:text-text"
                        aria-label={`عملیات ${table.name}`}
                        onClick={() =>
                          setOpenMenuId((currentId) =>
                            currentId === table.id ? null : table.id,
                          )
                        }
                      >
                        ⋯
                      </button>

                      {openMenuId === table.id && (
                        <div className="absolute left-0 top-12 z-10 w-36 overflow-hidden rounded-xl border border-border bg-surface-2 shadow-xl shadow-black/30">
                          <button
                            type="button"
                            className="block w-full px-4 py-3 text-right text-sm font-semibold text-text hover:bg-[var(--surface-3)]"
                            onClick={() => {
                              setOpenMenuId(null);
                              setDialog({
                                type: "rename",
                                table,
                                name: table.name,
                              });
                            }}
                          >
                            تغییر نام
                          </button>
                          <button
                            type="button"
                            className="block w-full px-4 py-3 text-right text-sm font-semibold text-bad hover:bg-bad/10"
                            onClick={() => {
                              setOpenMenuId(null);
                              setDialog({ type: "delete", table });
                            }}
                          >
                            حذف
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="absolute inset-x-5 bottom-5 flex items-end justify-between gap-3 border-t border-border pt-4">
                    <span className="text-sm font-semibold text-muted">مبلغ سفارش</span>
                    <span className="inline-flex items-baseline gap-2 text-2xl font-black text-text">
                      <span>{money(table.active_order_total ?? 0)}</span>
                      <span className="text-sm text-muted">{UNIT}</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {dialog?.type === "add" && (
        <Modal onClose={closeDialog}>
          <div className="mb-5">
            <h2 className="text-2xl font-black text-text">افزودن میز</h2>
          </div>
          <label className="block text-sm font-semibold text-muted" htmlFor="table-name">
            نام میز
          </label>
          <input
            id="table-name"
            className="mt-2 w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition focus:border-accent"
            autoFocus
            value={dialog.name}
            onChange={(event) =>
              setDialog({ type: "add", name: event.target.value })
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                submitAdd();
              }
            }}
          />
          <div className="mt-6 flex gap-3">
            <Button className="flex-1" variant="ghost" onClick={closeDialog}>
              انصراف
            </Button>
            <Button className="flex-1" onClick={submitAdd} disabled={isSubmitting}>
              ثبت میز
            </Button>
          </div>
        </Modal>
      )}

      {dialog?.type === "rename" && (
        <Modal onClose={closeDialog}>
          <div className="mb-5">
            <h2 className="text-2xl font-black text-text">تغییر نام میز</h2>
          </div>
          <label
            className="block text-sm font-semibold text-muted"
            htmlFor="rename-table-name"
          >
            نام میز
          </label>
          <input
            id="rename-table-name"
            className="mt-2 w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition focus:border-accent"
            autoFocus
            value={dialog.name}
            onChange={(event) =>
              setDialog({ ...dialog, name: event.target.value })
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                submitRename();
              }
            }}
          />
          <div className="mt-6 flex gap-3">
            <Button className="flex-1" variant="ghost" onClick={closeDialog}>
              انصراف
            </Button>
            <Button className="flex-1" onClick={submitRename} disabled={isSubmitting}>
              ذخیره
            </Button>
          </div>
        </Modal>
      )}

      {dialog?.type === "delete" && (
        <Modal onClose={closeDialog}>
          <div className="mb-5">
            <h2 className="text-2xl font-black text-text">حذف میز</h2>
          </div>
          <p className="rounded-xl border border-warn/30 bg-warn/10 px-4 py-3 text-base font-semibold leading-8 text-warn">
            میز «{dialog.table.name}» حذف شود؟
          </p>
          <div className="mt-6 flex gap-3">
            <Button className="flex-1" variant="ghost" onClick={closeDialog}>
              انصراف
            </Button>
            <Button
              className="flex-1 bg-bad text-[#1b0a0a] hover:bg-bad/90"
              onClick={submitDelete}
              disabled={isSubmitting}
            >
              حذف میز
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}
