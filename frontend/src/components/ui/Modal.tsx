import { useEffect, type ReactNode } from "react";

type ModalProps = {
  children: ReactNode;
  onClose: () => void;
  widthClassName?: string;
};

export function Modal({
  children,
  onClose,
  widthClassName = "max-w-lg",
}: ModalProps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/55 p-6 backdrop-blur-sm"
      onMouseDown={onClose}
      role="presentation"
    >
      <div
        className={[
          "w-full rounded-2xl border border-border bg-surface p-6 text-text shadow-2xl",
          widthClassName,
        ].join(" ")}
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {children}
      </div>
    </div>
  );
}
