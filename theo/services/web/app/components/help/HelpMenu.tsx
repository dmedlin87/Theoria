"use client";

import { useCallback } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown";

import { KeyboardShortcutsDialog, openKeyboardShortcutsDialog } from "./KeyboardShortcutsDialog";
import styles from "./HelpMenu.module.css";
import { HELP_RESOURCES, KEYBOARD_SHORTCUTS_RESOURCE } from "./resources";

export function HelpMenu(): JSX.Element {
  const handleKeyboardShortcuts = useCallback(() => {
    openKeyboardShortcutsDialog();
  }, []);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button type="button" className={styles.triggerButton} aria-haspopup="menu">
            <span className={styles.triggerIcon} aria-hidden="true">
              ?
            </span>
            <span>Help</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="end">
          <DropdownMenuLabel>Documentation</DropdownMenuLabel>
          {HELP_RESOURCES.map((resource) => (
            <DropdownMenuItem key={resource.id} asChild>
              <a
                href={resource.href}
                target={resource.external ? "_blank" : undefined}
                rel={resource.external ? "noopener noreferrer" : undefined}
                className={styles.linkItem}
              >
                <span>{resource.label}</span>
                <span className={styles.resourceDescription}>{resource.description}</span>
              </a>
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Reference</DropdownMenuLabel>
          <DropdownMenuItem
            onSelect={() => {
              handleKeyboardShortcuts();
            }}
          >
            <div className={styles.linkItem} role="presentation">
              <span>{KEYBOARD_SHORTCUTS_RESOURCE.label}</span>
              <span className={styles.resourceDescription}>
                {KEYBOARD_SHORTCUTS_RESOURCE.description}
              </span>
            </div>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <KeyboardShortcutsDialog />
    </>
  );
}
