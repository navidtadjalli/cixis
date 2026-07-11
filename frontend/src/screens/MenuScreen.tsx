import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiDelete, apiGet, apiPatch, apiPost } from "../lib/api";
import { faNum, money, UNIT } from "../lib/format";
import { Badge, Button, Modal } from "../components/ui";

type Category = {
  id: number;
  name: string;
  sort_order: number;
  is_active: boolean;
};

type Product = {
  id: number;
  category: number;
  name: string;
  description: string;
  price: number;
  is_available: boolean;
  is_publishable: boolean;
  sort_order: number;
};

type PublishResponse = {
  success: boolean;
  published_at?: string;
  error?: string;
};

type ProductFormState = {
  name: string;
  price: string;
  category: string;
  description: string;
  is_available: boolean;
  is_publishable: boolean;
};

type ProductFormValues = {
  name: string;
  price: number;
  category: number;
  description: string;
  is_available: boolean;
  is_publishable: boolean;
};

type DialogState =
  | { type: "add-category"; name: string }
  | { type: "rename-category"; category: Category; name: string }
  | { type: "delete-category"; category: Category }
  | { type: "add-product"; form: ProductFormState }
  | { type: "edit-product"; product: Product; form: ProductFormState }
  | { type: "delete-product"; product: Product }
  | null;

type Toast = {
  tone: "good" | "bad";
  message: string;
};

const emptyProductForm = (categoryId: number | null): ProductFormState => ({
  name: "",
  price: "",
  category: categoryId === null ? "" : String(categoryId),
  description: "",
  is_available: true,
  is_publishable: true,
});

function productFormFromProduct(product: Product): ProductFormState {
  return {
    name: product.name,
    price: String(product.price),
    category: String(product.category),
    description: product.description ?? "",
    is_available: product.is_available,
    is_publishable: product.is_publishable,
  };
}

function sortByOrder<T extends { id: number; sort_order: number }>(items: T[]) {
  return [...items].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
}

function formatMoney(value: number) {
  return `${money(value)} ${UNIT}`;
}

function apiMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const body = error.body;

    if (
      body &&
      typeof body === "object" &&
      "error" in body &&
      typeof body.error === "string"
    ) {
      return body.error;
    }
  }

  return fallback;
}

function publishBodyFromError(error: unknown) {
  if (error instanceof ApiError) {
    return error.body as Partial<PublishResponse> | null;
  }

  return null;
}

