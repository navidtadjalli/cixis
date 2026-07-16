import { FormEvent, useState } from "react";
import { ApiError, apiPost } from "../lib/api";
import { enNum, faNum } from "../lib/format";
import { brand } from "../brand.generated";
import { Button, Modal } from "../components/ui";

type BulkResult = { created: number; skipped: number };
type WipeTablesResult = { deleted_tables: number; deleted_orders: number };
type WipeOrdersResult = { deleted_orders: number };
type WipeMenuResult = { deleted_products: number; deleted_categories: number };
type LoadMenuResult = { categories_created: number; products_created: number };

type Confirmable = "tables" | "orders" | "menu";

const confirmCopy: Record<Confirmable, { title: string; body: string }> = {
  tables: {
    title: "پاک کردن همه میزها؟",
    body: "همه میزها و سفارش‌های تسویه‌نشده روی آن‌ها برای همیشه حذف می‌شوند. این کار قابل بازگشت نیست.",
  },
  orders: {
    title: "پاک کردن همه سفارش‌ها و کدها؟",
    body: "همه سفارش‌ها، اقلام و پرداخت‌ها برای همیشه حذف می‌شوند و صندوق صفر می‌شود. گزارش روزهای بسته‌شده باقی می‌ماند. این کار قابل بازگشت نیست.",
  },
  menu: {
    title: "پاک کردن همه دسته‌بندی‌ها و محصولات؟",
    body: "همه دسته‌بندی‌ها و محصولات برای همیشه حذف می‌شوند. این کار قابل بازگشت نیست.",
  },
};

type SetupScreenProps = {
  // Tables and categories live in App; a wipe or a bulk create must be
  // reflected there or the sidebar keeps offering rows that no longer exist.
  onDataChanged: () => void;
};

function detail(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "رمز عبور نادرست است";
    }
    const body = error.body as { detail?: string } | null;
    if (body?.detail) {
      return body.detail;
    }
  }
  return fallback;
}

const inputClass =
  "min-h-12 w-full rounded-xl border border-border bg-surface-2 px-4 text-lg font-semibold text-text outline-none transition placeholder:text-muted focus:border-accent";

