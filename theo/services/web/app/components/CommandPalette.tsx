"use client";

import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import "./CommandPalette.css";

import { openKeyboardShortcutsDialog } from "./help/KeyboardShortcutsDialog";
import { HELP_RESOURCES, KEYBOARD_SHORTCUTS_RESOURCE } from "./help/resources";

interface CommandEntry {
  label: string;
  href?: string;
  description?: string;
  shortcut?: string;
  keywords?: string;
  external?: boolean;
  action?: () => void;
}

const NAVIGATION_COMMANDS: CommandEntry[] = [
  { label: "Home", href: "/", keywords: "dashboard root" },
  { label: "Open chat", href: "/chat", keywords: "conversation" },
  { label: "Copilot workspace", href: "/copilot", keywords: "assist" },
  { label: "Search workspace", href: "/search", keywords: "find query" },
  { label: "Upload sources", href: "/upload", keywords: "ingest import" },
  { label: "Export center", href: "/export", keywords: "deliverable" },
  { label: "Settings", href: "/settings", keywords: "config preferences api key configuration" },
];

const HELP_COMMANDS: CommandEntry[] = [
  ...HELP_RESOURCES.map((resource) => ({
    label: resource.label,
    description: resource.description,
    href: resource.href,
    external: resource.external,
    keywords: resource.keywords,
    action: resource.href
      ? () => {
          if (resource.external) {
            window.open(resource.href!, "_blank", "noopener,noreferrer");
          } else {
            window.location.assign(resource.href!);
          }
        }
      : undefined,
  })),
  {
    label: KEYBOARD_SHORTCUTS_RESOURCE.label,
    description: KEYBOARD_SHORTCUTS_RESOURCE.description,
    keywords: KEYBOARD_SHORTCUTS_RESOURCE.keywords,
    action: openKeyboardShortcutsDialog,
  },
];

export default function CommandPalette(): JSX.Element {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const toggle = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((previous) => !previous);
      }
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("keydown", toggle);
    return () => window.removeEventListener("keydown", toggle);
  }, []);

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  const optimisticStatus = useMemo(() => {
    if (!pendingHref) {
      return "";
    }
    const command = NAVIGATION_COMMANDS.find((entry) => entry.href === pendingHref);
    if (!command) {
      return "";
    }
    return `Navigating to ${command.label}…`;
  }, [pendingHref]);

  const handleSelect = (command: CommandEntry) => {
    if (command.action) {
      command.action();
      setPendingHref(null);
      setOpen(false);
      return;
    }

    const href = command.href;
    if (!href) {
      setOpen(false);
      return;
    }

    if (command.external) {
      window.open(href, "_blank", "noopener,noreferrer");
      setPendingHref(null);
      setOpen(false);
      return;
    }

    setPendingHref(href);
    setOpen(false);
    startTransition(() => {
      router.push(href);
    });
  };

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      setSearchValue("");
      setPendingHref(null);
    }
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={handleOpenChange}
      label="Command menu"
      loop
      className="cmdk-dialog"
    >
      <div role="status" aria-live="polite" aria-atomic="true" className="visually-hidden">
        {isPending ? optimisticStatus : ""}
      </div>
      <Command.Input
        ref={inputRef}
        value={searchValue}
        onValueChange={setSearchValue}
        placeholder="Jump to a page or action…"
        className="cmdk-input"
      />
      <Command.List>
        <Command.Empty>No matches found.</Command.Empty>
        <Command.Group heading="Navigate">
          {NAVIGATION_COMMANDS.map((command) => (
            <Command.Item
              key={command.href}
              value={`${command.label.toLowerCase()} ${command.keywords ?? ""}`.trim()}
              onSelect={() => handleSelect(command)}
              disabled={isPending}
            >
              <span className="cmdk-item__label">
                <span>{command.label}</span>
                {command.description ? (
                  <span className="cmdk-item__description">{command.description}</span>
                ) : null}
              </span>
              {command.shortcut ? <span className="cmdk-item__shortcut">{command.shortcut}</span> : null}
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Group heading="Help">
          {HELP_COMMANDS.map((command) => (
            <Command.Item
              key={command.label}
              value={`${command.label.toLowerCase()} ${command.keywords ?? ""}`.trim()}
              onSelect={() => handleSelect(command)}
              disabled={isPending && Boolean(command.href) && !command.external}
            >
              <span className="cmdk-item__label">
                <span>{command.label}</span>
                {command.description ? (
                  <span className="cmdk-item__description">{command.description}</span>
                ) : null}
              </span>
            </Command.Item>
          ))}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
