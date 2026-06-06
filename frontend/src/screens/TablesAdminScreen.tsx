import { useMemo, useState } from "react";
import { ApiError, apiDelete, apiPatch, apiPost } from "../lib/api";
import { Badge, Button, Modal } from "../components/ui";
import type { Table } from "./TablesScreen";

type TablesAdminScreenProps = {
  tables: Table[];
  isLoading: boolean;
  refresh: () => Promise<void>;
};

type DialogState =
  | { type: "add"; name: string }
  | { type: "rename"; table: Table; name: string }
  | { type: "delete"; table: Table }
  | null;

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 409) {
    return "میز دارای سفارش باز است";
  }

  return "خطا در ارتباط با سرور";
}

export function TablesAdminScreen({
  tables,
  isLoading,
  refresh,
}: TablesAdminScreenProps) {
  const [dialog, setDialog] = useState<DialogState>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const sortedTables = useMemo(() => {
    return [...tables].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
  }, [tables]);

  const runMutation = async (mutation: () => Promise<void>) => {
    setIsSubmitting(true);
    setError(null);

    try {
      await mutation();
      await refresh();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitAdd = () => {
    if (dialog?.type !== "add") {
      return;
    }
    const name = dialog.name.trim();
    if (!name) {
      setError("نام میز را وارد کنید");
      return;
    }
    void runMutation(async () => {
      await apiPost<Table>("/tables/", { name });
      setDialog(null);
    });
  };

  const submitRename = () => {
    if (dialog?.type !== "rename") {
      return;
    }
    const name = dialog.name.trim();
    if (!name) {
      setError("نام میز را وارد کنید");
      return;
    }
    void runMutation(async () => {
      await apiPatch<Table>(`/tables/${dialog.table.id}/`, { name });
      setDialog(null);
    });
  };

  const submitDelete = () => {
    if (dialog?.type !== "delete") {
      return;
    }
    void runMutation(async () => {
      await apiDelete<null>(`/tables/${dialog.table.id}/`);
      setDialog(null);
    });
  };

  const closeDialog = () => {
    if (!isSubmitting) {
      setDialog(null);
    }
  };

  return (
    <>
      <div className="flex min-h-full flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-semibold text-muted">
            افزودن، تغییر نام و حذف میزها
          </p>
          <Button onClick={() => setDialog({ type: "add", name: "" })}>
            افزودن میز
          </Button>
        </div>

        {error && (
          <div className="rounded-xl border border-bad/30 bg-[#2a1518] px-4 py-3 text-base font-semibold text-bad">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="rounded-xl border border-border bg-surface p-8 text-lg text-muted">
            در حال دریافت میزها...
          </div>
        ) : sortedTables.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface p-8 text-lg text-muted">
            هنوز میزی ثبت نشده است.
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {sortedTables.map((table) => (
              <div
                key={table.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <span className="text-lg font-black text-text">{table.name}</span>
                  {table.active_order_id !== null && (
                    <Badge tone="accent">دارای سفارش باز</Badge>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    onClick={() =>
                      setDialog({ type: "rename", table, name: table.name })
                    }
                  >
                    تغییر نام
                  </Button>
                  <Button
                    variant="ghost"
                    className="border-bad/40 text-bad hover:bg-bad/10"
                    onClick={() => setDialog({ type: "delete", table })}
                  >
                    حذف
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {dialog?.type === "add" && (
        <Modal onClose={closeDialog}>
          <div className="mb-5">
            <h2 className="text-2xl font-black text-text">افزودن میز</h2>
          </div>
          <label className="block text-sm font-semibold text-muted" htmlFor="table-name">
            نام میز
          </label>
          <input
            id="table-name"
            className="mt-2 w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition focus:border-accent"
            autoFocus
            value={dialog.name}
            onChange={(event) =>
              setDialog({ type: "add", name: event.target.value })
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                submitAdd();
              }
            }}
          />
          <div className="mt-6 flex gap-3">
            <Button className="flex-1" variant="ghost" onClick={closeDialog}>
              انصراف
            </Button>
            <Button className="flex-1" onClick={submitAdd} disabled={isSubmitting}>
              ثبت میز
            </Button>
          </div>
        </Modal>
      )}

      {dialog?.type === "rename" && (
        <Modal onClose={closeDialog}>
          <div className="mb-5">
            <h2 className="text-2xl font-black text-text">تغییر نام میز</h2>
          </div>
          <label
            className="block text-sm font-semibold text-muted"
            htmlFor="rename-table-name"
          >
            نام میز
          </label>
          <input
            id="rename-table-name"
            className="mt-2 w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-lg font-semibold text-text outline-none transition focus:border-accent"
            autoFocus
            value={dialog.name}
            onChange={(event) =>
              setDialog({ ...dialog, name: event.target.value })
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                submitRename();
              }
            }}
          />
          <div className="mt-6 flex gap-3">
            <Button className="flex-1" variant="ghost" onClick={closeDialog}>
              انصراف
            </Button>
            <Button className="flex-1" onClick={submitRename} disabled={isSubmitting}>
              ذخیره
            </Button>
          </div>
        </Modal>
      )}

      {dialog?.type === "delete" && (
        <Modal onClose={closeDialog}>
          <div className="mb-5">
            <h2 className="text-2xl font-black text-text">حذف میز</h2>
          </div>
          <p className="rounded-xl border border-warn/30 bg-warn/10 px-4 py-3 text-base font-semibold leading-8 text-warn">
            میز «{dialog.table.name}» حذف شود؟
          </p>
          <div className="mt-6 flex gap-3">
            <Button className="flex-1" variant="ghost" onClick={closeDialog}>
              انصراف
            </Button>
            <Button
              className="flex-1 bg-bad text-[#1b0a0a] hover:bg-bad/90"
              onClick={submitDelete}
              disabled={isSubmitting}
            >
              حذف میز
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}
