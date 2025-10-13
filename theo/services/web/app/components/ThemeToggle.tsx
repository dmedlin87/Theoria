"use client";

import { useEffect, useState } from "react";
import styles from "./ThemeToggle.module.css";

type Theme = "light" | "dark" | "auto";

const STORAGE_KEY = "theo-theme-preference";

function getSystemTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "auto";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark" || stored === "auto") {
    return stored;
  }
  return "auto";
}

function applyTheme(theme: Theme): void {
  const resolvedTheme = theme === "auto" ? getSystemTheme() : theme;
  document.documentElement.setAttribute("data-theme", resolvedTheme);
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("auto");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = getStoredTheme();
    setTheme(stored);
    applyTheme(stored);

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => {
      if (getStoredTheme() === "auto") {
        applyTheme("auto");
      }
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  const handleThemeChange = (newTheme: Theme) => {
    setTheme(newTheme);
    localStorage.setItem(STORAGE_KEY, newTheme);
    applyTheme(newTheme);
  };

  // Prevent hydration mismatch by not rendering until mounted
  if (!mounted) {
    return (
      <div className={styles.toggle} aria-hidden="true">
        <span className={styles.label}>Theme</span>
        <div className={styles.buttons}>
          <button type="button" className={styles.button} disabled aria-label="Loading theme preference">
            <span className={styles.icon}>○</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.toggle} role="group" aria-label="Theme selection">
      <span className={styles.label}>Theme</span>
      <div className={styles.buttons}>
        <button
          type="button"
          className={theme === "light" ? `${styles.button} ${styles.active}` : styles.button}
          onClick={() => handleThemeChange("light")}
          aria-label="Light theme"
          aria-pressed={theme === "light"}
          title="Light theme"
        >
          <span className={styles.icon} aria-hidden="true">☀</span>
        </button>
        <button
          type="button"
          className={theme === "auto" ? `${styles.button} ${styles.active}` : styles.button}
          onClick={() => handleThemeChange("auto")}
          aria-label="Auto theme (follows system)"
          aria-pressed={theme === "auto"}
          title="Auto theme (follows system)"
        >
          <span className={styles.icon} aria-hidden="true">◐</span>
        </button>
        <button
          type="button"
          className={theme === "dark" ? `${styles.button} ${styles.active}` : styles.button}
          onClick={() => handleThemeChange("dark")}
          aria-label="Dark theme"
          aria-pressed={theme === "dark"}
          title="Dark theme"
        >
          <span className={styles.icon} aria-hidden="true">☾</span>
        </button>
      </div>
    </div>
  );
}
