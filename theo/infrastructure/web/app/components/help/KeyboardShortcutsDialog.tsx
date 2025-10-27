"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Dialog,
  DialogActions,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../ui/dialog";

import styles from "./HelpMenu.module.css";

type Shortcut = {
  id: string;
  label: string;
  description: string;
  keys: string[];
};

type ShortcutSection = {
  id: string;
  title: string;
  shortcuts: Shortcut[];
};

export const KEYBOARD_SHORTCUTS_EVENT = "theoria:open-keyboard-shortcuts";

export function openKeyboardShortcutsDialog(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent(KEYBOARD_SHORTCUTS_EVENT));
}

const SHORTCUT_SECTIONS: ShortcutSection[] = [
  {
    id: "global",
    title: "Global",
    shortcuts: [
      {
        id: "command-palette",
        label: "Command palette",
        description: "Open quick navigation and actions",
        keys: ["⌘", "K"],
      },
      {
        id: "command-palette-windows",
        label: "Command palette (Windows/Linux)",
        description: "Toggle quick actions",
        keys: ["Ctrl", "K"],
      },
      {
        id: "escape",
        label: "Close overlays",
        description: "Dismiss menus, dialogs, and side panels",
        keys: ["Esc"],
      },
    ],
  },
  {
    id: "chat",
    title: "Chat workspace",
    shortcuts: [
      {
        id: "chat-send",
        label: "Send message",
        description: "Submit the current prompt",
        keys: ["⌘", "Enter"],
      },
      {
        id: "chat-send-windows",
        label: "Send message (Windows/Linux)",
        description: "Submit without clicking the Send button",
        keys: ["Ctrl", "Enter"],
      },
    ],
  },
];

export function KeyboardShortcutsDialog(): JSX.Element {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }
    const handleOpen = () => setOpen(true);
    window.addEventListener(KEYBOARD_SHORTCUTS_EVENT, handleOpen);
    return () => window.removeEventListener(KEYBOARD_SHORTCUTS_EVENT, handleOpen);
  }, []);

  const renderedSections = useMemo(
    () =>
      SHORTCUT_SECTIONS.map((section) => (
        <section key={section.id} className={styles.shortcutSection} aria-labelledby={`${section.id}-heading`}>
          <h3 id={`${section.id}-heading`}>{section.title}</h3>
          <div className={styles.shortcutGrid}>
            {section.shortcuts.map((shortcut) => (
              <div key={shortcut.id} className={styles.shortcutRow}>
                <div>
                  <p className={styles.shortcutLabel}>{shortcut.label}</p>
                  <p className={styles.resourceDescription}>{shortcut.description}</p>
                </div>
                <span className={styles.shortcutKeys} aria-label={`${shortcut.label} keys`}>
                  {shortcut.keys.map((key) => (
                    <kbd key={key} className={styles.shortcutKey}>
                      {key}
                    </kbd>
                  ))}
                </span>
              </div>
            ))}
          </div>
        </section>
      )),
    [],
  );

  const handleOpenChange = useCallback((nextOpen: boolean) => {
    setOpen(nextOpen);
  }, []);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className={styles.dialogContent} aria-describedby="keyboard-shortcuts-description">
        <DialogTitle>Keyboard shortcuts</DialogTitle>
        <DialogDescription id="keyboard-shortcuts-description">
          Learn the fastest ways to navigate Theoria and work without leaving the keyboard.
        </DialogDescription>
        {renderedSections}
        <DialogActions className={styles.dialogFooter}>
          <DialogClose asChild>
            <button type="button" className="btn btn-secondary">
              Close
            </button>
          </DialogClose>
        </DialogActions>
      </DialogContent>
    </Dialog>
  );
}