function Card({
  title,
  hint,
  children,
}: {
  title: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-5">
      <h3 className="text-lg font-black text-text">{title}</h3>
      <p className="mt-1.5 text-sm leading-6 text-muted">{hint}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function SetupScreen({ onDataChanged }: SetupScreenProps) {
  // Held after unlock: the destructive routes each re-check it server-side, so
  // the gate below is a convenience, not the security boundary.
  const [password, setPassword] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [gateError, setGateError] = useState<string | null>(null);
  const [gateBusy, setGateBusy] = useState(false);

  const [tableCount, setTableCount] = useState("");
  const [prefix, setPrefix] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<Confirmable | null>(null);

  const unlock = async (event: FormEvent) => {
    event.preventDefault();
    setGateBusy(true);
    setGateError(null);
    try {
      await apiPost("/revenue/unlock/", { password });
      setUnlocked(true);
    } catch (caught) {
      setGateError(detail(caught, "خطا در ورود"));
    } finally {
      setGateBusy(false);
    }
  };

  const run = async <T,>(
    key: string,
    path: string,
    body: Record<string, unknown>,
    describe: (result: T) => string,
  ) => {
    setBusy(key);
    setError(null);
    setMessage(null);
    try {
      const result = await apiPost<T>(path, { password, ...body });
      setMessage(describe(result));
      onDataChanged();
    } catch (caught) {
      setError(detail(caught, "عملیات ناموفق بود"));
    } finally {
      setBusy(null);
    }
  };

  const wipeActions: Record<Confirmable, () => void> = {
    tables: () =>
      void run<WipeTablesResult>(
        "wipe-tables",
        "/setup/tables/wipe/",
        {},
        (result) =>
          `${faNum(result.deleted_tables)} میز حذف شد` +
          (result.deleted_orders
            ? ` — ${faNum(result.deleted_orders)} سفارش تسویه‌نشده هم حذف شد.`
            : "."),
      ),
    orders: () =>
      void run<WipeOrdersResult>(
        "wipe-orders",
        "/setup/orders/wipe/",
        {},
        (result) => `${faNum(result.deleted_orders)} سفارش و کد حذف شد.`,
      ),
    menu: () =>
      void run<WipeMenuResult>(
        "wipe-menu",
        "/setup/menu/wipe/",
        {},
        (result) =>
          `${faNum(result.deleted_categories)} دسته‌بندی و ${faNum(
            result.deleted_products,
          )} محصول حذف شد.`,
      ),
  };

  if (!unlocked) {
    return (
      <div className="grid min-h-[60vh] place-items-center">
        <form
          onSubmit={unlock}
          className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 text-center"
        >
          <h2 className="text-2xl font-black text-text">راه‌اندازی</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            برای ساخت یا پاک کردن میزها و منو، رمز عبور بستن روز را وارد کنید.
          </p>
          <input
            type="password"
            autoFocus
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="رمز عبور"
            className="mt-6 h-12 w-full rounded-xl border border-border bg-surface-2 px-4 text-center text-lg text-text outline-none focus:border-accent"
          />
          {gateError && (
            <div className="mt-3 text-sm font-semibold text-bad">{gateError}</div>
          )}
          <Button
            type="submit"
            className="mt-5 w-full"
            disabled={gateBusy || !password}
          >
            {gateBusy ? "در حال بررسی..." : "ورود"}
          </Button>
        </form>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h2 className="text-3xl font-black text-text">راه‌اندازی</h2>
        <p className="mt-2 text-base text-muted">
          ساخت گروهی میز و کد، و پاک کردن اطلاعات برای شروع از نو.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-bad/30 bg-[#2a1518] px-4 py-3 text-base font-semibold text-bad">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-xl border border-good/30 bg-good/10 px-4 py-3 text-base font-semibold text-good">
          {message}
        </div>
      )}

      <Card
        title="ساخت میز"
        hint="میزها با نام «میز ۱» تا «میز N» ساخته می‌شوند. نام‌های تکراری دوباره ساخته نمی‌شوند."
      >
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            className={inputClass}
            inputMode="numeric"
            value={tableCount}
            onChange={(event) => setTableCount(event.target.value)}
            placeholder="تعداد میز"
            aria-label="تعداد میز"
            autoComplete="off"
          />
          <Button
            className="min-h-12 whitespace-nowrap px-6"
            disabled={busy !== null || !tableCount.trim()}
            onClick={() =>
              void run<BulkResult>(
                "tables",
                "/setup/tables/bulk/",
                { count: enNum(tableCount.trim()) },
                (result) =>
                  `${faNum(result.created)} میز ساخته شد` +
                  (result.skipped
                    ? ` — ${faNum(result.skipped)} مورد از قبل وجود داشت.`
                    : "."),
              )
            }
          >
            {busy === "tables" ? "در حال ساخت..." : "ساخت میزها"}
          </Button>
        </div>
      </Card>

      <Card
        title="ساخت کد"
        hint={`برای هر شماره از شروع تا پایان (هر دو شامل) یک کد ساخته می‌شود؛ مثلا «الف» از ۱ تا ۳ یعنی الف۱، الف۲ و الف۳. کدها در فهرست «${brand.events.title}» می‌مانند و با بازگشت از سفارش پاک نمی‌شوند.`}
      >
        <div className="grid gap-3 sm:grid-cols-[1.4fr_1fr_1fr_auto]">
          <input
            className={inputClass}
            value={prefix}
            onChange={(event) => setPrefix(event.target.value)}
            placeholder="پیشوند"
            aria-label="پیشوند"
            autoComplete="off"
          />
          <input
            className={inputClass}
            inputMode="numeric"
            value={start}
            onChange={(event) => setStart(event.target.value)}
            placeholder="از شماره"
            aria-label="از شماره"
            autoComplete="off"
          />
          <input
            className={inputClass}
            inputMode="numeric"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
            placeholder="تا شماره"
            aria-label="تا شماره"
            autoComplete="off"
          />
          <Button
            className="min-h-12 whitespace-nowrap px-6"
            disabled={busy !== null || !start.trim() || !end.trim()}
            onClick={() =>
              void run<BulkResult>(
                "codes",
                "/setup/event-codes/bulk/",
                {
                  prefix: prefix.trim(),
                  start: enNum(start.trim()),
                  end: enNum(end.trim()),
                },
                (result) =>
                  `${faNum(result.created)} کد ساخته شد` +
                  (result.skipped
                    ? ` — ${faNum(result.skipped)} مورد از قبل فعال بود.`
                    : "."),
              )
            }
          >
            {busy === "codes" ? "در حال ساخت..." : "ساخت کدها"}
          </Button>
        </div>
      </Card>

      <Card
        title="بارگذاری منوی مَجاز"
        hint="دسته‌بندی‌ها و محصولات منوی مَجاز اضافه می‌شوند. مواردی که از قبل هست دوباره ساخته نمی‌شود و قیمت‌های ویرایش‌شده دست‌نخورده می‌مانند."
      >
        <Button
          className="min-h-12 px-6"
          disabled={busy !== null}
          onClick={() =>
            void run<LoadMenuResult>(
              "load-menu",
              "/setup/menu/load/",
              {},
              (result) =>
                `${faNum(result.categories_created)} دسته‌بندی و ${faNum(
                  result.products_created,
                )} محصول اضافه شد.`,
            )
          }
        >
          {busy === "load-menu" ? "در حال بارگذاری..." : "بارگذاری منو"}
        </Button>
      </Card>

      <Card
        title="پاک کردن میزها"
        hint="همه میزها حذف می‌شوند، به‌همراه سفارش‌های تسویه‌نشده‌ای که روی آن‌ها باز است. منو و محصولات دست‌نخورده می‌مانند."
      >
        <Button
          variant="ghost"
          className="min-h-12 border-bad/40 px-6 text-bad hover:bg-bad/10"
          disabled={busy !== null}
          onClick={() => setConfirming("tables")}
        >
          پاک کردن همه میزها
        </Button>
      </Card>

      <Card
        title="پاک کردن سفارش‌ها و کدها"
        hint={`همه سفارش‌های میز و ${brand.events.title} با اقلام و پرداخت‌هایشان حذف می‌شوند و صندوق صفر می‌شود. میزها و منو دست‌نخورده می‌مانند.`}
      >
        <Button
          variant="ghost"
          className="min-h-12 border-bad/40 px-6 text-bad hover:bg-bad/10"
          disabled={busy !== null}
          onClick={() => setConfirming("orders")}
        >
          پاک کردن همه سفارش‌ها و کدها
        </Button>
      </Card>

      <Card
        title="پاک کردن منو"
        hint="همه دسته‌بندی‌ها و محصولات حذف می‌شوند. سفارش‌های گذشته و گزارش‌ها دست‌نخورده می‌مانند. میزها دست‌نخورده می‌مانند."
      >
        <Button
          variant="ghost"
          className="min-h-12 border-bad/40 px-6 text-bad hover:bg-bad/10"
          disabled={busy !== null}
          onClick={() => setConfirming("menu")}
        >
          پاک کردن دسته‌بندی‌ها و محصولات
        </Button>
      </Card>

      {confirming && (
        <Modal onClose={() => setConfirming(null)} widthClassName="max-w-md">
          <h3 className="text-xl font-black text-text">
            {confirmCopy[confirming].title}
          </h3>
          <p className="mt-3 text-sm leading-7 text-muted">
            {confirmCopy[confirming].body}
          </p>
          <div className="mt-6 flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setConfirming(null)}>
              انصراف
            </Button>
            <Button
              className="bg-bad text-white hover:bg-bad/90"
              disabled={busy !== null}
              onClick={() => {
                const target = confirming;
                setConfirming(null);
                wipeActions[target]();
              }}
            >
              بله، پاک کن
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
