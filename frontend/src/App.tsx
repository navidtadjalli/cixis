import { useEffect, useState } from "react";

// Minimal scaffold shell. The full 3-screen shell is built in TASK-010.
export default function App() {
  const [status, setStatus] = useState<string>("در حال اتصال…");

  useEffect(() => {
    fetch("/api/")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => setStatus(`اتصال برقرار شد — نسخه ${d.version}`))
      .catch(() => setStatus("اتصال به سرور محلی برقرار نشد"));
  }, []);

  return (
    <div className="flex h-full items-center justify-center" dir="rtl">
      <div className="card p-8 text-center">
        <h1 className="text-3xl font-bold text-accent">CiXiS</h1>
        <p className="mt-2 text-muted">صندوق فروش کافه</p>
        <p className="mt-6 text-text">{status}</p>
      </div>
    </div>
  );
}
