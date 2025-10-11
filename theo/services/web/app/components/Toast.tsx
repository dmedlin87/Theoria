"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
}

interface ToastContextValue {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}

export function ToastProvider({ children }: { children: ReactNode }): JSX.Element {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = crypto.randomUUID?.() ?? `toast-${Date.now()}`;
    const newToast: Toast = { ...toast, id };
    
    setToasts((prev) => [...prev, newToast]);

    const duration = toast.duration ?? 5000;
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const value: ToastContextValue = {
    toasts,
    addToast,
    removeToast,
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}

function ToastContainer({ toasts, onRemove }: { toasts: Toast[]; onRemove: (id: string) => void }): JSX.Element {
  if (toasts.length === 0) {
    return <></>;
  }

  return (
    <div
      role="region"
      aria-label="Notifications"
      className="toast-container"
      style={{
        position: "fixed",
        bottom: "var(--space-4)",
        right: "var(--space-4)",
        zIndex: 9999,
        display: "grid",
        gap: "var(--space-2)",
        maxWidth: "min(420px, calc(100vw - var(--space-4) * 2))",
      }}
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: (id: string) => void }): JSX.Element {
  const alertClass = `alert alert-${toast.type}`;

  return (
    <div
      role="alert"
      aria-live="polite"
      aria-atomic="true"
      className={alertClass}
      style={{
        animation: "toast-slide-in 0.3s ease-out",
        boxShadow: "var(--shadow-xl)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-2)" }}>
        <div className="stack-xs" style={{ flex: 1 }}>
          {toast.title && <div className="alert__title">{toast.title}</div>}
          <div className="alert__message">{toast.message}</div>
        </div>
        <button
          type="button"
          onClick={() => onRemove(toast.id)}
          className="btn-ghost btn-sm"
          aria-label="Dismiss notification"
          style={{
            padding: "0.25rem",
            minWidth: "auto",
            width: "1.75rem",
            height: "1.75rem",
          }}
        >
          ×
        </button>
      </div>
      <style jsx>{`
        @keyframes toast-slide-in {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
