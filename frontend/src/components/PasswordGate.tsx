import { FormEvent, ReactNode, useCallback, useState } from "react";
import { ApiError, apiPost } from "../lib/api";
import { Button } from "./ui";

export type UnlockResponse = {
  token: string;
  expires_at: string;
  // Manager unlock only: true while the default password is still in use.
  must_change?: boolean;
};

/**
 * Per-screen unlock state against a given endpoint. Unlike RevenueContext (which
 * is shared app-wide for بستن روز), each attendance tab tracks its own unlock so
 * the supervisor tab and the manager-only report gate independently.
 */
export function useGate(unlockPath: string) {
  const [unlocked, setUnlocked] = useState(false);
  const [response, setResponse] = useState<UnlockResponse | null>(null);

  const unlock = useCallback(
    async (password: string) => {
      const res = await apiPost<UnlockResponse>(unlockPath, { password });
      setResponse(res);
      setUnlocked(true);
      return res;
    },
    [unlockPath],
  );

  const lock = useCallback(() => {
    setUnlocked(false);
    setResponse(null);
  }, []);

  return { unlocked, response, setResponse, unlock, lock };
}

// Shared reveal-prompt UI. Maps a 401 to the standard wrong-password message.
export function PasswordGate({
  title,
  prompt,
  onSubmit,
  footer,
}: {
  title: string;
  prompt: string;
  onSubmit: (password: string) => Promise<unknown>;
  footer?: ReactNode;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(password);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "رمز عبور نادرست است"
          : "خطا در ورود",
      );
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-[60vh] place-items-center">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 text-center"
      >
        <h2 className="text-2xl font-black text-text">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-muted">{prompt}</p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="رمز عبور"
          className="mt-6 h-12 w-full rounded-xl border border-border bg-surface-2 px-4 text-center text-lg text-text outline-none focus:border-accent"
        />
        {error && <div className="mt-3 text-sm font-semibold text-bad">{error}</div>}
        <Button type="submit" className="mt-5 w-full" disabled={busy || !password}>
          {busy ? "در حال بررسی..." : "ورود"}
        </Button>
        {footer}
      </form>
    </div>
  );
}

/**
 * Change-password form for a given endpoint (revenue or manager). Accepts the
 * master code as the current password, so a forgotten password is never a
 * lockout. Used both voluntarily and as the manager's forced first-use change.
 */
export function ChangePasswordForm({
  changePath,
  title = "تغییر رمز عبور",
  intro,
  onDone,
  onCancel,
}: {
  changePath: string;
  title?: string;
  intro?: string;
  onDone: () => void;
  onCancel?: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
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
      await apiPost(changePath, {
        current_password: current,
        new_password: next,
      });
      onDone();
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
        <h2 className="text-2xl font-black text-text">{title}</h2>
        {intro && <p className="mt-2 text-sm leading-6 text-muted">{intro}</p>}
        <input
          type="password"
          autoFocus
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          placeholder="رمز عبور فعلی"
          className="mt-6 h-12 w-full rounded-xl border border-border bg-surface-2 px-4 text-center text-lg text-text outline-none focus:border-accent"
        />
        <p className="mt-2 text-xs text-muted">
          رمز فعلی را فراموش کرده‌اید؟ کد اصلی را به‌جای آن وارد کنید.
        </p>
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
        {error && <div className="mt-3 text-sm font-semibold text-bad">{error}</div>}
        <Button
          type="submit"
          className="mt-5 w-full"
          disabled={submitting || !current || !next || !confirm}
        >
          ذخیره
        </Button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="mt-4 text-sm text-muted underline-offset-4 hover:text-text hover:underline"
          >
            انصراف
          </button>
        )}
      </form>
    </div>
  );
}
