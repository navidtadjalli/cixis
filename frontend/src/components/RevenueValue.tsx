import { useState, type FormEvent, type MouseEvent } from "react";
import { ApiError } from "../lib/api";
import { money } from "../lib/format";
import { useRevenue } from "../context/RevenueContext";
import { Button, Modal } from "./ui";

type RevenueValueProps = {
  value: number | null | undefined;
  className?: string;
};

export function RevenueValue({ value, className = "" }: RevenueValueProps) {
  const { unlocked, unlock } = useRevenue();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const openModal = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setPassword("");
    setError(null);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    if (!isSubmitting) {
      setIsModalOpen(false);
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setIsSubmitting(true);
    setError(null);

    try {
      await unlock(password);
      setIsModalOpen(false);
      setPassword("");
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        setError("رمز عبور نادرست است");
      } else {
        setError("خطا در ارتباط با سرور");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (unlocked) {
    return <span className={className}>{money(value ?? 0)}</span>;
  }

  return (
    <>
      <button
        type="button"
        className={[
          "inline-flex items-baseline rounded-lg text-inherit transition hover:text-accent focus:outline-none focus:ring-2 focus:ring-accent",
          className,
        ].join(" ")}
        aria-label="باز کردن قفل درآمد"
        onClick={openModal}
      >
        <span className="tracking-[0.18em]" aria-label="محرمانه">
          ••••
        </span>
      </button>

      {isModalOpen && (
        <Modal onClose={closeModal} widthClassName="max-w-sm">
          <form className="grid gap-4" onSubmit={(event) => void submit(event)}>
            <div>
              <h2 className="text-2xl font-black text-text">باز کردن درآمد</h2>
            </div>
            <label className="block text-sm font-semibold text-muted" htmlFor="revenue-password">
              رمز عبور
            </label>
            <input
              id="revenue-password"
              className="w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition focus:border-accent"
              type="password"
              autoFocus
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            {error && (
              <div className="rounded-xl border border-bad/30 bg-[#2a1518] px-4 py-3 text-sm font-semibold text-bad">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-3">
              <Button variant="ghost" onClick={closeModal} disabled={isSubmitting}>
                انصراف
              </Button>
              <Button type="submit" disabled={isSubmitting || !password.trim()}>
                {isSubmitting ? "در حال بررسی..." : "نمایش"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
