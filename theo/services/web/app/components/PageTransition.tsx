"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import styles from "./PageTransition.module.css";

interface PageTransitionProps {
  children: ReactNode;
}

export function PageTransition({ children }: PageTransitionProps) {
  const pathname = usePathname();
  const [displayPath, setDisplayPath] = useState(pathname);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    if (pathname !== displayPath) {
      setIsTransitioning(true);
      
      // Brief delay to show exit animation
      const exitTimer = setTimeout(() => {
        setDisplayPath(pathname);
        setIsTransitioning(false);
      }, 150);

      return () => clearTimeout(exitTimer);
    }
  }, [pathname, displayPath]);

  return (
    <div
      className={isTransitioning ? `${styles.transition} ${styles.exiting}` : styles.transition}
      data-path={displayPath}
    >
      {children}
    </div>
  );
}
