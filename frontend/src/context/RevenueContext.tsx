import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { apiPost } from "../lib/api";

type UnlockResponse = {
  token: string;
  expires_at: string;
};

type RevenueContextValue = {
  unlocked: boolean;
  unlock: (password: string) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  lock: () => void;
};

const RevenueContext = createContext<RevenueContextValue | null>(null);

const REVENUE_LOCK_TIMEOUT_MS = 5 * 60 * 1000;

export function RevenueProvider({ children }: { children: ReactNode }) {
  const [unlocked, setUnlocked] = useState(false);
  const tokenRef = useRef<string | null>(null);
  const expiresAtRef = useRef<string | null>(null);
  const lockTimerRef = useRef<number | null>(null);

  const clearLockTimer = useCallback(() => {
    if (lockTimerRef.current !== null) {
      window.clearTimeout(lockTimerRef.current);
      lockTimerRef.current = null;
    }
  }, []);

  const lock = useCallback(() => {
    clearLockTimer();
    tokenRef.current = null;
    expiresAtRef.current = null;
    setUnlocked(false);
  }, [clearLockTimer]);

  const scheduleLock = useCallback(
    (expiresAt: string) => {
      clearLockTimer();

      const serverExpiryMs = Date.parse(expiresAt) - Date.now();
      const timeoutMs = Number.isFinite(serverExpiryMs)
        ? Math.max(0, Math.min(REVENUE_LOCK_TIMEOUT_MS, serverExpiryMs))
        : REVENUE_LOCK_TIMEOUT_MS;

      lockTimerRef.current = window.setTimeout(lock, timeoutMs);
    },
    [clearLockTimer, lock],
  );

  const unlock = useCallback(
    async (password: string) => {
      const response = await apiPost<UnlockResponse>("/revenue/unlock/", {
        password,
      });

      tokenRef.current = response.token;
      expiresAtRef.current = response.expires_at;
      setUnlocked(true);
      scheduleLock(response.expires_at);
    },
    [scheduleLock],
  );

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      await apiPost("/revenue/password/", {
        current_password: currentPassword,
        new_password: newPassword,
      });
    },
    [],
  );

  useEffect(() => {
    return clearLockTimer;
  }, [clearLockTimer]);

  return (
    <RevenueContext.Provider value={{ unlocked, unlock, changePassword, lock }}>
      {children}
    </RevenueContext.Provider>
  );
}

export function useRevenue() {
  const context = useContext(RevenueContext);

  if (!context) {
    throw new Error("useRevenue must be used within RevenueProvider");
  }

  return context;
}
