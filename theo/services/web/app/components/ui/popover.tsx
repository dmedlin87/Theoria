"use client";

import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";

import styles from "./popover.module.css";
import "./tokens.module.css";

type PopoverContentProps = ComponentPropsWithoutRef<typeof PopoverPrimitive.Content> & {
  className?: string;
};

type PopoverArrowProps = ComponentPropsWithoutRef<typeof PopoverPrimitive.Arrow> & {
  className?: string;
};

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverClose = PopoverPrimitive.Close;

export const PopoverContent = forwardRef<
  ElementRef<typeof PopoverPrimitive.Content>,
  PopoverContentProps
>(({ className, sideOffset = 8, children, ...props }, ref) => (
  <PopoverPrimitive.Content
    ref={ref}
    className={cx(styles.content, className)}
    sideOffset={sideOffset}
    {...props}
  >
    {children}
  </PopoverPrimitive.Content>
));
PopoverContent.displayName = PopoverPrimitive.Content.displayName;

export const PopoverArrow = forwardRef<ElementRef<typeof PopoverPrimitive.Arrow>, PopoverArrowProps>(
  ({ className, ...props }, ref) => (
    <PopoverPrimitive.Arrow ref={ref} className={cx(styles.arrow, className)} {...props} />
  ),
);
PopoverArrow.displayName = PopoverPrimitive.Arrow.displayName;
