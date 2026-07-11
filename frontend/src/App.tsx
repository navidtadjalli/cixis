import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Sidebar, navItems, type Screen } from "./components/Sidebar";
import { Titlebar } from "./components/Titlebar";
import { EventScreen } from "./screens/EventScreen";
import { DayClosingScreen } from "./screens/DayClosingScreen";
import { MenuScreen } from "./screens/MenuScreen";
import { OrderPanel, type Category, type Product } from "./screens/OrderPanel";
import { SettingsScreen } from "./screens/SettingsScreen";
import { TablesScreen, type Table } from "./screens/TablesScreen";
import { TablesAdminScreen } from "./screens/TablesAdminScreen";
import { apiGet } from "./lib/api";
import { useRevenue } from "./context/RevenueContext";
import { DayClosingGate } from "./components/DayClosingGate";
import { AnimatedBackground } from "./components/AnimatedBackground";

export default function App() {
  const { lock, unlocked } = useRevenue();
  const [screen, setScreen] = useState<Screen>("tables");
  const [openOrderId, setOpenOrderId] = useState<number | null>(null);
  const [eventMode, setEventMode] = useState(false);

  const [tables, setTables] = useState<Table[]>([]);
  const [tablesLoading, setTablesLoading] = useState(true);
  const [tablesError, setTablesError] = useState<string | null>(null);

  // Menu (categories + products) lives at the top level so the sidebar can show
  // categories everywhere and the open order panel renders the picked items.
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);

  // The open OrderPanel registers its addProduct handler here so the sidebar
  // product picker can add items to the active order.
  const addProductRef = useRef<((product: Product) => void) | null>(null);
  const handleSidebarAddProduct = useCallback((product: Product) => {
    addProductRef.current?.(product);
  }, []);

  const refreshTables = useCallback(async () => {
    setTables(await apiGet<Table[]>("/tables/"));
  }, []);

  useEffect(() => {
    let ignore = false;

    const load = async () => {
      try {
        const tableList = await apiGet<Table[]>("/tables/");
        if (!ignore) {
          setTables(tableList);
          setTablesError(null);
        }
      } catch {
        if (!ignore) {
          setTablesError("دریافت اطلاعات میزها ناموفق بود");
        }
      } finally {
        if (!ignore) {
          setTablesLoading(false);
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

  useEffect(() => {
    let ignore = false;

    void (async () => {
      try {
        const list = await apiGet<Category[]>("/categories/");
        if (!ignore) {
          setCategories(list);
        }
      } catch {
        // Sidebar simply shows "no categories" if this fails.
      }
    })();

    return () => {
      ignore = true;
    };
  }, []);

  const handleSelectCategory = useCallback(
    (categoryId: number) => {
      if (categoryId === selectedCategoryId) {
        return;
      }
      setSelectedCategoryId(categoryId);
      setProductsLoading(true);
      void apiGet<Product[]>(`/products/?category=${categoryId}`)
        .then((list) => setProducts(list))
        .catch(() => setProducts([]))
        .finally(() => setProductsLoading(false));
    },
    [selectedCategoryId],
  );

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

  const handleScreenChange = (nextScreen: Screen) => {
    lock();
    setScreen(nextScreen);
    setOpenOrderId(null);
    setEventMode(false);
  };

  const handleOpenOrder = (orderId: number) => {
    setOpenOrderId(orderId);
  };

  const handleEventMode = () => {
    setEventMode(true);
  };

  const handleBackToTables = () => {
    setEventMode(false);
  };

  return (
    <div className="relative flex h-full min-h-0 flex-col overflow-hidden text-text" dir="rtl">
      <AnimatedBackground camelCount={counts.occupied} />
      <div className="relative z-10 flex min-h-0 flex-1 flex-col overflow-hidden">
      <Titlebar />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Sidebar
          categories={categories}
          selectedCategoryId={selectedCategoryId}
          onSelectCategory={handleSelectCategory}
          products={products}
          isProductsLoading={productsLoading}
          onAddProduct={handleSidebarAddProduct}
          canAddProduct={openOrderId !== null}
          occupiedCount={counts.occupied}
          emptyCount={counts.empty}
        />

        <main className="min-w-0 flex-1 overflow-x-hidden">
          <div className="flex min-h-full flex-col">
            <header className="flex flex-none items-center gap-2 border-b border-border bg-surface-2 px-6 py-2">
              <nav className="flex flex-wrap gap-2" aria-label="ناوبری اصلی">
                {navItems.map((item) => {
                  const isActive = item.id === screen;

                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={[
                        "rounded-xl px-4 py-2 text-sm font-bold transition",
                        isActive
                          ? "bg-accent text-[#1b1206] shadow-lg shadow-black/20"
                          : "text-text hover:bg-surface",
                      ].join(" ")}
                      aria-current={isActive ? "page" : undefined}
                      onClick={() => handleScreenChange(item.id)}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </nav>
            </header>

            <section className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-8">
              {openOrderId !== null ? (
                <OrderPanel
                  orderId={openOrderId}
                  registerAddProduct={(handler) => {
                    addProductRef.current = handler;
                  }}
                  onClose={() => {
                    setOpenOrderId(null);
                    void refreshTables();
                  }}
                />
              ) : screen === "tables" && eventMode ? (
                <EventScreen
                  onOpenOrder={handleOpenOrder}
                  onBack={handleBackToTables}
                />
              ) : screen === "tables" ? (
                <TablesScreen
                  tables={tables}
                  isLoading={tablesLoading}
                  loadError={tablesError}
                  refresh={refreshTables}
                  onOpenOrder={handleOpenOrder}
                  onEventMode={handleEventMode}
                />
              ) : screen === "tables-admin" ? (
                <TablesAdminScreen
                  tables={tables}
                  isLoading={tablesLoading}
                  refresh={refreshTables}
                />
              ) : screen === "menu" ? (
                <MenuScreen />
              ) : screen === "closing" ? (
                unlocked ? <DayClosingScreen /> : <DayClosingGate />
              ) : screen === "settings" ? (
                <SettingsScreen />
              ) : null}
            </section>
          </div>
        </main>
      </div>
      </div>
    </div>
  );
}
