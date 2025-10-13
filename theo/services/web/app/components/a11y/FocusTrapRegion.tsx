"use client";

import { useEffect, useState, type ReactElement } from "react";
import FocusTrap from "focus-trap-react";
import type { FocusTarget, FocusTrapOptions } from "focus-trap";

export interface FocusTrapRegionProps {
  /** Controls whether the focus trap is active. */
  active: boolean;
  /** Element that should receive focus when the trap is activated. */
  initialFocus?: FocusTarget;
  /** Fallback focus target if no tabbable elements are present. */
  fallbackFocus?: FocusTarget;
  /** Whether focus should return to the previously focused element when the trap deactivates. */
  restoreFocus?: boolean;
  /** Allows clicking outside the trap to dismiss. Defaults to false. */
  allowOutsideClick?: FocusTrapOptions["allowOutsideClick"];
  children: ReactElement;
}

/**
 * Wrapper around `focus-trap-react` that avoids hydration mismatches and provides
 * sensible defaults for our modal and drawer implementations.
 */
export function FocusTrapRegion({
  active,
  initialFocus,
  fallbackFocus,
  restoreFocus = true,
  allowOutsideClick = false,
  children,
}: FocusTrapRegionProps): ReactElement {
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isClient) {
    return children;
  }

  return (
    <FocusTrap
      active={active}
      focusTrapOptions={{
        initialFocus,
        fallbackFocus,
        returnFocusOnDeactivate: restoreFocus,
        allowOutsideClick,
        escapeDeactivates: true,
      }}
    >
      {children}
    </FocusTrap>
  );
}
