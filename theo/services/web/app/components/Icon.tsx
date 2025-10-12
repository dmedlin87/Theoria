"use client";

import { forwardRef, type SVGProps } from "react";
import type { LucideIcon } from "lucide-react";

export type IconSize = "sm" | "md" | "lg" | number;

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, "ref"> {
  icon: LucideIcon;
  size?: IconSize;
  decorative?: boolean;
  label?: string;
  className?: string;
}

const SIZE_MAP: Record<Exclude<IconSize, number>, number> = {
  sm: 16,
  md: 20,
  lg: 24,
};

export const Icon = forwardRef<SVGSVGElement, IconProps>(function Icon(
  { icon: IconComponent, size = "md", decorative = true, label, className = "", ...props },
  ref,
) {
  const resolvedSize = typeof size === "number" ? size : SIZE_MAP[size];
  const classes = ["icon", typeof size === "string" ? `icon--${size}` : null, className]
    .filter(Boolean)
    .join(" ");

  const accessibilityProps = decorative
    ? { "aria-hidden": true }
    : { role: "img", "aria-label": label ?? props["aria-label"] };

  return (
    <IconComponent
      ref={ref}
      width={props.width ?? resolvedSize}
      height={props.height ?? resolvedSize}
      strokeWidth={(props.strokeWidth as number | undefined) ?? 2}
      className={classes}
      focusable="false"
      {...props}
      {...accessibilityProps}
    />
  );
});
