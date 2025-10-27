"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode, useTransition } from "react";
import styles from "./PageTransition.module.css";

interface PageTransitionProps {
  children: ReactNode;
}

export function PageTransition({ children }: PageTransitionProps) {
  const pathname = usePathname();
  const [displayPath, setDisplayPath] = useState(pathname);
  const [isPending, startTransition] = useTransition();
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const previousPathnameRef = useRef(pathname);

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Handle pathname changes with React's transition API
  // Use ref to avoid unnecessary effect runs
  useEffect(() => {
    // Skip if pathname hasn't actually changed
    if (pathname === previousPathnameRef.current) {
      return;
    }

    previousPathnameRef.current = pathname;

    // Clear any pending timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Use transition for the update after a brief delay
    timeoutRef.current = setTimeout(() => {
      startTransition(() => {
        setDisplayPath(pathname);
      });
    }, 150);
  }, [pathname, startTransition]);

  return (
    <div
      className={isPending ? `${styles.transition} ${styles.exiting}` : styles.transition}
      data-path={displayPath}
    >
      {children}
    </div>
  );
}
