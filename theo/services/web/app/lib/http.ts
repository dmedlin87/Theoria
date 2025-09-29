import { getApiBaseUrl } from "./api";

export class TheoApiError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = "TheoApiError";
    this.status = status;
    this.payload = payload;
  }
}

export function buildErrorMessage(status: number, body: string | null): string {
  if (body) {
    return body;
  }
  return `Request failed with status ${status}`;
}

export type RequestOptions = RequestInit & { parseJson?: boolean };

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
        console.warn("Failed to parse error payload", parseError);
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
    throw new TheoApiError(message, response.status, payload ?? bodyText);
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
    const { parseJson = true, headers, ...rest } = init ?? {};
    const response = await fetch(`${resolved}${path}`, {
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(headers ?? {}),
      },
      ...rest,
    });
    if (parseJson) {
      return handleResponse<T>(response, true);
    }
    return handleResponse(response, false);
  }

  return { baseUrl: resolved, request };
}

export { handleResponse };
