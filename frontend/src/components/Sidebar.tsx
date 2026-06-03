export type Screen = "tables" | "menu" | "closing";

type NavItem = {
  id: Screen;
  label: string;
};

const navItems: NavItem[] = [
  { id: "tables", label: "میزها" },
  { id: "menu", label: "منو و محصولات" },
  { id: "closing", label: "بستن روز" },
];

type SidebarProps = {
  active: Screen;
  onChange: (screen: Screen) => void;
};

export function Sidebar({ active, onChange }: SidebarProps) {
  return (
    <aside className="flex w-72 flex-none flex-col border-l border-border bg-surface px-4 py-5">
      <div className="mb-6 flex items-center gap-3">
        <div className="grid h-12 w-12 place-items-center rounded-xl bg-accent text-xl font-black text-[#1b1206]">
          C
        </div>
        <div className="min-w-0">
          <div className="text-lg font-bold text-text">کافه CiXiS</div>
          <div className="text-sm text-muted">صندوق فروش</div>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-2" aria-label="ناوبری اصلی">
        {navItems.map((item) => {
          const isActive = item.id === active;

          return (
            <button
              key={item.id}
              type="button"
              className={[
                "w-full rounded-xl px-4 py-3 text-right transition",
                isActive
                  ? "bg-accent text-[#1b1206] shadow-lg shadow-black/20"
                  : "text-text hover:bg-surface-2",
              ].join(" ")}
              aria-current={isActive ? "page" : undefined}
              onClick={() => onChange(item.id)}
            >
              <span className="block text-base font-bold">{item.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
