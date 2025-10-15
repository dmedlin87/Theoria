import { useEffect, useRef } from "react";

/**
 * Performance metrics interface
 */
export interface PerformanceMetrics {
  componentName: string;
  renderCount: number;
  averageRenderTime: number;
  lastRenderTime: number;
  mountTime: number;
}

/**
 * Hook to monitor component render performance
 * Only active in development mode
 * 
 * @param componentName - Name of the component to monitor
 * @param logThreshold - Minimum render time (ms) to log (default: 16ms ~60fps)
 * 
 * @example
 * function MyComponent() {
 *   usePerformanceMonitor('MyComponent', 50);
 *   // ... rest of component
 * }
 */
export function usePerformanceMonitor(
  componentName: string,
  logThreshold = 16
): void {
  const renderCount = useRef(0);
  const renderTimes = useRef<number[]>([]);
  const renderStartRef = useRef<number>(0);
  const mountTime = useRef<number | null>(null);

  // Increment render count
  renderCount.current += 1;

  // Track render performance in layout effect (before paint)
  useEffect(() => {
    // Capture start time at the beginning of this effect
    const endTime = performance.now();
    const renderTime = endTime - renderStartRef.current;
    
    renderTimes.current.push(renderTime);

    // Keep only last 100 render times
    if (renderTimes.current.length > 100) {
      renderTimes.current.shift();
    }

    // Log slow renders in development
    if (process.env.NODE_ENV === "development" && renderTime > logThreshold) {
      const avgTime = renderTimes.current.reduce((a, b) => a + b, 0) / renderTimes.current.length;
      console.warn(
        `[Performance] ${componentName} render #${renderCount.current} took ${renderTime.toFixed(2)}ms (avg: ${avgTime.toFixed(2)}ms)`
      );
    }
    
    // Set start time for next render
    renderStartRef.current = performance.now();
  });

  // Track mount time
  useEffect(() => {
    mountTime.current = performance.now();
    renderStartRef.current = performance.now();
    
    if (process.env.NODE_ENV === "development") {
      console.log(`[Performance] ${componentName} mounted`);
    }

    return () => {
      if (process.env.NODE_ENV === "development" && mountTime.current) {
        const lifetimeMs = performance.now() - mountTime.current;
        console.log(
          `[Performance] ${componentName} unmounted after ${(lifetimeMs / 1000).toFixed(2)}s (${renderCount.current} renders)`
        );
      }
    };
  }, [componentName]);
}

/**
 * Hook to track and log expensive operations
 * 
 * @example
 * const trackOperation = useOperationTracker();
 * 
 * const handleClick = () => {
 *   trackOperation('data-processing', () => {
 *     // expensive operation
 *   });
 * };
 */
export function useOperationTracker(): (
  operationName: string,
  operation: () => void
) => void {
  return (operationName: string, operation: () => void) => {
    const start = performance.now();
    
    try {
      operation();
    } finally {
      const duration = performance.now() - start;
      
      if (process.env.NODE_ENV === "development") {
        console.log(`[Operation] ${operationName} took ${duration.toFixed(2)}ms`);
      }
    }
  };
}

/**
 * Hook to detect memory leaks by tracking component instances
 * Logs warning if component instances exceed threshold
 * 
 * @param componentName - Name of the component
 * @param maxInstances - Maximum expected instances (default: 10)
 */
export function useMemoryLeakDetector(
  componentName: string,
  maxInstances = 10
): void {
  useEffect(() => {
    if (process.env.NODE_ENV !== "development") {
      return;
    }

    // Track component instances in global registry
    type GlobalWithRegistry = typeof globalThis & {
      __componentRegistry?: Map<string, number>;
    };
    const global = globalThis as GlobalWithRegistry;
    
    if (!global.__componentRegistry) {
      global.__componentRegistry = new Map();
    }

    const componentRegistry = global.__componentRegistry;
    const currentCount = componentRegistry.get(componentName) ?? 0;
    const newCount = currentCount + 1;
    
    componentRegistry.set(componentName, newCount);

    if (newCount > maxInstances) {
      console.warn(
        `[Memory Leak Warning] ${componentName} has ${newCount} active instances (max: ${maxInstances}). ` +
        `This may indicate a memory leak.`
      );
    }

    return () => {
      const count = componentRegistry.get(componentName) ?? 0;
      if (count > 0) {
        componentRegistry.set(componentName, count - 1);
      }
    };
  }, [componentName, maxInstances]);
}
