import { useEffect, useRef, useState } from "react";

/**
 * Debounce a value to reduce unnecessary re-renders and API calls
 * 
 * @param value - The value to debounce
 * @param delay - Delay in milliseconds (default: 300ms)
 * @returns Debounced value
 * 
 * @example
 * const SearchInput = () => {
 *   const [query, setQuery] = useState("");
 *   const debouncedQuery = useDebounce(query, 500);
 *   
 *   useEffect(() => {
 *     if (debouncedQuery) {
 *       performSearch(debouncedQuery);
 *     }
 *   }, [debouncedQuery]);
 * 
 *   return <input value={query} onChange={(e) => setQuery(e.target.value)} />;
 * };
 */
export function useDebounce<T>(value: T, delay = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Hook for debouncing callback functions
 * Useful for expensive operations that shouldn't run on every render
 * 
 * @param callback - The function to debounce
 * @param delay - Delay in milliseconds (default: 300ms)
 * @returns Debounced callback function
 * 
 * @example
 * const handleSearch = useDebouncedCallback(
 *   (query: string) => {
 *     api.search(query);
 *   },
 *   500
 * );
 */
export function useDebouncedCallback<T extends (...args: Parameters<T>) => void>(
  callback: T,
  delay = 300
): (...args: Parameters<T>) => void {
  // Use useRef instead of useState to avoid re-renders
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const callbackRef = useRef(callback);

  // Keep callback reference up to date
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (...args: Parameters<T>) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      callbackRef.current(...args);
    }, delay);
  };
}

/**
 * Hook for throttling callback functions
 * Ensures callback executes at most once per delay period
 * 
 * @param callback - The function to throttle
 * @param delay - Minimum time between calls in milliseconds (default: 300ms)
 * @returns Throttled callback function
 * 
 * @example
 * const handleScroll = useThrottledCallback(
 *   () => {
 *     console.log('Scroll position:', window.scrollY);
 *   },
 *   100
 * );
 */
export function useThrottledCallback<T extends (...args: Parameters<T>) => void>(
  callback: T,
  delay = 300
): (...args: Parameters<T>) => void {
  const lastRunRef = useRef<number>(0);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const callbackRef = useRef(callback);

  // Keep callback reference up to date
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (...args: Parameters<T>) => {
    const now = Date.now();
    const timeSinceLastRun = now - lastRunRef.current;

    // If enough time has passed, execute immediately
    if (timeSinceLastRun >= delay) {
      lastRunRef.current = now;
      callbackRef.current(...args);
    } else {
      // Otherwise, schedule for later
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      const remainingTime = delay - timeSinceLastRun;
      timeoutRef.current = setTimeout(() => {
        lastRunRef.current = Date.now();
        callbackRef.current(...args);
      }, remainingTime);
    }
  };
}
