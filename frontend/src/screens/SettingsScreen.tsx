import { FormEvent, useState } from "react";
import { ApiError, apiPost } from "../lib/api";
import { Badge, Button } from "../components/ui";

type StorageSettings = {
  s3_access_key: string;
  s3_secret_key: string;
  s3_bucket: string;
  s3_endpoint_url: string;
  s3_region: string;
};

type SettingsState = {
  settings: StorageSettings;
  configured: boolean;
  website_url: string;
  sync_enabled: boolean;
};

const FIELDS: {
  key: keyof StorageSettings;
  label: string;
  hint?: string;
  secret?: boolean;
}[] = [
  { key: "s3_access_key", label: "کلید دسترسی", secret: true },
  { key: "s3_secret_key", label: "کلید مخفی", secret: true },
  { key: "s3_bucket", label: "نام باکت", hint: "cixis" },
  {
    key: "s3_endpoint_url",
    label: "آدرس فضای ذخیره‌سازی",
    hint: "https://s3.ir-thr-at1.arvanstorage.ir",
  },
  { key: "s3_region", label: "ناحیه", hint: "ir-thr-at1" },
];

const EMPTY: StorageSettings = {
  s3_access_key: "",
  s3_secret_key: "",
  s3_bucket: "",
  s3_endpoint_url: "",
  s3_region: "",
};

function detailFromError(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const body = error.body as { detail?: string } | null;
    if (body?.detail) {
      return body.detail;
    }
  }
  return fallback;
}

export function SettingsScreen() {
  const [godCode, setGodCode] = useState("");
  const [state, setState] = useState<SettingsState | null>(null);
  const [form, setForm] = useState<StorageSettings>(EMPTY);
  // The unlock response masks credentials. Sending a mask back would overwrite the
  // real value with dots, so a credential only leaves the form if it was retyped.
  const [touched, setTouched] = useState<Set<keyof StorageSettings>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const unlock = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      const next = await apiPost<SettingsState>("/settings/publish/unlock/", {
        god_code: godCode,
      });
      setState(next);
      setForm(next.settings);
      setTouched(new Set());
    } catch (caught) {
      setError(detailFromError(caught, "باز کردن تنظیمات ناموفق بود"));
    } finally {
      setBusy(false);
    }
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);

    const payload: Record<string, string> = { god_code: godCode };
    for (const field of FIELDS) {
      const isUntouchedSecret = field.secret && !touched.has(field.key);
      payload[field.key] = isUntouchedSecret ? "" : form[field.key];
    }

    try {
      const next = await apiPost<SettingsState>("/settings/publish/", payload);
      setState(next);
      setForm(next.settings);
      setTouched(new Set());
      setSaved(true);
    } catch (caught) {
      setError(detailFromError(caught, "ذخیره تنظیمات ناموفق بود"));
    } finally {
      setBusy(false);
    }
  };

  const updateField = (key: keyof StorageSettings, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    setTouched((current) => new Set(current).add(key));
    setSaved(false);
  };

  if (state === null) {
    return (
      <div className="mx-auto max-w-md">
        <h1 className="text-2xl font-black text-text">تنظیمات انتشار</h1>
        <p className="mt-2 text-sm text-muted">
          برای دیدن و تغییر تنظیمات فضای ذخیره‌سازی، کد دسترسی را وارد کنید.
        </p>

        <form onSubmit={unlock} className="mt-6 space-y-4">
          <input
            type="password"
            value={godCode}
            onChange={(event) => setGodCode(event.target.value)}
            placeholder="کد دسترسی"
            autoFocus
            className="w-full rounded-xl border border-border bg-surface-2 px-4 py-3 text-text outline-none focus:border-accent"
          />

          {error && <p className="text-sm font-semibold text-bad">{error}</p>}

          <Button type="submit" disabled={busy || !godCode} className="w-full">
            {busy ? "در حال بررسی..." : "باز کردن"}
          </Button>
        </form>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-black text-text">تنظیمات انتشار</h1>
        {state.configured ? (
          <Badge tone="good">پیکربندی‌شده</Badge>
        ) : (
          <Badge tone="warn">ناقص</Badge>
        )}
      </div>

      {state.website_url && (
        <p className="mt-3 text-sm text-muted">
          نشانی منو برای کد QR:{" "}
          <span className="font-mono text-accent" dir="ltr">
            {state.website_url}
          </span>
        </p>
      )}

      <form onSubmit={save} className="mt-6 space-y-5">
        {FIELDS.map((field) => (
          <label key={field.key} className="block">
            <span className="text-sm font-bold text-text">{field.label}</span>
            <input
              type="text"
              dir="ltr"
              value={form[field.key]}
              onChange={(event) => updateField(field.key, event.target.value)}
              placeholder={field.hint}
              className="mt-1.5 w-full rounded-xl border border-border bg-surface-2 px-4 py-2.5 text-left font-mono text-sm text-text outline-none focus:border-accent"
            />
            {field.secret && !touched.has(field.key) && form[field.key] && (
              <span className="mt-1 block text-xs text-muted">
                برای نگه داشتن مقدار فعلی، دست نزنید.
              </span>
            )}
          </label>
        ))}

        {error && <p className="text-sm font-semibold text-bad">{error}</p>}
        {saved && <p className="text-sm font-semibold text-good">تنظیمات ذخیره شد.</p>}

        <div className="flex gap-3">
          <Button type="submit" disabled={busy}>
            {busy ? "در حال ذخیره..." : "ذخیره"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => {
              setState(null);
              setGodCode("");
              setForm(EMPTY);
              setError(null);
              setSaved(false);
            }}
          >
            بستن
          </Button>
        </div>
      </form>
    </div>
  );
}
