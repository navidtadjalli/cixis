import { faNum } from "../lib/format";
import type { Category } from "../screens/OrderPanel";

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
  occupiedCount?: number;
  emptyCount?: number;
};

export function Sidebar({
  categories,
  selectedCategoryId,
  onSelectCategory,
  occupiedCount,
  emptyCount,
}: SidebarProps) {
  const sortedCategories = [...categories].sort(
    (a, b) => a.sort_order - b.sort_order || a.id - b.id,
  );

  return (
    <aside className="flex w-60 flex-none flex-col border-l border-border bg-surface px-3 py-5">
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
        className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto"
        aria-label="دسته‌بندی‌ها"
      >
        {sortedCategories.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
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
                  "w-full rounded-xl px-3 py-2.5 text-right text-sm font-bold transition",
                  isActive
                    ? "bg-accent text-[#1b1206] shadow-lg shadow-black/20"
                    : "text-text hover:bg-surface-2",
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
