"use client";

import { forwardRef, type ComponentPropsWithoutRef, type ElementRef, type ReactNode } from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";

import styles from "./toast.module.css";
import "./tokens.css";

type ToastRootProps = ComponentPropsWithoutRef<typeof ToastPrimitive.Root> & {
  className?: string;
};

type ToastViewportProps = ComponentPropsWithoutRef<typeof ToastPrimitive.Viewport> & {
  className?: string;
};

type ToastTitleProps = ComponentPropsWithoutRef<typeof ToastPrimitive.Title> & {
  className?: string;
};

type ToastDescriptionProps = ComponentPropsWithoutRef<typeof ToastPrimitive.Description> & {
  className?: string;
};

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export const ToastProvider = ToastPrimitive.Provider;
export const ToastClose = ToastPrimitive.Close;
export const ToastAction = ToastPrimitive.Action;

export const ToastRoot = forwardRef<ElementRef<typeof ToastPrimitive.Root>, ToastRootProps>(
  ({ className, ...props }, ref) => (
    <ToastPrimitive.Root ref={ref} className={cx(styles.toast, className)} {...props} />
  ),
);
ToastRoot.displayName = ToastPrimitive.Root.displayName;

export const ToastViewport = forwardRef<ElementRef<typeof ToastPrimitive.Viewport>, ToastViewportProps>(
  ({ className, ...props }, ref) => (
    <ToastPrimitive.Viewport ref={ref} className={cx(styles.viewport, className)} {...props} />
  ),
);
ToastViewport.displayName = ToastPrimitive.Viewport.displayName;

export const ToastTitle = forwardRef<ElementRef<typeof ToastPrimitive.Title>, ToastTitleProps>(
  ({ className, ...props }, ref) => (
    <ToastPrimitive.Title ref={ref} className={cx(styles.title, className)} {...props} />
  ),
);
ToastTitle.displayName = ToastPrimitive.Title.displayName;

export const ToastDescription = forwardRef<ElementRef<typeof ToastPrimitive.Description>, ToastDescriptionProps>(
  ({ className, ...props }, ref) => (
    <ToastPrimitive.Description ref={ref} className={cx(styles.description, className)} {...props} />
  ),
);
ToastDescription.displayName = ToastPrimitive.Description.displayName;

export const ToastActions = ({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}): JSX.Element => {
  return <div className={cx(styles.actions, className)}>{children}</div>;
};

export const ToastCloseButton = forwardRef<
  ElementRef<typeof ToastPrimitive.Close>,
  ComponentPropsWithoutRef<typeof ToastPrimitive.Close> & { className?: string }
>(({ className, ...props }, ref) => (
  <ToastPrimitive.Close ref={ref} className={cx(styles.closeButton, className)} {...props} />
));
ToastCloseButton.displayName = ToastPrimitive.Close.displayName;

export const toastVariants = {
  success: styles.toastSuccess,
  error: styles.toastError,
  warning: styles.toastWarning,
  info: styles.toastInfo,
};
