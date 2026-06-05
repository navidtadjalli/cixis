import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiDelete, apiGet, apiPatch, apiPost } from "../lib/api";
import { faNum, money, UNIT } from "../lib/format";
import { Badge, Button, Modal } from "../components/ui";

type OrderStatus = "open" | "partially_paid" | "paid" | "closed";
type PaymentMethod = "cash" | "card" | "bank_transfer";

type OrderItem = {
  id: number;
  product: number;
  product_name_snapshot: string;
  unit_price_snapshot: number;
  quantity: number;
  paid_quantity: number;
  line_total: number;
};

type Payment = {
  id: number;
  amount: number;
  method: PaymentMethod;
  payer_label: string | null;
  note: string | null;
};

type Order = {
  id: number;
  order_number: string;
  mode: string;
  table: number | null;
  table_name: string | null;
  event_customer_label: string | null;
  status: OrderStatus;
  subtotal: number;
  paid_amount: number;
  remaining_amount: number;
  items: OrderItem[];
  payments: Payment[];
};

type Category = {
  id: number;
  name: string;
  sort_order: number;
};

type Product = {
  id: number;
  category: number;
  name: string;
  price: number;
  is_available: boolean;
  sort_order: number;
};

type Table = {
  id: number;
  name: string;
  active_order_id: number | null;
};

type OrderPanelProps = {
  orderId: number;
  onClose: () => void;
};

const statusMeta: Record<
  OrderStatus,
  { label: string; tone: "default" | "good" | "warn" | "accent" }
> = {
  open: { label: "باز", tone: "accent" },
  partially_paid: { label: "پرداخت ناقص", tone: "warn" },
  paid: { label: "تسویه‌شده", tone: "good" },
  closed: { label: "بسته", tone: "default" },
};

const paymentMethods: Array<{ value: PaymentMethod; label: string }> = [
  { value: "cash", label: "نقدی" },
  { value: "card", label: "کارت" },
  { value: "bank_transfer", label: "کارت‌به‌کارت" },
];

function formatMoney(value: number) {
  return `${money(value)} ${UNIT}`;
}

function mutationError(error: unknown) {
  if (error instanceof ApiError && error.status === 400) {
    return "این سفارش برای این عملیات قفل شده است";
  }

  return "خطا در ارتباط با سرور";
}

