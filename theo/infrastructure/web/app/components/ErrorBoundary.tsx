"use client";

import { Component, type ReactNode, type ErrorInfo } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void, errorCount: number) => ReactNode;
  /**
   * Maximum number of consecutive errors before showing permanent error state
   */
  maxRetries?: number;
  /**
   * Callback when error occurs
   */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorCount: number;
  errorTimestamp: number | null;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null,
      errorCount: 0,
      errorTimestamp: null
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { 
      hasError: true, 
      error,
      errorTimestamp: Date.now()
    };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Increment error count
    this.setState((prevState) => ({
      errorCount: prevState.errorCount + 1
    }));

    // Call custom error handler if provided
    this.props.onError?.(error, errorInfo);

    // Log error with component stack for debugging
    if (process.env.NODE_ENV === "development") {
      console.error("ErrorBoundary caught an error:", {
        error,
        componentStack: errorInfo.componentStack,
        digest: errorInfo.digest,
        errorCount: this.state.errorCount + 1,
      });
    } else {
      // In production, log minimal information with error ID
      const errorId = `ERR-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      console.error(`[${errorId}] Application error:`, error.message);
    }
  }

  reset = (): void => {
    const { errorTimestamp, errorCount } = this.state;
    const now = Date.now();
    
    // Reset error count if more than 5 minutes have passed since last error
    const shouldResetCount = errorTimestamp && (now - errorTimestamp) > 300000;
    
    this.setState({ 
      hasError: false, 
      error: null,
      errorCount: shouldResetCount ? 0 : errorCount,
      errorTimestamp: null
    });
  };

  override render(): ReactNode {
    if (this.state.hasError && this.state.error) {
      const { maxRetries = 3 } = this.props;
      const { errorCount } = this.state;
      const tooManyErrors = errorCount >= maxRetries;

      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset, errorCount);
      }

      return (
        <div className="alert alert-danger" role="alert">
          <div className="alert__title">
            {tooManyErrors ? "Persistent Error Detected" : "Something went wrong"}
          </div>
          <div className="alert__message">
            {tooManyErrors 
              ? "This component has encountered multiple errors. Please refresh the page or contact support if the problem persists."
              : this.state.error.message}
          </div>
          {process.env.NODE_ENV === "development" && (
            <details className="mt-2">
              <summary>Error details (dev only)</summary>
              <pre className="text-xs mt-2">
                {this.state.error.stack}
              </pre>
            </details>
          )}
          {!tooManyErrors && (
            <button 
              type="button" 
              className="btn btn-secondary btn-sm mt-2" 
              onClick={this.reset}
              aria-label="Try to recover from error"
            >
              Try again {errorCount > 1 && `(${errorCount}/${maxRetries})`}
            </button>
          )}
          {tooManyErrors && (
            <button 
              type="button" 
              className="btn btn-primary btn-sm mt-2" 
              onClick={() => window.location.reload()}
              aria-label="Reload page"
            >
              Reload page
            </button>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
