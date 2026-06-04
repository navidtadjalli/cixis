type WindowControls = {
  platform: string;
  minimize: () => void;
  toggleMaximize: () => void;
  close: () => void;
};

function getControls(): WindowControls | undefined {
  return window.cixis;
}

export function Titlebar() {
  const controls = getControls();

  return (
    <header
      className="[-webkit-app-region:drag] flex h-11 flex-none items-center justify-between border-b border-border bg-surface px-3 text-text"
    >
      <div className="flex items-center gap-2">
        <div className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-sm font-black text-[#1b1206]">
          Ç
        </div>
        <span className="text-sm font-bold tracking-normal">خروج</span>
      </div>

      <div
        className="[-webkit-app-region:no-drag] flex items-center gap-1"
      >
        <button
          type="button"
          className="grid h-8 w-9 place-items-center rounded-lg text-muted transition hover:bg-surface-2 hover:text-text disabled:opacity-40"
          aria-label="Minimize window"
          onClick={() => controls?.minimize()}
          disabled={!controls}
        >
          <span className="h-px w-3 bg-current" />
        </button>
        <button
          type="button"
          className="grid h-8 w-9 place-items-center rounded-lg text-muted transition hover:bg-surface-2 hover:text-text disabled:opacity-40"
          aria-label="Maximize window"
          onClick={() => controls?.toggleMaximize()}
          disabled={!controls}
        >
          <span className="h-3 w-3 rounded-[3px] border border-current" />
        </button>
        <button
          type="button"
          className="grid h-8 w-9 place-items-center rounded-lg text-muted transition hover:bg-bad hover:text-[#1b0a0a] disabled:opacity-40"
          aria-label="Close window"
          onClick={() => controls?.close()}
          disabled={!controls}
        >
          <span className="text-lg leading-none">x</span>
        </button>
      </div>
    </header>
  );
}
