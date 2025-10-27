"use client";

import { useState } from "react";

import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "../../components/ui/dropdown";
import {
  TooltipProvider,
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "../../components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogActions,
  DialogClose,
} from "../../components/ui/dialog";
import "../../components/ui/tokens.css";
import styles from "./SessionControls.module.css";

type SessionControlsProps = {
  disabled: boolean;
  onReset: () => void;
  onFork: () => void;
};

export function SessionControls({ disabled, onReset, onFork }: SessionControlsProps): JSX.Element {
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);

  const handleReset = () => {
    onReset();
    setIsConfirmOpen(false);
  };

  return (
    <TooltipProvider>
      <div className={styles.container} aria-label="Session history controls">
        <DropdownMenu>
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className={styles.trigger}
                  disabled={disabled}
                >
                  Session actions
                </button>
              </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent side="top" align="center">
              Manage the current transcript and branch new conversations.
            </TooltipContent>
          </Tooltip>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Conversation</DropdownMenuLabel>
            <DropdownMenuItem
              onSelect={() => {
                if (!disabled) {
                  onFork();
                }
              }}
              disabled={disabled}
            >
              Fork conversation
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => {
                if (!disabled) {
                  setIsConfirmOpen(true);
                }
              }}
              disabled={disabled}
            >
              Reset session
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Dialog open={isConfirmOpen} onOpenChange={setIsConfirmOpen}>
          <DialogContent>
            <DialogTitle>Reset this session?</DialogTitle>
            <DialogDescription>
              Clearing the session removes the conversation history and feedback. This cannot be undone.
            </DialogDescription>
            <DialogActions className={styles.dialogActions}>
              <DialogClose asChild>
                <button type="button" className={styles.dialogSecondary}>
                  Cancel
                </button>
              </DialogClose>
              <button type="button" className={styles.dialogPrimary} onClick={handleReset}>
                Reset session
              </button>
            </DialogActions>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
