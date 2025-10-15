"use client";

import { type ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../ui/tooltip";

import styles from "./HelpTooltip.module.css";

interface HelpTooltipProps {
  label: string;
  description: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
}

export function HelpTooltip({ label, description, side = "top" }: HelpTooltipProps): JSX.Element {
  return (
    <TooltipProvider delayDuration={150} skipDelayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button type="button" className={styles.iconButton} aria-label={label}>
            <span aria-hidden="true">?</span>
          </button>
        </TooltipTrigger>
        <TooltipContent side={side} className={styles.tooltipBody}>
          <p className={styles.tooltipTitle}>{label}</p>
          <div className={styles.tooltipBody}>{description}</div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export function TooltipParagraph({ children }: { children: ReactNode }): JSX.Element {
  return <p className={styles.tooltipParagraph}>{children}</p>;
}

export function TooltipList({ items }: { items: string[] }): JSX.Element {
  return (
    <ul className={styles.tooltipList}>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}
