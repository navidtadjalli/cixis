import { FormEvent, useState } from "react";
import { ApiError } from "../lib/api";
import { useRevenue } from "../context/RevenueContext";
import { Button } from "./ui";

// Password gate shown before the Day Closing screen. Prices/orders are visible
// everywhere else; only بستن روز requires the password.
export function DayClosingGate() {
  const { unlock } = useRevenue();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await unlock(password);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("رمز عبور نادرست است");
      } else {
        setError("خطا در ورود");
      }
      setSubmitting(false);
    }
  };

  return (
    <div className="grid min-h-[60vh] place-items-center">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 text-center"
      >
        <h2 className="text-2xl font-black text-text">بستن روز</h2>
        <p className="mt-2 text-sm text-muted">
          برای مشاهده و بستن روز، رمز عبور را وارد کنید.
        </p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="رمز عبور"
          className="mt-6 h-12 w-full rounded-xl border border-border bg-surface-2 px-4 text-center text-lg text-text outline-none focus:border-accent"
        />
        {error && <div className="mt-3 text-sm font-semibold text-bad">{error}</div>}
        <Button type="submit" className="mt-5 w-full" disabled={submitting || !password}>
          ورود
        </Button>
      </form>
    </div>
  );
}
