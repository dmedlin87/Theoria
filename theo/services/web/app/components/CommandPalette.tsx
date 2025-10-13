"use client";

import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";

interface CommandEntry {
  label: string;
  href: string;
  description?: string;
  shortcut?: string;
  keywords?: string;
}

const NAVIGATION_COMMANDS: CommandEntry[] = [
  { label: "Home", href: "/", keywords: "dashboard root" },
  { label: "Open chat", href: "/chat", keywords: "conversation" },
  { label: "Copilot workspace", href: "/copilot", keywords: "assist" },
  { label: "Search workspace", href: "/search", keywords: "find query" },
  { label: "Upload sources", href: "/upload", keywords: "ingest import" },
  { label: "Export center", href: "/export", keywords: "deliverable" },
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

  const handleSelect = (href: string) => {
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
              onSelect={() => handleSelect(command.href)}
              disabled={isPending}
            >
              <span className="cmdk-item__label">{command.label}</span>
              {command.shortcut ? <span className="cmdk-item__shortcut">{command.shortcut}</span> : null}
            </Command.Item>
          ))}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
