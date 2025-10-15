"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";

import {
  ToastProvider as RadixToastProvider,
  ToastViewport,
  ToastRoot,
  ToastTitle,
  ToastDescription,
  ToastActions,
  ToastCloseButton,
  toastVariants,
} from "./ui/toast";

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

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const addToast = useCallback(
    (toast: Omit<Toast, "id">) => {
      const id = crypto.randomUUID?.() ?? `toast-${Date.now()}`;
      const newToast: Toast = { ...toast, id };

      setToasts((prev) => [...prev, newToast]);

      const duration = toast.duration ?? 5000;
      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }
    },
    [removeToast],
  );

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
  return (
    <RadixToastProvider label="Notifications" swipeDirection="right">
      <ToastViewport />
      <div
        role="region"
        aria-label="Notifications"
        aria-live="polite"
        aria-atomic="false"
        className="toast-container"
      >
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
        ))}
      </div>
    </RadixToastProvider>
  );
}

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: (id: string) => void }): JSX.Element {
  const variantClass = toastVariants[toast.type] ?? toastVariants.info;
  
  // Add animation based on toast type
  const animationClass = toast.type === 'success' ? 'slide-up bounce' : 
                        toast.type === 'error' ? 'slide-up shake' : 
                        'slide-up fade-in';

  return (
    <ToastRoot
      open
      duration={toast.duration ?? 5000}
      onOpenChange={(isOpen) => {
        if (!isOpen) {
          onRemove(toast.id);
        }
      }}
      className={cx(variantClass, animationClass)}
    >
      <VisuallyHidden role="status" aria-live="polite" aria-atomic="true">
        {toast.message}
      </VisuallyHidden>
      {toast.title ? <ToastTitle>{toast.title}</ToastTitle> : null}
      <ToastDescription>{toast.message}</ToastDescription>
      <ToastActions>
        <ToastCloseButton aria-label="Dismiss notification">×</ToastCloseButton>
      </ToastActions>
    </ToastRoot>
  );
}
