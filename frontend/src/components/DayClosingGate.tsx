import { FormEvent, useState } from "react";
import { ApiError } from "../lib/api";
import { useRevenue } from "../context/RevenueContext";
import { Button } from "./ui";

// Password gate shown before the Day Closing screen. Prices/orders are visible
// everywhere else; only بستن روز requires the password.
export function DayClosingGate() {
  const { unlock, changePassword } = useRevenue();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [changing, setChanging] = useState(false);

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

  if (changing) {
    return (
      <ChangePasswordForm
        changePassword={changePassword}
        onDone={() => setChanging(false)}
      />
    );
  }

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
        <button
          type="button"
          onClick={() => setChanging(true)}
          className="mt-4 text-sm text-muted underline-offset-4 hover:text-text hover:underline"
        >
          تغییر رمز عبور
        </button>
      </form>
    </div>
  );
}

function ChangePasswordForm({
  changePassword,
  onDone,
}: {
  changePassword: (current: string, next: string) => Promise<void>;
  onDone: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (next !== confirm) {
      setError("رمز عبور جدید با تکرار آن یکسان نیست");
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(current, next);
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("رمز عبور فعلی نادرست است");
      } else if (err instanceof ApiError && err.status === 400) {
        setError("رمز عبور جدید باید حداقل ۴ نویسه باشد");
      } else {
        setError("خطا در تغییر رمز عبور");
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
        <h2 className="text-2xl font-black text-text">تغییر رمز عبور</h2>
        {done ? (
          <>
            <p className="mt-4 text-sm font-semibold text-good">رمز عبور تغییر کرد.</p>
            <Button type="button" className="mt-6 w-full" onClick={onDone}>
              بازگشت
            </Button>
          </>
        ) : (
          <>
            <input
              type="password"
              autoFocus
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              placeholder="رمز عبور فعلی"
              className="mt-6 h-12 w-full rounded-xl border border-border bg-surface-2 px-4 text-center text-lg text-text outline-none focus:border-accent"
            />
            <input
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              placeholder="رمز عبور جدید"
              className="mt-3 h-12 w-full rounded-xl border border-border bg-surface-2 px-4 text-center text-lg text-text outline-none focus:border-accent"
            />
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="تکرار رمز عبور جدید"
              className="mt-3 h-12 w-full rounded-xl border border-border bg-surface-2 px-4 text-center text-lg text-text outline-none focus:border-accent"
            />
            {error && (
              <div className="mt-3 text-sm font-semibold text-bad">{error}</div>
            )}
            <Button
              type="submit"
              className="mt-5 w-full"
              disabled={submitting || !current || !next || !confirm}
            >
              ذخیره
            </Button>
            <button
              type="button"
              onClick={onDone}
              className="mt-4 text-sm text-muted underline-offset-4 hover:text-text hover:underline"
            >
              انصراف
            </button>
          </>
        )}
      </form>
    </div>
  );
}
