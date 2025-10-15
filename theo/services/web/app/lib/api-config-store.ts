export type ApiCredentials = {
  authorization: string | null;
  apiKey: string | null;
};

const STORAGE_KEY = "theo.api.credentials";

let cachedCredentials: ApiCredentials | null = null;

function normalizeValue(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function normalizeCredentials(
  credentials: Partial<ApiCredentials> | ApiCredentials | null | undefined,
): ApiCredentials {
  return {
    authorization: normalizeValue(credentials?.authorization),
    apiKey: normalizeValue(credentials?.apiKey),
  };
}

export function getCachedCredentials(): ApiCredentials | null {
  return cachedCredentials;
}

export function setCachedCredentials(credentials: ApiCredentials | null): void {
  cachedCredentials = credentials ? normalizeCredentials(credentials) : null;
}

export function readCredentialsFromStorage(): ApiCredentials | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<ApiCredentials> | null;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    const normalized = normalizeCredentials(parsed);
    if (!normalized.authorization && !normalized.apiKey) {
      return null;
    }
    return normalized;
  } catch {
    return null;
  }
}

export function writeCredentialsToStorage(credentials: ApiCredentials): void {
  if (typeof window === "undefined") {
    return;
  }
  const normalized = normalizeCredentials(credentials);
  if (!normalized.authorization && !normalized.apiKey) {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    // Ignore storage errors (private browsing, quota issues, etc.)
  }
}

export function clearCredentialsStorage(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage errors
  }
}

function pickEnvValue(names: string[]): string | null {
  for (const name of names) {
    const value = process.env[name];
    if (typeof value === "string") {
      const normalized = value.trim();
      if (normalized) {
        return normalized;
      }
    }
  }
  return null;
}

const PUBLIC_AUTHORIZATION_ENV_VARS = ["NEXT_PUBLIC_API_AUTHORIZATION"];
const SERVER_AUTHORIZATION_ENV_VARS = [
  "API_AUTHORIZATION",
  "THEO_API_AUTHORIZATION",
];
const PUBLIC_API_KEY_ENV_VARS = ["NEXT_PUBLIC_API_KEY"];
const SERVER_API_KEY_ENV_VARS = ["API_KEY", "THEO_SEARCH_API_KEY"];

export function getEnvCredentials(): ApiCredentials {
  const isBrowser = typeof window !== "undefined";
  const authorizationNames = isBrowser
    ? PUBLIC_AUTHORIZATION_ENV_VARS
    : [...PUBLIC_AUTHORIZATION_ENV_VARS, ...SERVER_AUTHORIZATION_ENV_VARS];
  const apiKeyNames = isBrowser
    ? PUBLIC_API_KEY_ENV_VARS
    : [...PUBLIC_API_KEY_ENV_VARS, ...SERVER_API_KEY_ENV_VARS];

  return {
    authorization: pickEnvValue(authorizationNames),
    apiKey: pickEnvValue(apiKeyNames),
  };
}

export function buildAuthorizationHeaders(
  credentials: ApiCredentials | null | undefined,
): Record<string, string> {
  const normalized = normalizeCredentials(credentials ?? null);
  if (normalized.authorization) {
    return { Authorization: normalized.authorization };
  }
  if (normalized.apiKey) {
    if (/^Bearer\s+/i.test(normalized.apiKey)) {
      return { Authorization: normalized.apiKey };
    }
    return { "X-API-Key": normalized.apiKey };
  }
  return {};
}

export function resolveAuthHeaders(
  preferred?: ApiCredentials | null,
): Record<string, string> {
  const attempts: Array<ApiCredentials | null> = [];
  if (preferred) {
    attempts.push(normalizeCredentials(preferred));
  }
  const cached = getCachedCredentials();
  if (cached) {
    attempts.push(cached);
  }
  attempts.push(getEnvCredentials());

  for (const candidate of attempts) {
    if (!candidate) {
      continue;
    }
    const headers = buildAuthorizationHeaders(candidate);
    if (Object.keys(headers).length > 0) {
      return headers;
    }
  }
  return {};
}

export { STORAGE_KEY };
