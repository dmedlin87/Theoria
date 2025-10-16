const AUTH_HEADER_NAMES = [
  "authorization",
  "x-api-key",
  "cookie",
] as const;

export function forwardAuthHeaders(source: Headers, target: Headers): void {
  for (const header of AUTH_HEADER_NAMES) {
    const value = source.get(header);
    if (value && value.trim()) {
      target.set(header, value);
    }
  }
}

export { AUTH_HEADER_NAMES };
