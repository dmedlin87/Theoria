/**
 * Cache utilities for optimizing API requests
 * Provides configurable caching strategies for fetch requests
 */

export type CacheStrategy = 
  | "no-cache"      // Always fetch fresh data
  | "default"       // Use browser's default caching
  | "force-cache"   // Use cached data if available
  | "only-if-cached"; // Only use cached data, fail if not cached

export interface CacheConfig {
  /**
   * Cache strategy for the request
   * @default "default"
   */
  strategy?: CacheStrategy;
  
  /**
   * Custom cache time in seconds
   * Only used with "force-cache" strategy
   */
  revalidate?: number;
  
  /**
   * Tags for Next.js cache invalidation
   */
  tags?: string[];
}

/**
 * Build fetch options with optimized caching for different data types
 */
export function buildCacheOptions(config: CacheConfig = {}): RequestInit {
  const { strategy = "default", revalidate, tags } = config;
  
  const options: RequestInit = {};
  
  // Only set cache if not default to avoid undefined assignment
  if (strategy !== "default") {
    options.cache = strategy;
  }
  
  // Next.js-specific caching options
  if (revalidate !== undefined) {
    (options as Record<string, unknown>).next = {
      revalidate,
      tags: tags ?? [],
    };
  }
  
  return options;
}

/**
 * Predefined cache configurations for common use cases
 */
export const CachePresets = {
  /**
   * For static content that rarely changes (docs, metadata)
   */
  static: (): CacheConfig => ({
    strategy: "force-cache",
    revalidate: 3600, // 1 hour
  }),
  
  /**
   * For search results and dynamic content
   */
  dynamic: (): CacheConfig => ({
    strategy: "no-cache",
  }),
  
  /**
   * For user-specific data that changes frequently
   */
  realtime: (): CacheConfig => ({
    strategy: "no-cache",
  }),
  
  /**
   * For content that updates periodically (digests, summaries)
   */
  periodic: (minutes = 5): CacheConfig => ({
    strategy: "force-cache",
    revalidate: minutes * 60,
  }),
} as const;

/**
 * Simple in-memory cache for client-side data
 * Useful for caching expensive computations
 */
export class ClientCache<T> {
  private cache = new Map<string, { data: T; timestamp: number }>();
  private ttl: number;
  
  constructor(ttlSeconds = 300) {
    this.ttl = ttlSeconds * 1000;
  }
  
  get(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;
    
    const isExpired = Date.now() - entry.timestamp > this.ttl;
    if (isExpired) {
      this.cache.delete(key);
      return null;
    }
    
    return entry.data;
  }
  
  set(key: string, data: T): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
    });
  }
  
  clear(): void {
    this.cache.clear();
  }
  
  has(key: string): boolean {
    return this.get(key) !== null;
  }
}
