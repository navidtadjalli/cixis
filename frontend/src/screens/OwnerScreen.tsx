import { useState } from "react";
import { apiPost } from "../lib/api";
import { brand } from "../brand.generated";

// brand.id is a build-time literal; alias to string so both brand builds typecheck.
const brandId: string = brand.id;
import { PasswordGate } from "../components/PasswordGate";
import { FreeAllowanceConfig } from "../components/FreeAllowanceConfig";
import { SetupScreen } from "./SetupScreen";
import { SettingsScreen, type SettingsState } from "./SettingsScreen";

// Owner-only tab: the merged راه‌اندازی + تنظیمات انتشار (and, for CiXiS, the
// staff free-allowance config). Gated by the GOD code via the publish-unlock
// endpoint, which both validates the code and returns the publish settings.
export function OwnerScreen({ onDataChanged }: { onDataChanged: () => void }) {
  const [godCode, setGodCode] = useState<string | null>(null);
  const [settings, setSettings] = useState<SettingsState | null>(null);

  if (godCode === null || settings === null) {
    return (
      <PasswordGate
        title="تنظیمات برنامه"
        prompt="این بخش فقط برای مالک است. کد اصلی را وارد کنید."
        onSubmit={async (code) => {
          const state = await apiPost<SettingsState>(
            "/settings/publish/unlock/",
            { god_code: code },
          );
          setSettings(state);
          setGodCode(code);
        }}
      />
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8">
      <div>
        <h2 className="text-3xl font-black text-text">تنظیمات برنامه</h2>
        <p className="mt-2 text-base text-muted">
          راه‌اندازی و تنظیمات انتشار
          {brandId === "cixis" ? " و سهمیه رایگان پرسنل" : ""} — فقط برای مالک.
        </p>
      </div>

      {brandId === "cixis" && <FreeAllowanceConfig />}

      <section className="flex flex-col gap-3">
        <h3 className="text-xl font-black text-text">راه‌اندازی</h3>
        <SetupScreen onDataChanged={onDataChanged} embeddedPassword={godCode} />
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-xl font-black text-text">تنظیمات انتشار</h3>
        <SettingsScreen embedded={{ godCode, state: settings }} />
      </section>
    </div>
  );
}
