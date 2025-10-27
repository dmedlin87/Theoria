"use client";

import type { ReactNode } from "react";

interface FormErrorProps {
  message?: ReactNode | null;
  id?: string;
  role?: "alert" | "status";
  className?: string;
}

export default function FormError({
  message,
  id,
  role = "alert",
  className = "",
}: FormErrorProps): JSX.Element | null {
  if (!message) {
    return null;
  }

  const classes = ["form-error", className].filter(Boolean).join(" ");

  return (
    <p id={id} role={role} className={classes}>
      {message}
    </p>
  );
}
