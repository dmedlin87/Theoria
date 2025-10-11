const TRACE_HEADER_NAMES = ["traceparent", "x-trace-id", "x-request-id"] as const;

export function forwardTraceHeaders(source: Headers, target: Headers): void {
  for (const header of TRACE_HEADER_NAMES) {
    const value = source.get(header);
    if (value && value.trim()) {
      target.set(header, value.trim());
    }
  }
}

export { TRACE_HEADER_NAMES };
