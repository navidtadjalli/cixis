import { useState } from "react";
import { Sidebar, type Screen } from "./components/Sidebar";
import { Titlebar } from "./components/Titlebar";
import { Badge } from "./components/ui";
import { TablesScreen } from "./screens/TablesScreen";

const screenTitles: Record<Screen, string> = {
  tables: "میزها",
  menu: "منو و محصولات",
  closing: "بستن روز",
};

export default function App() {
  const [screen, setScreen] = useState<Screen>("tables");

  const handleOpenOrder = (orderId: number, tableId: number) => {
    console.log("open order placeholder", { orderId, tableId });
  };

  const handleEventMode = () => {
    console.log("event mode placeholder");
  };

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-bg text-text" dir="rtl">
      <Titlebar />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Sidebar active={screen} onChange={setScreen} />

        <main className="min-w-0 flex-1 overflow-x-hidden bg-bg">
          <div className="flex min-h-full flex-col">
            <header className="flex flex-none items-center justify-between border-b border-border bg-surface-2 px-8 py-5">
              <div>
                <h1 className="text-2xl font-extrabold text-text">
                  {screenTitles[screen]}
                </h1>
                <p className="mt-1 text-base text-muted">
                  پوسته اصلی صندوق فروش کافه
                </p>
              </div>
              <Badge tone="good">ذخیره‌شده روی این رایانه</Badge>
            </header>

            <section className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-8">
              {screen === "tables" ? (
                <TablesScreen
                  onOpenOrder={handleOpenOrder}
                  onEventMode={handleEventMode}
                />
              ) : (
                <div className="rounded-2xl border border-border bg-surface p-8">
                  <h2 className="text-3xl font-black text-text">
                    {screenTitles[screen]}
                  </h2>
                  <p className="mt-3 max-w-2xl text-lg leading-8 text-muted">
                    این بخش در تسک‌های بعدی با جریان کامل کاری تکمیل می‌شود.
                  </p>
                </div>
              )}
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
