import type { CSSProperties } from "react";

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  className?: string;
  style?: CSSProperties;
}

export function Skeleton({ width, height, className = "", style = {} }: SkeletonProps): JSX.Element {
  const combinedStyle: CSSProperties = {
    width,
    height,
    ...style,
  };

  return <div className={`skeleton ${className}`.trim()} style={combinedStyle} />;
}

export function SkeletonText({ lines = 3, className = "" }: { lines?: number; className?: string }): JSX.Element {
  return (
    <div className={`stack-xs ${className}`.trim()}>
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} className="skeleton skeleton-text" />
      ))}
    </div>
  );
}

export function SkeletonCard(): JSX.Element {
  return (
    <div className="card">
      <div className="skeleton skeleton-title" />
      <div className="stack-xs mt-2">
        <div className="skeleton skeleton-text" />
        <div className="skeleton skeleton-text" />
        <div className="skeleton skeleton-text" style={{ width: "70%" }} />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 3 }: { count?: number }): JSX.Element {
  return (
    <div className="stack-md">
      {Array.from({ length: count }, (_, index) => (
        <SkeletonCard key={index} />
      ))}
    </div>
  );
}

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function Spinner({ size = "md", className = "" }: SpinnerProps): JSX.Element {
  const sizeClass = size === "lg" ? "spinner-lg" : "";
  
  return (
    <div
      className={`spinner ${sizeClass} ${className}`.trim()}
      role="status"
      aria-label="Loading"
    >
      <span className="sr-only">Loading...</span>
    </div>
  );
}

export function LoadingOverlay({ message = "Loading..." }: { message?: string }): JSX.Element {
  return (
    <div
      className="loading-overlay"
      role="alert"
      aria-busy="true"
      aria-live="polite"
    >
      <Spinner size="lg" />
      <p className="text-muted font-medium">{message}</p>
    </div>
  );
}