export function OrderPanel({ orderId, onClose }: OrderPanelProps) {
  const [order, setOrder] = useState<Order | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [tables, setTables] = useState<Table[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [selectedTableId, setSelectedTableId] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cash");
  // Item-based split payment: pick how many of each item this customer pays for.
  const [splitOpen, setSplitOpen] = useState(false);
  const [splitCounts, setSplitCounts] = useState<Record<number, number>>({});
  const [splitMethod, setSplitMethod] = useState<PaymentMethod>("cash");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProductsLoading, setIsProductsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isLocked = order?.status === "paid" || order?.status === "closed";
  const currentStatus = order ? statusMeta[order.status] : null;

  const sortedCategories = useMemo(() => {
    return [...categories].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
  }, [categories]);

  const sortedProducts = useMemo(() => {
    return [...products].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
  }, [products]);

  const sortedItems = useMemo(() => {
    return order ? [...order.items].sort((a, b) => a.id - b.id) : [];
  }, [order]);

  const moveTables = useMemo(() => {
    return tables
      .filter((table) => table.id !== order?.table)
      .sort((a, b) => a.id - b.id);
  }, [order?.table, tables]);

  const remaining = order?.remaining_amount ?? 0;
  // The simple payment button settles the full remaining balance in one go.
  const canSubmitPayment = !isLocked && !isSubmitting && remaining > 0;

  // Sum of the selected items in the split modal.
  const splitTotal = useMemo(
    () =>
      sortedItems.reduce(
        (sum, item) => sum + (splitCounts[item.id] ?? 0) * item.unit_price_snapshot,
        0,
      ),
    [sortedItems, splitCounts],
  );
  const overRemaining = splitTotal > remaining;
  const canSubmitSplit =
    !isLocked && !isSubmitting && splitTotal > 0 && !overRemaining;

  const refreshOrder = useCallback(async () => {
    const nextOrder = await apiGet<Order>(`/orders/${orderId}/`);
    setOrder(nextOrder);
    setSelectedTableId("");
  }, [orderId]);

  const loadProducts = useCallback(async (categoryId: number) => {
    setIsProductsLoading(true);

    try {
      const nextProducts = await apiGet<Product[]>(`/products/?category=${categoryId}`);
      setProducts(nextProducts);
    } finally {
      setIsProductsLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;

    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const [nextOrder, nextCategories, nextTables] = await Promise.all([
          apiGet<Order>(`/orders/${orderId}/`),
          apiGet<Category[]>("/categories/"),
          apiGet<Table[]>("/tables/"),
        ]);

        const sortedNextCategories = [...nextCategories].sort(
          (a, b) => a.sort_order - b.sort_order || a.id - b.id,
        );
        const firstCategoryId = sortedNextCategories[0]?.id ?? null;
        const nextProducts =
          firstCategoryId === null
            ? []
            : await apiGet<Product[]>(`/products/?category=${firstCategoryId}`);

        if (!ignore) {
          setOrder(nextOrder);
          setCategories(nextCategories);
          setTables(nextTables);
          setSelectedCategoryId(firstCategoryId);
          setProducts(nextProducts);
        }
      } catch {
        if (!ignore) {
          setError("دریافت اطلاعات سفارش ناموفق بود");
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
  }, [orderId]);

  const runMutation = async (mutation: () => Promise<void>) => {
    if (isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await mutation();
      await refreshOrder();
    } catch (caughtError) {
      setError(mutationError(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCategorySelect = (categoryId: number) => {
    if (categoryId === selectedCategoryId) {
      return;
    }

    setSelectedCategoryId(categoryId);
    setError(null);
    void loadProducts(categoryId).catch(() => {
      setError("دریافت محصولات ناموفق بود");
    });
  };

  const addProduct = (product: Product) => {
    if (isLocked || !product.is_available) {
      return;
    }

    void runMutation(async () => {
      await apiPost<OrderItem>(`/orders/${orderId}/items/`, {
        product_id: product.id,
        quantity: 1,
      });
    });
  };

  const changeQuantity = (item: OrderItem, nextQuantity: number) => {
    if (isLocked) {
      return;
    }

    if (nextQuantity < 1) {
      void removeItem(item);
      return;
    }

    void runMutation(async () => {
      await apiPatch<OrderItem>(`/order-items/${item.id}/`, {
        quantity: nextQuantity,
      });
    });
  };

  const removeItem = async (item: OrderItem) => {
    if (isLocked) {
      return;
    }

    await runMutation(async () => {
      await apiDelete<null>(`/order-items/${item.id}/`);
    });
  };

  const addPayment = () => {
    if (!canSubmitPayment) {
      return;
    }

    void runMutation(async () => {
      await apiPost<Payment>(`/orders/${orderId}/payments/`, {
        amount: remaining,
        method: paymentMethod,
      });
    });
  };

  const openSplit = () => {
    setSplitCounts({});
    setSplitMethod("cash");
    setSplitOpen(true);
  };

  // Clamp a per-item count to [0, the item's quantity].
  const setSplitCount = (itemId: number, value: number, max: number) => {
    const clamped = Math.max(0, Math.min(max, value));
    setSplitCounts((prev) => ({ ...prev, [itemId]: clamped }));
  };

  const submitSplitPayment = () => {
    if (!canSubmitSplit) {
      return;
    }
    const items = sortedItems
      .map((item) => ({ item_id: item.id, quantity: splitCounts[item.id] ?? 0 }))
      .filter((entry) => entry.quantity > 0);

    void runMutation(async () => {
      await apiPost<Payment>(`/orders/${orderId}/payments/`, {
        method: splitMethod,
        items,
      });
      setSplitOpen(false);
      setSplitCounts({});
    });
  };

  const moveOrder = (tableIdValue: string) => {
    setSelectedTableId(tableIdValue);

    const tableId = Number(tableIdValue);
    if (!Number.isFinite(tableId) || tableId <= 0) {
      return;
    }

    void runMutation(async () => {
      await apiPatch<Order>(`/orders/${orderId}/`, { table_id: tableId });
    });
  };

  return (
    <div className="flex min-h-full flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border bg-surface px-5 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-2xl font-black text-text">
              سفارش {order ? faNum(order.order_number) : ""}
            </h2>
            {currentStatus && <Badge tone={currentStatus.tone}>{currentStatus.label}</Badge>}
          </div>
          <div className="mt-2 text-sm font-semibold text-muted">
            {order?.table_name ?? order?.event_customer_label ?? "بدون میز"}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm font-semibold text-muted" htmlFor="move-order">
            انتقال سفارش
          </label>
          <select
            id="move-order"
            className="h-10 min-w-40 rounded-xl border border-border bg-surface-2 px-3 text-sm font-semibold text-text outline-none transition focus:border-accent disabled:cursor-not-allowed disabled:opacity-50"
            value={selectedTableId}
            disabled={isSubmitting || isLoading || moveTables.length === 0}
            onChange={(event) => moveOrder(event.target.value)}
          >
            <option value="">انتخاب میز</option>
            {moveTables.map((table) => (
              <option key={table.id} value={table.id}>
                {table.name}
              </option>
            ))}
          </select>
          <Button variant="ghost" onClick={onClose}>
            بستن
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-bad/30 bg-[#2a1518] px-4 py-3 text-base font-semibold text-bad">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="rounded-xl border border-border bg-surface p-8 text-lg text-muted">
          در حال دریافت سفارش...
        </div>
      ) : order === null ? (
        <div className="rounded-xl border border-border bg-surface p-8 text-lg text-muted">
          سفارش پیدا نشد.
        </div>
      ) : (
        <div className="grid min-h-[calc(100vh-15rem)] grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_26rem]">
          <section className="order-2 min-h-0 rounded-2xl border border-border bg-surface p-5 xl:order-1">
            <div className="flex gap-2 overflow-x-auto pb-3">
              {sortedCategories.length === 0 ? (
                <div className="text-sm font-semibold text-muted">دسته‌بندی ثبت نشده است</div>
              ) : (
                sortedCategories.map((category) => {
                  const isSelected = category.id === selectedCategoryId;

                  return (
                    <button
                      key={category.id}
                      type="button"
                      className={[
                        "h-10 flex-none rounded-xl border px-4 text-sm font-bold transition",
                        isSelected
                          ? "border-accent bg-accent text-[#1b1206]"
                          : "border-border bg-surface-2 text-muted hover:bg-[var(--surface-3)] hover:text-text",
                      ].join(" ")}
                      onClick={() => handleCategorySelect(category.id)}
                    >
                      {category.name}
                    </button>
                  );
                })
              )}
            </div>

            {isProductsLoading ? (
              <div className="mt-4 rounded-xl border border-border bg-surface-2 p-6 text-muted">
                در حال دریافت محصولات...
              </div>
            ) : sortedProducts.length === 0 ? (
              <div className="mt-4 rounded-xl border border-border bg-surface-2 p-6 text-muted">
                محصولی برای این دسته‌بندی ثبت نشده است.
              </div>
            ) : (
              <div className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-3">
                {sortedProducts.map((product) => {
                  const disabled = isLocked || !product.is_available || isSubmitting;

                  return (
                    <button
                      key={product.id}
                      type="button"
                      className={[
                        "min-h-32 rounded-2xl border p-4 text-right transition focus:outline-none focus:ring-2 focus:ring-accent",
                        disabled
                          ? "cursor-not-allowed border-border bg-surface-2 opacity-45"
                          : "border-border bg-surface-2 hover:-translate-y-0.5 hover:border-accent/50 hover:bg-[var(--surface-3)]",
                      ].join(" ")}
                      disabled={disabled}
                      onClick={() => addProduct(product)}
                    >
                      <div className="line-clamp-2 min-h-12 text-base font-black text-text">
                        {product.name}
                      </div>
                      <div className="mt-4 flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold text-muted">
                          {formatMoney(product.price)}
                        </span>
                        {!product.is_available && <Badge>ناموجود</Badge>}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>

          <aside className="order-1 flex min-h-0 flex-col rounded-2xl border border-border bg-surface xl:order-2">
            <div className="border-b border-border px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-xl font-black text-text">سبد سفارش</h3>
                {isLocked && <Badge tone="good">قفل پرداخت</Badge>}
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
              {sortedItems.length === 0 ? (
                <div className="rounded-xl border border-border bg-surface-2 p-5 text-sm font-semibold leading-7 text-muted">
                  هنوز آیتمی به سفارش اضافه نشده است.
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {sortedItems.map((item) => (
                    <div
                      key={item.id}
                      className="rounded-xl border border-border bg-surface-2 p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="break-words text-base font-black text-text">
                            {item.product_name_snapshot}
                          </div>
                          <div className="mt-1 text-xs font-semibold text-muted">
                            {formatMoney(item.unit_price_snapshot)}
                          </div>
                          {item.paid_quantity > 0 && (
                            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs font-black">
                              <span className="rounded-md bg-good/15 px-2 py-0.5 text-good">
                                پرداخت‌شده {faNum(item.paid_quantity)}
                              </span>
                              {item.quantity - item.paid_quantity > 0 && (
                                <span className="rounded-md bg-bad/15 px-2 py-0.5 text-bad">
                                  مانده {faNum(item.quantity - item.paid_quantity)}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                        <button
                          type="button"
                          className="grid h-8 w-8 flex-none place-items-center rounded-lg border border-border bg-surface text-lg font-black text-muted transition hover:bg-bad/10 hover:text-bad disabled:cursor-not-allowed disabled:opacity-40"
                          disabled={isLocked || isSubmitting}
                          aria-label={`حذف ${item.product_name_snapshot}`}
                          onClick={() => void removeItem(item)}
                        >
                          ×
                        </button>
                      </div>

                      <div className="mt-4 flex items-center justify-between gap-3">
                        <div className="inline-flex h-10 items-center overflow-hidden rounded-xl border border-border bg-surface">
                          <button
                            type="button"
                            className="h-10 w-10 text-lg font-black text-muted transition hover:bg-[var(--surface-3)] hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
                            disabled={isLocked || isSubmitting}
                            onClick={() => changeQuantity(item, item.quantity - 1)}
                          >
                            −
                          </button>
                          <span className="grid h-10 w-12 place-items-center border-x border-border text-sm font-black text-text">
                            {faNum(item.quantity)}
                          </span>
                          <button
                            type="button"
                            className="h-10 w-10 text-lg font-black text-muted transition hover:bg-[var(--surface-3)] hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
                            disabled={isLocked || isSubmitting}
                            onClick={() => changeQuantity(item, item.quantity + 1)}
                          >
                            +
                          </button>
                        </div>
                        <div className="text-sm font-black text-text">
                          {formatMoney(item.line_total)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="border-t border-border px-5 py-4">
              <div className="space-y-3 rounded-xl border border-border bg-surface-2 p-4">
                <div className="flex items-center justify-between gap-3 text-sm font-semibold text-muted">
                  <span>جمع سفارش</span>
                  <span className="text-text">{formatMoney(order.subtotal)}</span>
                </div>
                <div className="flex items-center justify-between gap-3 text-sm font-semibold text-muted">
                  <span>پرداخت‌شده</span>
                  <span className="text-good">{formatMoney(order.paid_amount)}</span>
                </div>
                <div className="flex items-center justify-between gap-3 text-base font-black text-text">
                  <span>مانده</span>
                  <span>{formatMoney(order.remaining_amount)}</span>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <div className="grid grid-cols-3 gap-2">
                  {paymentMethods.map((method) => (
                    <button
                      key={method.value}
                      type="button"
                      className={[
                        "h-10 rounded-xl border text-xs font-black transition disabled:cursor-not-allowed disabled:opacity-40",
                        paymentMethod === method.value
                          ? "border-accent bg-accent text-[#1b1206]"
                          : "border-border bg-surface-2 text-muted hover:bg-[var(--surface-3)] hover:text-text",
                      ].join(" ")}
                      disabled={isLocked || isSubmitting}
                      onClick={() => setPaymentMethod(method.value)}
                    >
                      {method.label}
                    </button>
                  ))}
                </div>

                <Button className="w-full" onClick={addPayment} disabled={!canSubmitPayment}>
                  پرداخت کامل ({formatMoney(remaining)})
                </Button>
                <Button
                  variant="ghost"
                  className="w-full"
                  onClick={openSplit}
                  disabled={isLocked || isSubmitting || sortedItems.length === 0}
                >
                  پرداخت تفکیکی (انتخاب اقلام)
                </Button>
              </div>
            </div>
          </aside>
        </div>
      )}

      {splitOpen && order && (
        <Modal onClose={() => setSplitOpen(false)} widthClassName="max-w-xl">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xl font-black text-text">پرداخت تفکیکی</h3>
            <span className="text-sm text-muted">
              مانده: {formatMoney(order.remaining_amount)}
            </span>
          </div>
          <p className="mt-1 text-sm text-muted">
            اقلامی که این مشتری پرداخت می‌کند و تعداد آن‌ها را انتخاب کنید.
          </p>

          <div className="mt-4 max-h-[46vh] space-y-2 overflow-y-auto pe-1">
            {sortedItems.map((item) => {
              const count = splitCounts[item.id] ?? 0;
              const unpaid = item.quantity - item.paid_quantity;
              const wouldExceed =
                splitTotal + item.unit_price_snapshot > order.remaining_amount;
              return (
                <div
                  key={item.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 px-4 py-3"
                >
                  <div className="min-w-0">
                    <div className="truncate font-bold text-text">
                      {item.product_name_snapshot}
                    </div>
                    <div className="text-xs text-muted">
                      {formatMoney(item.unit_price_snapshot)} · باقی‌مانده {faNum(unpaid)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 rounded-lg border border-border bg-surface px-1">
                      <button
                        type="button"
                        className="h-8 w-8 text-lg font-black text-muted transition hover:text-bad disabled:opacity-40"
                        disabled={count <= 0}
                        onClick={() => setSplitCount(item.id, count - 1, unpaid)}
                      >
                        −
                      </button>
                      <span className="w-7 text-center font-black text-text">
                        {faNum(count)}
                      </span>
                      <button
                        type="button"
                        className="h-8 w-8 text-lg font-black text-muted transition hover:text-accent disabled:opacity-40"
                        disabled={count >= unpaid || wouldExceed}
                        onClick={() => setSplitCount(item.id, count + 1, unpaid)}
                      >
                        +
                      </button>
                    </div>
                    <span className="w-24 text-left text-sm font-bold text-text">
                      {money(count * item.unit_price_snapshot)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex items-center justify-between gap-3 border-t border-border pt-3 text-lg font-black text-text">
            <span>جمع انتخاب‌شده</span>
            <span className="inline-flex items-baseline gap-2">
              <span>{money(splitTotal)}</span>
              <span className="text-sm text-muted">{UNIT}</span>
            </span>
          </div>
          {overRemaining && (
            <div className="mt-1 text-sm font-semibold text-bad">
              مبلغ انتخاب‌شده از مانده سفارش بیشتر است.
            </div>
          )}

          <div className="mt-4 grid grid-cols-3 gap-2">
            {paymentMethods.map((method) => (
              <button
                key={method.value}
                type="button"
                className={[
                  "h-10 rounded-xl border text-xs font-black transition",
                  splitMethod === method.value
                    ? "border-accent bg-accent text-[#1b1206]"
                    : "border-border bg-surface-2 text-muted hover:bg-[var(--surface-3)] hover:text-text",
                ].join(" ")}
                onClick={() => setSplitMethod(method.value)}
              >
                {method.label}
              </button>
            ))}
          </div>

          <div className="mt-4 flex gap-2">
            <Button
              variant="ghost"
              className="flex-1"
              onClick={() => setSplitOpen(false)}
            >
              انصراف
            </Button>
            <Button
              className="flex-1"
              onClick={submitSplitPayment}
              disabled={!canSubmitSplit}
            >
              ثبت پرداخت
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
