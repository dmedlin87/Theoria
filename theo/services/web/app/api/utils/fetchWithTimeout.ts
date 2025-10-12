export class TimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`Request timeout after ${timeoutMs}ms`);
    this.name = "TimeoutError";
  }
}

export class NetworkError extends Error {
  public override readonly cause?: unknown;

  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = "NetworkError";
    this.cause = cause;
  }
}

/**
 * Fetches with a configurable timeout to prevent hung requests.
 * @param url The URL to fetch
 * @param options Standard fetch options
 * @param timeoutMs Timeout in milliseconds (default: 30000)
 * @returns Promise that resolves to Response or rejects on timeout/error
 */
export async function fetchWithTimeout(
  url: string | URL,
  options?: RequestInit,
  timeoutMs: number = 30000,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    
    if (error instanceof Error && error.name === "AbortError") {
      throw new TimeoutError(timeoutMs);
    }
    
    // Network errors (ECONNREFUSED, ENOTFOUND, etc.)
    if (error instanceof TypeError) {
      throw new NetworkError("Failed to connect to backend service", error);
    }
    
    throw error;
  }
}