export function MenuScreen() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [dialog, setDialog] = useState<DialogState>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProductsLoading, setIsProductsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);

  const sortedCategories = useMemo(() => sortByOrder(categories), [categories]);
  const sortedProducts = useMemo(() => sortByOrder(products), [products]);
  const selectedCategory = sortedCategories.find(
    (category) => category.id === selectedCategoryId,
  );

  const showToast = useCallback((nextToast: Toast) => {
    setToast(nextToast);
    window.setTimeout(() => setToast(null), 4_000);
  }, []);

  const loadProducts = useCallback(async (categoryId: number | null) => {
    if (categoryId === null) {
      setProducts([]);
      return;
    }

    setIsProductsLoading(true);

    try {
      const nextProducts = await apiGet<Product[]>(
        `/products/?category=${categoryId}`,
      );
      setProducts(nextProducts);
    } finally {
      setIsProductsLoading(false);
    }
  }, []);

  const loadInitial = useCallback(async () => {
    setIsLoading(true);

    try {
      const nextCategories = await apiGet<Category[]>("/categories/");
      const orderedCategories = sortByOrder(nextCategories);
      const firstCategoryId = orderedCategories[0]?.id ?? null;
      const nextProducts =
        firstCategoryId === null
          ? []
          : await apiGet<Product[]>(`/products/?category=${firstCategoryId}`);

      setCategories(nextCategories);
      setSelectedCategoryId(firstCategoryId);
      setProducts(nextProducts);
      setToast(null);
    } catch {
      showToast({ tone: "bad", message: "دریافت منو ناموفق بود" });
    } finally {
      setIsLoading(false);
    }
  }, [showToast]);

  const refreshCategories = useCallback(async () => {
    const nextCategories = await apiGet<Category[]>("/categories/");
    const orderedCategories = sortByOrder(nextCategories);

    setCategories(nextCategories);
    setSelectedCategoryId((currentId) => {
      if (orderedCategories.length === 0) {
        return null;
      }

      if (currentId !== null && orderedCategories.some((item) => item.id === currentId)) {
        return currentId;
      }

      return orderedCategories[0].id;
    });

    return orderedCategories;
  }, []);

  const refreshProducts = useCallback(async () => {
    await loadProducts(selectedCategoryId);
  }, [loadProducts, selectedCategoryId]);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  const runMutation = async (
    mutation: () => Promise<void>,
    fallbackMessage = "خطا در ارتباط با سرور",
  ) => {
    if (isSubmitting) {
      return;
    }

    setIsSubmitting(true);

    try {
      await mutation();
      setDialog(null);
    } catch (caughtError) {
      showToast({
        tone: "bad",
        message: apiMessage(caughtError, fallbackMessage),
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCategorySelect = (categoryId: number) => {
    if (categoryId === selectedCategoryId) {
      return;
    }

    setSelectedCategoryId(categoryId);
    void loadProducts(categoryId).catch(() => {
      showToast({ tone: "bad", message: "دریافت محصولات ناموفق بود" });
    });
  };

  const moveCategory = (category: Category, direction: -1 | 1) => {
    const currentIndex = sortedCategories.findIndex((item) => item.id === category.id);
    const neighbor = sortedCategories[currentIndex + direction];

    if (!neighbor || isSubmitting) {
      return;
    }

    void runMutation(async () => {
      await Promise.all([
        apiPatch<Category>(`/categories/${category.id}/`, {
          sort_order: neighbor.sort_order,
        }),
        apiPatch<Category>(`/categories/${neighbor.id}/`, {
          sort_order: category.sort_order,
        }),
      ]);
      await refreshCategories();
    });
  };

  const submitCategory = () => {
    if (dialog?.type !== "add-category" && dialog?.type !== "rename-category") {
      return;
    }

    const name = dialog.name.trim();
    if (!name) {
      showToast({ tone: "bad", message: "نام دسته‌بندی را وارد کنید" });
      return;
    }

    void runMutation(async () => {
      if (dialog.type === "add-category") {
        const created = await apiPost<Category>("/categories/", { name });
        const nextCategories = await refreshCategories();
        const nextSelectedId = created.id ?? nextCategories[0]?.id ?? null;
        setSelectedCategoryId(nextSelectedId);
        await loadProducts(nextSelectedId);
      } else {
        await apiPatch<Category>(`/categories/${dialog.category.id}/`, { name });
        await refreshCategories();
      }
    });
  };

  const submitDeleteCategory = () => {
    if (dialog?.type !== "delete-category") {
      return;
    }

    void runMutation(async () => {
      await apiDelete<null>(`/categories/${dialog.category.id}/`);
      const nextCategories = await refreshCategories();
      const nextSelectedId = nextCategories[0]?.id ?? null;
      setSelectedCategoryId(nextSelectedId);
      await loadProducts(nextSelectedId);
    });
  };

  const readProductForm = (
    form: ProductFormState,
  ): { values: ProductFormValues } | { error: string } => {
    const name = form.name.trim();
    const price = Number(form.price);
    const category = Number(form.category);
    const description = form.description.trim();

    if (!name) {
      return { error: "نام محصول را وارد کنید" };
    }

    if (!Number.isFinite(price) || price < 0) {
      return { error: "قیمت محصول معتبر نیست" };
    }

    if (!Number.isInteger(category) || category <= 0) {
      return { error: "دسته‌بندی محصول را انتخاب کنید" };
    }

    return {
      values: {
        name,
        price,
        category,
        description,
        is_available: form.is_available,
        is_publishable: form.is_publishable,
      },
    };
  };

  const submitProduct = () => {
    if (dialog?.type !== "add-product" && dialog?.type !== "edit-product") {
      return;
    }

    const parsed = readProductForm(dialog.form);
    if ("error" in parsed) {
      showToast({ tone: "bad", message: parsed.error });
      return;
    }

    void runMutation(async () => {
      if (dialog.type === "add-product") {
        await apiPost<Product>("/products/", parsed.values);
      } else {
        await apiPatch<Product>(`/products/${dialog.product.id}/`, {
          name: parsed.values.name,
          price: parsed.values.price,
          category: parsed.values.category,
          is_available: parsed.values.is_available,
          is_publishable: parsed.values.is_publishable,
        });
      }

      await refreshProducts();
    });
  };

  const submitDeleteProduct = () => {
    if (dialog?.type !== "delete-product") {
      return;
    }

    void runMutation(async () => {
      await apiDelete<null>(`/products/${dialog.product.id}/`);
      await refreshProducts();
    });
  };

  const publishMenu = async () => {
    if (isPublishing) {
      return;
    }

    setIsPublishing(true);

    try {
      const response = await apiPost<PublishResponse>("/menu/publish/");
      if (response.success) {
        showToast({ tone: "good", message: "منو منتشر شد" });
      } else {
        showToast({
          tone: "bad",
          message: response.error || "انتشار منو ناموفق بود",
        });
      }
    } catch (caughtError) {
      const body = publishBodyFromError(caughtError);
      showToast({
        tone: "bad",
        message: body?.error || "انتشار منو ناموفق بود",
      });
    } finally {
      setIsPublishing(false);
    }
  };

  const closeDialog = () => {
    if (!isSubmitting) {
      setDialog(null);
    }
  };

  const updateProductForm = (form: ProductFormState) => {
    if (dialog?.type === "add-product" || dialog?.type === "edit-product") {
      setDialog({ ...dialog, form });
    }
  };

  return (
    <>
      <div className="flex min-h-full flex-col gap-6 pb-24">
        {toast && (
          <div
            className={[
              "fixed left-8 top-16 z-[60] max-w-md rounded-xl border px-4 py-3 text-base font-semibold shadow-xl shadow-black/30",
              toast.tone === "good"
                ? "border-good/30 bg-[#112418] text-good"
                : "border-bad/30 bg-[#2a1518] text-bad",
            ].join(" ")}
          >
            {toast.message}
          </div>
        )}

        <div className="grid min-h-[34rem] grid-cols-1 gap-6 xl:grid-cols-[19rem_minmax(0,1fr)]">
          <aside className="min-h-0 rounded-2xl border border-border bg-surface">
            <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
              <div>
                <h2 className="text-xl font-black text-text">دسته‌بندی‌ها</h2>
                <p className="mt-1 text-sm font-semibold text-muted">
                  {faNum(sortedCategories.length)} دسته
                </p>
              </div>
              <Button
                className="h-10 w-10 rounded-xl px-0 text-xl"
                aria-label="افزودن دسته‌بندی"
                onClick={() => setDialog({ type: "add-category", name: "" })}
              >
                +
              </Button>
            </div>

            {isLoading ? (
              <div className="p-5 text-base text-muted">در حال دریافت...</div>
            ) : sortedCategories.length === 0 ? (
              <div className="p-5 text-base leading-8 text-muted">
                هنوز دسته‌بندی ثبت نشده است.
              </div>
            ) : (
              <div className="divide-y divide-border">
                {sortedCategories.map((category, index) => {
                  const isSelected = category.id === selectedCategoryId;

                  return (
                    <div
                      key={category.id}
                      className={[
                        "grid grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-3 transition",
                        isSelected ? "bg-accent/10" : "hover:bg-surface-2",
                      ].join(" ")}
                    >
                      <button
                        type="button"
                        className="min-w-0 text-right focus:outline-none"
                        onClick={() => handleCategorySelect(category.id)}
                      >
                        <div
                          className={[
                            "truncate text-base font-black",
                            isSelected ? "text-accent" : "text-text",
                          ].join(" ")}
                        >
                          {category.name}
                        </div>
                        <div className="mt-1 text-xs font-semibold text-muted">
                          ترتیب {faNum(category.sort_order)}
                        </div>
                      </button>

                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          className="grid h-8 w-8 place-items-center rounded-lg border border-border bg-surface-2 text-sm font-black text-muted transition hover:bg-[var(--surface-3)] hover:text-text disabled:opacity-40"
                          aria-label={`انتقال ${category.name} به بالا`}
                          disabled={index === 0 || isSubmitting}
                          onClick={() => moveCategory(category, -1)}
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          className="grid h-8 w-8 place-items-center rounded-lg border border-border bg-surface-2 text-sm font-black text-muted transition hover:bg-[var(--surface-3)] hover:text-text disabled:opacity-40"
                          aria-label={`انتقال ${category.name} به پایین`}
                          disabled={index === sortedCategories.length - 1 || isSubmitting}
                          onClick={() => moveCategory(category, 1)}
                        >
                          ↓
                        </button>
                        <button
                          type="button"
                          className="grid h-8 w-8 place-items-center rounded-lg border border-border bg-surface-2 text-xs font-black text-muted transition hover:bg-[var(--surface-3)] hover:text-text"
                          aria-label={`تغییر نام ${category.name}`}
                          onClick={() =>
                            setDialog({
                              type: "rename-category",
                              category,
                              name: category.name,
                            })
                          }
                        >
                          ✎
                        </button>
                        <button
                          type="button"
                          className="grid h-8 w-8 place-items-center rounded-lg border border-bad/30 bg-bad/10 text-xs font-black text-bad transition hover:bg-bad/20"
                          aria-label={`حذف ${category.name}`}
                          onClick={() => setDialog({ type: "delete-category", category })}
                        >
                          ×
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </aside>

          <section className="min-w-0 rounded-2xl border border-border bg-surface">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-5 py-4">
              <div className="min-w-0">
                <h2 className="truncate text-2xl font-black text-text">
                  {selectedCategory?.name ?? "محصولات"}
                </h2>
                <p className="mt-1 text-sm font-semibold text-muted">
                  {selectedCategory
                    ? `${faNum(sortedProducts.length)} محصول در این دسته`
                    : "برای افزودن محصول ابتدا دسته‌بندی بسازید"}
                </p>
              </div>
              <Button
                disabled={selectedCategoryId === null}
                onClick={() =>
                  setDialog({
                    type: "add-product",
                    form: emptyProductForm(selectedCategoryId),
                  })
                }
              >
                افزودن محصول
              </Button>
            </div>

            {isLoading || isProductsLoading ? (
              <div className="p-8 text-lg text-muted">در حال دریافت محصولات...</div>
            ) : selectedCategoryId === null ? (
              <div className="p-8 text-lg leading-8 text-muted">
                هنوز دسته‌بندی فعالی برای نمایش محصولات وجود ندارد.
              </div>
            ) : sortedProducts.length === 0 ? (
              <div className="p-8 text-lg leading-8 text-muted">
                هنوز محصولی در این دسته ثبت نشده است.
              </div>
            ) : (
              <div className="grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-3 p-4">
                {sortedProducts.map((product) => (
                  <button
                    key={product.id}
                    type="button"
                    aria-label={`ویرایش ${product.name}`}
                    onClick={() =>
                      setDialog({
                        type: "edit-product",
                        product,
                        form: productFormFromProduct(product),
                      })
                    }
                    className={[
                      "flex flex-col rounded-xl border p-3 text-right transition hover:border-accent focus:border-accent focus:outline-none",
                      product.is_available
                        ? "border-border bg-surface-2"
                        : "border-border bg-surface-2 opacity-70",
                    ].join(" ")}
                  >
                    <div className="flex w-full items-start justify-between gap-2">
                      <h3 className="min-w-0 truncate text-base font-black text-text">
                        {product.name}
                      </h3>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        <Badge tone={product.is_available ? "good" : "default"}>
                          {product.is_available ? "موجود" : "ناموجود"}
                        </Badge>
                        {!product.is_publishable && (
                          <Badge tone="accent">پنهان از منو</Badge>
                        )}
                      </div>
                    </div>

                    <div className="mt-2 text-lg font-black text-accent">
                      {formatMoney(product.price)}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface-2/95 px-8 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-base font-black text-text">انتشار منو</div>
            <div className="mt-1 text-sm font-semibold text-muted">
              تغییرات محلی منو را برای کانال‌های بیرونی منتشر کنید.
            </div>
          </div>
          <Button onClick={() => void publishMenu()} disabled={isPublishing}>
            {isPublishing ? "در حال انتشار..." : "انتشار منو"}
          </Button>
        </div>
      </div>

      {(dialog?.type === "add-category" || dialog?.type === "rename-category") && (
        <Modal onClose={closeDialog}>
          <div className="mb-5">
            <h2 className="text-2xl font-black text-text">
              {dialog.type === "add-category" ? "افزودن دسته‌بندی" : "تغییر نام دسته‌بندی"}
            </h2>
          </div>
          <label className="block text-sm font-semibold text-muted" htmlFor="category-name">
            نام دسته‌بندی
          </label>
          <input
            id="category-name"
            className="mt-2 w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition focus:border-accent"
            autoFocus
            value={dialog.name}
            onChange={(event) => setDialog({ ...dialog, name: event.target.value })}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                submitCategory();
              }
            }}
          />
          <div className="mt-6 flex gap-3">
            <Button className="flex-1" variant="ghost" onClick={closeDialog}>
              انصراف
            </Button>
            <Button className="flex-1" onClick={submitCategory} disabled={isSubmitting}>
              ذخیره
            </Button>
          </div>
        </Modal>
      )}

      {dialog?.type === "delete-category" && (
        <Modal onClose={closeDialog}>
          <div className="mb-5">
            <h2 className="text-2xl font-black text-text">حذف دسته‌بندی</h2>
          </div>
          <p className="rounded-xl border border-warn/30 bg-warn/10 px-4 py-3 text-base font-semibold leading-8 text-warn">
            دسته‌بندی «{dialog.category.name}» حذف شود؟
          </p>
          <div className="mt-6 flex gap-3">
            <Button className="flex-1" variant="ghost" onClick={closeDialog}>
              انصراف
            </Button>
            <Button
              className="flex-1 bg-bad text-[#1b0a0a] hover:bg-bad/90"
              onClick={submitDeleteCategory}
              disabled={isSubmitting}
            >
              حذف دسته‌بندی
            </Button>
          </div>
        </Modal>
      )}

      {(dialog?.type === "add-product" || dialog?.type === "edit-product") && (
        <Modal onClose={closeDialog} widthClassName="max-w-2xl">
          <form
            onSubmit={(event: FormEvent<HTMLFormElement>) => {
              event.preventDefault();
              submitProduct();
            }}
          >
            <div className="mb-5">
              <h2 className="text-2xl font-black text-text">
                {dialog.type === "add-product" ? "افزودن محصول" : "ویرایش محصول"}
              </h2>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="block text-sm font-semibold text-muted" htmlFor="product-name">
                  نام محصول
                </label>
                <input
                  id="product-name"
                  className="mt-2 w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition focus:border-accent"
                  autoFocus
                  value={dialog.form.name}
                  onChange={(event) =>
                    updateProductForm({ ...dialog.form, name: event.target.value })
                  }
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-muted" htmlFor="product-price">
                  قیمت
                </label>
                <input
                  id="product-price"
                  className="mt-2 w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition focus:border-accent"
                  inputMode="numeric"
                  value={dialog.form.price}
                  onChange={(event) =>
                    updateProductForm({ ...dialog.form, price: event.target.value })
                  }
                />
              </div>

              <div>
                <label
                  className="block text-sm font-semibold text-muted"
                  htmlFor="product-category"
                >
                  دسته‌بندی
                </label>
                <select
                  id="product-category"
                  className="mt-2 w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition focus:border-accent"
                  value={dialog.form.category}
                  onChange={(event) =>
                    updateProductForm({ ...dialog.form, category: event.target.value })
                  }
                >
                  <option value="">انتخاب دسته‌بندی</option>
                  {sortedCategories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <span className="block text-sm font-semibold text-muted">وضعیت</span>
                <button
                  type="button"
                  aria-pressed={dialog.form.is_available}
                  onClick={() =>
                    updateProductForm({
                      ...dialog.form,
                      is_available: !dialog.form.is_available,
                    })
                  }
                  className={[
                    "mt-2 inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-base font-bold transition",
                    dialog.form.is_available
                      ? "border-good/30 bg-good/10 text-good"
                      : "border-border bg-[var(--surface-3)] text-muted",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "relative h-5 w-9 rounded-full transition",
                      dialog.form.is_available ? "bg-good/60" : "bg-border",
                    ].join(" ")}
                  >
                    <span
                      className={[
                        "absolute top-1 h-3 w-3 rounded-full bg-text transition",
                        dialog.form.is_available ? "right-5" : "right-1",
                      ].join(" ")}
                    />
                  </span>
                  {dialog.form.is_available ? "موجود" : "ناموجود"}
                </button>
              </div>

              <div>
                <span className="block text-sm font-semibold text-muted">
                  نمایش در منوی منتشرشده
                </span>
                <button
                  type="button"
                  aria-pressed={dialog.form.is_publishable}
                  onClick={() =>
                    updateProductForm({
                      ...dialog.form,
                      is_publishable: !dialog.form.is_publishable,
                    })
                  }
                  className={[
                    "mt-2 inline-flex min-h-11 items-center gap-2 rounded-xl border px-4 text-base font-bold transition",
                    dialog.form.is_publishable
                      ? "border-accent/30 bg-accent/10 text-accent"
                      : "border-border bg-[var(--surface-3)] text-muted",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "relative h-5 w-9 rounded-full transition",
                      dialog.form.is_publishable ? "bg-accent/60" : "bg-border",
                    ].join(" ")}
                  >
                    <span
                      className={[
                        "absolute top-1 h-3 w-3 rounded-full bg-text transition",
                        dialog.form.is_publishable ? "right-5" : "right-1",
                      ].join(" ")}
                    />
                  </span>
                  {dialog.form.is_publishable ? "در منو" : "پنهان"}
                </button>
              </div>

              {dialog.type === "add-product" && (
                <div className="md:col-span-2">
                  <label
                    className="block text-sm font-semibold text-muted"
                    htmlFor="product-description"
                  >
                    توضیحات
                  </label>
                  <textarea
                    id="product-description"
                    className="mt-2 min-h-28 w-full resize-none rounded-xl border border-border bg-surface-2 px-4 py-3 text-base font-semibold leading-8 text-text outline-none transition focus:border-accent"
                    value={dialog.form.description}
                    onChange={(event) =>
                      updateProductForm({
                        ...dialog.form,
                        description: event.target.value,
                      })
                    }
                  />
                </div>
              )}
            </div>

            <div className="mt-6 flex gap-3">
              <Button className="flex-1" variant="ghost" onClick={closeDialog}>
                انصراف
              </Button>
              {dialog.type === "edit-product" && (
                <Button
                  type="button"
                  className="flex-1 border-bad/30 bg-bad/10 text-bad hover:bg-bad/20"
                  variant="ghost"
                  disabled={isSubmitting}
                  onClick={() =>
                    setDialog({ type: "delete-product", product: dialog.product })
                  }
                >
                  حذف
                </Button>
              )}
              <Button className="flex-1" type="submit" disabled={isSubmitting}>
                ذخیره
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {dialog?.type === "delete-product" && (
        <Modal onClose={closeDialog}>
          <div className="mb-5">
            <h2 className="text-2xl font-black text-text">حذف محصول</h2>
          </div>
          <p className="rounded-xl border border-warn/30 bg-warn/10 px-4 py-3 text-base font-semibold leading-8 text-warn">
            محصول «{dialog.product.name}» حذف شود؟
          </p>
          <div className="mt-6 flex gap-3">
            <Button className="flex-1" variant="ghost" onClick={closeDialog}>
              انصراف
            </Button>
            <Button
              className="flex-1 bg-bad text-[#1b0a0a] hover:bg-bad/90"
              onClick={submitDeleteProduct}
              disabled={isSubmitting}
            >
              حذف محصول
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}
