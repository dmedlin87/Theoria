"use client";

import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogActions } from "./ui/dialog";
import Link from "next/link";
import styles from "./WelcomeModal.module.css";

const WELCOME_DISMISSED_KEY = "theoria.welcome.dismissed";

export function WelcomeModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem(WELCOME_DISMISSED_KEY);
    if (!dismissed) {
      // Delay showing modal slightly for better UX
      const timer = setTimeout(() => setOpen(true), 500);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, []);

  const handleDismiss = () => {
    localStorage.setItem(WELCOME_DISMISSED_KEY, "true");
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className={styles.content || ""}>
        <div className={styles.header}>
          <span className={styles.icon}>📖</span>
          <DialogTitle>Welcome to Theoria</DialogTitle>
          <DialogDescription>
            A modern research engine for theological study
          </DialogDescription>
        </div>

        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>What you can do</h3>
          <ul className={styles.features}>
            <li>
              <span className={styles.featureIcon}>🔍</span>
              <div>
                <strong>Scripture-anchored search</strong>
                <p>Find passages and cross-references across corpora</p>
              </div>
            </li>
            <li>
              <span className={styles.featureIcon}>🤖</span>
              <div>
                <strong>AI-powered chat</strong>
                <p>Ask questions with citations and context</p>
              </div>
            </li>
            <li>
              <span className={styles.featureIcon}>📚</span>
              <div>
                <strong>Document analysis</strong>
                <p>Upload and explore your own theological texts</p>
              </div>
            </li>
          </ul>
        </div>

        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>Quick setup</h3>
          <ol className={styles.steps}>
            <li>
              Configure your API key in <Link href="/settings" onClick={handleDismiss}>Settings</Link>
            </li>
            <li>
              Upload some documents in <Link href="/upload" onClick={handleDismiss}>Upload</Link>
            </li>
            <li>
              Start exploring in <Link href="/chat" onClick={handleDismiss}>Chat Studio</Link>
            </li>
          </ol>
        </div>

        <DialogActions>
          <button onClick={handleDismiss} className={styles.button}>
            Get Started
          </button>
        </DialogActions>
      </DialogContent>
    </Dialog>
  );
}
