import { getApiBaseUrl } from "./api";
import { resolveAuthHeaders } from "./api-config-store";

export class TheoApiError extends Error {
  readonly status: number;
  readonly payload: unknown;
  readonly url: string;
  readonly timestamp: number;

  constructor(message: string, status: number, url: string, payload?: unknown) {
    super(message);
    this.name = "TheoApiError";
    this.status = status;
    this.url = url;
    this.payload = payload;
    this.timestamp = Date.now();
  }

  /**
   * Check if the error is retryable based on status code
   */
  get isRetryable(): boolean {
    // Retry on network errors, timeouts, and server errors
    return this.status >= 500 || this.status === 408 || this.status === 429;
  }

  /**
   * Check if the error is a client error (4xx)
   */
  get isClientError(): boolean {
    return this.status >= 400 && this.status < 500;
  }
}

export class NetworkError extends Error {
  readonly originalError: unknown;

  constructor(message: string, originalError?: unknown) {
    super(message);
    this.name = "NetworkError";
    this.originalError = originalError;
  }
}

export function buildErrorMessage(status: number, body: string | null): string {
  if (body) {
    return body;
  }
  return `Request failed with status ${status}`;
}

export type RequestOptions = RequestInit & { 
  parseJson?: boolean;
  /**
   * Number of retry attempts for failed requests (default: 0)
   */
  retries?: number;
  /**
   * Delay between retries in milliseconds (default: 1000)
   */
  retryDelay?: number;
  /**
   * AbortSignal to cancel the request
   */
  signal?: AbortSignal;
};

async function handleResponse(
  response: Response,
  parseJson: false,
): Promise<void>;
async function handleResponse<T>(
  response: Response,
  parseJson: true,
): Promise<T>;
async function handleResponse<T>(response: Response, parseJson: boolean): Promise<T | void>;
async function handleResponse<T>(response: Response, parseJson: boolean): Promise<T | void> {
  if (!response.ok) {
    const bodyText = await response.text();
    const contentType = response.headers.get("content-type") ?? "";
    let payload: unknown = bodyText || null;
    if (contentType.includes("application/json") && bodyText) {
      try {
        payload = JSON.parse(bodyText) as unknown;
      } catch (parseError) {
        // Only log in development to avoid console noise in production
        if (process.env.NODE_ENV === "development") {
          console.warn("Failed to parse error payload:", parseError);
        }
        payload = bodyText;
      }
    }
    let message = buildErrorMessage(response.status, bodyText || null);
    if (payload && typeof payload === "object") {
      const detail = (payload as Record<string, unknown>).detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail && typeof detail === "object") {
        const nested = (detail as Record<string, unknown>).message;
        if (typeof nested === "string") {
          message = nested;
        }
      }
    }
    
    const error = new TheoApiError(message, response.status, response.url, payload ?? bodyText);
    
    // Log API errors in development for debugging
    if (process.env.NODE_ENV === "development") {
      console.error(`[API Error] ${response.status} ${response.url}:`, {
        message,
        payload,
        status: response.status,
      });
    }
    
    throw error;
  }
  if (!parseJson) {
    return;
  }
  if (response.status === 204) {
    return;
  }
  const data = (await response.json()) as unknown;
  return data as T;
}

export type HttpClient = {
  baseUrl: string;
  request: {
    (path: string, init: RequestOptions & { parseJson: false }): Promise<void>;
    <T>(path: string, init?: RequestOptions & { parseJson?: true }): Promise<T>;
  };
};

export function createHttpClient(baseUrl?: string): HttpClient {
  const resolved = (baseUrl ?? getApiBaseUrl()).replace(/\/$/, "");

  async function request(path: string, init: RequestOptions & { parseJson: false }): Promise<void>;
  async function request<T>(
    path: string,
    init?: RequestOptions & { parseJson?: true },
  ): Promise<T>;
  async function request<T>(path: string, init?: RequestOptions): Promise<T | void> {
    const { 
      parseJson = true, 
      headers, 
      retries = 0, 
      retryDelay = 1000,
      signal,
      ...rest 
    } = init ?? {};
    const defaultHeaders: HeadersInit =
      rest.body === undefined ? {} : { "Content-Type": "application/json" };

    let lastError: Error | null = null;
    const maxAttempts = retries + 1;

    const authHeaders = resolveAuthHeaders();

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        // Check if request was cancelled
        if (signal?.aborted) {
          throw new NetworkError("Request was cancelled", signal.reason);
        }

        const response = await fetch(`${resolved}${path}`, {
          cache: "no-store",
          headers: {
            ...authHeaders,
            ...defaultHeaders,
            ...(headers ?? {}),
          },
          ...(signal ? { signal } : {}),
          ...rest,
        });
        
        if (parseJson) {
          return handleResponse<T>(response, true);
        }
        return handleResponse(response, false);
      } catch (error) {
        lastError = error as Error;

        // Don't retry if cancelled or if it's the last attempt
        if (signal?.aborted || attempt === maxAttempts - 1) {
          throw error;
        }

        // Only retry on network errors or retryable API errors
        const shouldRetry = 
          error instanceof NetworkError ||
          (error instanceof TheoApiError && error.isRetryable);

        if (!shouldRetry) {
          throw error;
        }

        // Exponential backoff with jitter
        const backoffDelay = retryDelay * Math.pow(2, attempt) + Math.random() * 500;
        
        if (process.env.NODE_ENV === "development") {
          console.warn(
            `[HTTP Retry] Attempt ${attempt + 1}/${maxAttempts} failed, retrying in ${Math.round(backoffDelay)}ms`,
            error
          );
        }

        await new Promise((resolve) => setTimeout(resolve, backoffDelay));
      }
    }

    // Should never reach here, but TypeScript needs it
    throw lastError ?? new NetworkError("Request failed");
  }

  return { baseUrl: resolved, request };
}

export { handleResponse };
