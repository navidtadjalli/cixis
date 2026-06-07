import { faNum } from "../lib/format";
import type { Category, Product } from "../screens/OrderPanel";

export type Screen = "tables" | "tables-admin" | "menu" | "closing";

export const navItems: { id: Screen; label: string }[] = [
  { id: "tables", label: "سفارش گیری" },
  { id: "tables-admin", label: "مدیریت میزها" },
  { id: "menu", label: "منو و محصولات" },
  { id: "closing", label: "بستن روز" },
];

type SidebarProps = {
  categories: Category[];
  selectedCategoryId: number | null;
  onSelectCategory: (id: number) => void;
  products: Product[];
  isProductsLoading: boolean;
  onAddProduct: (product: Product) => void;
  // Only an open order can receive items; without one the picker is inert.
  canAddProduct: boolean;
  occupiedCount?: number;
  emptyCount?: number;
};

export function Sidebar({
  categories,
  selectedCategoryId,
  onSelectCategory,
  products,
  isProductsLoading,
  onAddProduct,
  canAddProduct,
  occupiedCount,
  emptyCount,
}: SidebarProps) {
  const sortedCategories = [...categories].sort(
    (a, b) => a.sort_order - b.sort_order || a.id - b.id,
  );

  const sortedProducts = [...products].sort(
    (a, b) => a.sort_order - b.sort_order || a.id - b.id,
  );

  return (
    <aside className="flex w-80 flex-none flex-col border-l border-border bg-surface px-3 py-5">
      <div className="mb-5 flex items-center gap-3">
        <div className="grid h-11 w-11 place-items-center rounded-xl bg-accent text-xl font-black text-[#1b1206]">
          Ç
        </div>
        <div className="min-w-0">
          <div className="text-base font-bold text-text">کافه خروج</div>
          <div className="text-xs text-muted">صندوق فروش</div>
        </div>
      </div>

      <div className="mb-2 text-xs font-bold text-muted">دسته‌بندی‌ها</div>
      <nav
        className="flex max-h-[35vh] flex-none flex-wrap gap-1.5 overflow-y-auto"
        aria-label="دسته‌بندی‌ها"
      >
        {sortedCategories.length === 0 ? (
          <div className="w-full rounded-xl border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
            دسته‌بندی ثبت نشده است.
          </div>
        ) : (
          sortedCategories.map((category) => {
            const isActive = category.id === selectedCategoryId;

            return (
              <button
                key={category.id}
                type="button"
                className={[
                  "rounded-xl border px-3 py-1.5 text-lg font-bold transition",
                  isActive
                    ? "border-accent bg-accent text-[#1b1206] shadow-lg shadow-black/20"
                    : "border-border bg-surface-2 text-text hover:bg-[var(--surface-3)]",
                ].join(" ")}
                aria-current={isActive ? "true" : undefined}
                onClick={() => onSelectCategory(category.id)}
              >
                {category.name}
              </button>
            );
          })
        )}
      </nav>

      <div className="mb-2 mt-5 text-xs font-bold text-muted">محصولات</div>
      <div className="flex min-h-0 flex-1 flex-wrap content-start gap-1.5 overflow-y-auto">
        {selectedCategoryId === null ? (
          <div className="w-full rounded-xl border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
            یک دسته‌بندی را انتخاب کنید.
          </div>
        ) : isProductsLoading ? (
          <div className="w-full rounded-xl border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
            در حال دریافت محصولات...
          </div>
        ) : sortedProducts.length === 0 ? (
          <div className="w-full rounded-xl border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
            محصولی برای این دسته‌بندی ثبت نشده است.
          </div>
        ) : (
          sortedProducts.map((product) => {
            const disabled = !canAddProduct || !product.is_available;

            return (
              <button
                key={product.id}
                type="button"
                className={[
                  "flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-base font-bold transition",
                  disabled
                    ? "cursor-not-allowed border-border bg-surface-2 text-muted opacity-50"
                    : "border-border bg-surface-2 text-text hover:border-accent/50 hover:bg-[var(--surface-3)]",
                ].join(" ")}
                disabled={disabled}
                onClick={() => onAddProduct(product)}
              >
                <span>{product.name}</span>
                {!product.is_available && (
                  <span className="flex-none text-[11px] font-black text-bad">
                    ناموجود
                  </span>
                )}
              </button>
            );
          })
        )}
      </div>

      {(occupiedCount !== undefined || emptyCount !== undefined) && (
        <div className="mt-4 grid grid-cols-2 gap-2 border-t border-border pt-4">
          <div className="rounded-xl border border-border bg-surface-2 px-2 py-2 text-center">
            <div className="text-xs font-semibold text-muted">در حال سرویس</div>
            <div className="mt-1 text-lg font-black text-text">
              {faNum(occupiedCount ?? 0)}
            </div>
          </div>
          <div className="rounded-xl border border-border bg-surface-2 px-2 py-2 text-center">
            <div className="text-xs font-semibold text-muted">خالی</div>
            <div className="mt-1 text-lg font-black text-text">
              {faNum(emptyCount ?? 0)}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
