export type ApiErrorDetail = {
  message: string;
  code?: string | null;
  metadata?: Record<string, unknown> | null;
  traceId?: string | null;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly metadata?: Record<string, unknown> | null;
  readonly traceId?: string | null;

  constructor(
    status: number,
    detail: ApiErrorDetail,
    options?: { cause?: unknown },
  ) {
    super(detail.message, options);
    this.name = "ApiError";
    this.status = status;
    this.code = detail.code ?? undefined;
    this.metadata = detail.metadata ?? null;
    this.traceId = detail.traceId ?? null;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
