import { useEffect, useState } from "react";
import { apiGet, apiPatch } from "../lib/api";
import { enNum, faNum } from "../lib/format";
import { Button } from "./ui";

// Designates which menu items staff get free each month: one "coffee" category
// (default 10 units) and one tagged product — the peanut-butter shake (default
// 1). The monthly report reads these quotas. CiXiS only.

type Category = { id: number; name: string; staff_free_monthly_quota: number };
type Product = { id: number; name: string; staff_free_monthly_quota: number };

const selectClass =
  "min-h-12 w-full rounded-xl border border-border bg-surface-2 px-4 text-lg font-semibold text-text outline-none transition focus:border-accent";
const numClass =
  "min-h-12 w-28 rounded-xl border border-border bg-surface-2 px-4 text-center text-lg font-semibold text-text outline-none transition focus:border-accent";

export function FreeAllowanceConfig() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [coffeeCat, setCoffeeCat] = useState("");
  const [coffeeQuota, setCoffeeQuota] = useState("10");
  const [shakeProduct, setShakeProduct] = useState("");
  const [shakeQuota, setShakeQuota] = useState("1");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    const [cats, prods] = await Promise.all([
      apiGet<Category[]>("/categories/"),
      apiGet<Product[]>("/products/"),
    ]);
    setCategories(cats);
    setProducts(prods);
    const coffee = cats.find((c) => c.staff_free_monthly_quota > 0);
    if (coffee) {
      setCoffeeCat(String(coffee.id));
      setCoffeeQuota(String(coffee.staff_free_monthly_quota));
    }
    const shake = prods.find((p) => p.staff_free_monthly_quota > 0);
    if (shake) {
      setShakeProduct(String(shake.id));
      setShakeQuota(String(shake.staff_free_monthly_quota));
    }
  };

  useEffect(() => {
    void load().catch(() => setError("دریافت دسته‌بندی‌ها و محصولات ناموفق بود"));
  }, []);

  const save = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const catId = Number(coffeeCat);
      const cQuota = Number(enNum(coffeeQuota)) || 0;
      // Only one category carries the coffee quota — clear any stragglers first.
      for (const c of categories) {
        if (c.id !== catId && c.staff_free_monthly_quota > 0) {
          await apiPatch(`/categories/${c.id}/`, { staff_free_monthly_quota: 0 });
        }
      }
      if (catId) {
        await apiPatch(`/categories/${catId}/`, {
          staff_free_monthly_quota: cQuota,
        });
      }

      const prodId = Number(shakeProduct);
      const sQuota = Number(enNum(shakeQuota)) || 0;
      for (const p of products) {
        if (p.id !== prodId && p.staff_free_monthly_quota > 0) {
          await apiPatch(`/products/${p.id}/`, { staff_free_monthly_quota: 0 });
        }
      }
      if (prodId) {
        await apiPatch(`/products/${prodId}/`, { staff_free_monthly_quota: sQuota });
      }

      setMessage("سهمیه رایگان ذخیره شد.");
      await load();
    } catch {
      setError("ذخیره سهمیه رایگان ناموفق بود");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-2xl border border-border bg-surface p-5">
      <h3 className="text-lg font-black text-text">سهمیه رایگان پرسنل</h3>
      <p className="mt-1.5 text-sm leading-6 text-muted">
        دسته‌بندی «قهوه» و محصول «شیک بادام‌زمینی» را انتخاب کنید؛ هر پرسنل ماهانه
        تا این تعداد را رایگان مصرف می‌کند و از حساب ماهش کم می‌شود.
      </p>

      {error && (
        <div className="mt-4 rounded-xl border border-bad/30 bg-[#2a1518] px-4 py-3 text-sm font-semibold text-bad">
          {error}
        </div>
      )}
      {message && (
        <div className="mt-4 rounded-xl border border-good/30 bg-good/10 px-4 py-3 text-sm font-semibold text-good">
          {message}
        </div>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-bold text-text">دسته‌بندی قهوه</span>
          <div className="mt-1.5 flex gap-2">
            <select
              className={selectClass}
              value={coffeeCat}
              onChange={(e) => setCoffeeCat(e.target.value)}
            >
              <option value="">— بدون سهمیه —</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <input
              className={numClass}
              inputMode="numeric"
              value={coffeeQuota}
              onChange={(e) => setCoffeeQuota(e.target.value)}
              aria-label="سهمیه قهوه"
            />
          </div>
        </label>

        <label className="block">
          <span className="text-sm font-bold text-text">محصول شیک بادام‌زمینی</span>
          <div className="mt-1.5 flex gap-2">
            <select
              className={selectClass}
              value={shakeProduct}
              onChange={(e) => setShakeProduct(e.target.value)}
            >
              <option value="">— بدون سهمیه —</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <input
              className={numClass}
              inputMode="numeric"
              value={shakeQuota}
              onChange={(e) => setShakeQuota(e.target.value)}
              aria-label="سهمیه شیک"
            />
          </div>
        </label>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <Button className="min-h-12 px-6" disabled={busy} onClick={() => void save()}>
          {busy ? "در حال ذخیره..." : "ذخیره سهمیه"}
        </Button>
        <span className="text-xs text-muted">
          سهمیهٔ فعلی قهوه: {faNum(coffeeQuota || "۰")} — شیک: {faNum(shakeQuota || "۰")}
        </span>
      </div>
    </section>
  );
}
