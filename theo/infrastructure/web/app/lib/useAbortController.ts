import { useEffect, useMemo, useRef } from "react";

/**
 * Hook to manage AbortController for request cancellation
 * Automatically aborts requests when component unmounts
 * 
 * @returns Object with signal and abort function
 * 
 * @example
 * function MyComponent() {
 *   const { signal, abort } = useAbortController();
 * 
 *   useEffect(() => {
 *     fetchData('/api/data', { signal });
 *   }, [signal]);
 * 
 *   return <button onClick={abort}>Cancel</button>;
 * }
 */
export function useAbortController(): {
  signal: AbortSignal;
  abort: (reason?: string) => void;
  reset: () => void;
} {
  const controllerRef = useRef<AbortController>(new AbortController());

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (!controllerRef.current.signal.aborted) {
        controllerRef.current.abort("Component unmounted");
      }
    };
  }, []);

  // Use useMemo to create stable functions and signal
  return useMemo(() => {
    const abort = (reason?: string) => {
      if (!controllerRef.current.signal.aborted) {
        controllerRef.current.abort(reason ?? "Request cancelled");
      }
    };

    const reset = () => {
      abort("Controller reset");
      controllerRef.current = new AbortController();
    };

    return {
      signal: controllerRef.current.signal,
      abort,
      reset,
    };
  }, []);
}

/**
 * Hook to create a new AbortController for each dependency change
 * Useful for search inputs or filters that should cancel previous requests
 * 
 * @param dependencies - Values that trigger controller reset
 * @returns AbortSignal
 * 
 * @example
 * function SearchComponent({ query }: { query: string }) {
 *   const signal = useAbortSignal([query]);
 * 
 *   useEffect(() => {
 *     search(query, { signal });
 *   }, [query, signal]);
 * }
 */
export function useAbortSignal(dependencies: unknown[]): AbortSignal {
  const controllerRef = useRef<AbortController>(new AbortController());

  useEffect(() => {
    // Abort previous request
    if (controllerRef.current && !controllerRef.current.signal.aborted) {
      controllerRef.current.abort("New request initiated");
    }

    // Create new controller
    controllerRef.current = new AbortController();

    return () => {
      if (controllerRef.current && !controllerRef.current.signal.aborted) {
        controllerRef.current.abort("Component unmounted");
      }
    };
  }, dependencies);

  return controllerRef.current.signal;
}
