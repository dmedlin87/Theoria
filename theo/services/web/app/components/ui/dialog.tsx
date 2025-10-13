"use client";

import { forwardRef, type ComponentPropsWithoutRef, type ElementRef, type ReactNode } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";

import styles from "./dialog.module.css";
import "./tokens.module.css";

type DialogContentProps = ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  className?: string;
};

type DialogTitleProps = ComponentPropsWithoutRef<typeof DialogPrimitive.Title> & {
  className?: string;
};

type DialogDescriptionProps = ComponentPropsWithoutRef<typeof DialogPrimitive.Description> & {
  className?: string;
};

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export const DialogContent = forwardRef<ElementRef<typeof DialogPrimitive.Content>, DialogContentProps>(
  ({ className, children, ...props }, ref) => (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className={styles.overlay} />
      <DialogPrimitive.Content ref={ref} className={cx(styles.content, className)} {...props}>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  ),
);
DialogContent.displayName = DialogPrimitive.Content.displayName;

export const DialogTitle = forwardRef<ElementRef<typeof DialogPrimitive.Title>, DialogTitleProps>(
  ({ className, ...props }, ref) => (
    <DialogPrimitive.Title ref={ref} className={cx(styles.title, className)} {...props} />
  ),
);
DialogTitle.displayName = DialogPrimitive.Title.displayName;

export const DialogDescription = forwardRef<ElementRef<typeof DialogPrimitive.Description>, DialogDescriptionProps>(
  ({ className, ...props }, ref) => (
    <DialogPrimitive.Description ref={ref} className={cx(styles.description, className)} {...props} />
  ),
);
DialogDescription.displayName = DialogPrimitive.Description.displayName;

export const DialogActions = ({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}): JSX.Element => {
  return <div className={cx(styles.actions, className)}>{children}</div>;
};
