export type ApiCredentials = {
  authorization: string | null;
  apiKey: string | null;
};

const STORAGE_KEY = "theo.api.credentials";

// Encryption settings
// Retrieve encryption passphrase from runtime configuration (e.g., injected global variable)
const ENCRYPTION_PASSPHRASE: string = (window as any).THEO_API_ENCRYPTION_PASSPHRASE;
if (!ENCRYPTION_PASSPHRASE || typeof ENCRYPTION_PASSPHRASE !== "string" || ENCRYPTION_PASSPHRASE.length < 12) {
  throw new Error("Encryption passphrase not set. Please provide a strong passphrase via window.THEO_API_ENCRYPTION_PASSPHRASE.");
}

// Utility to derive or import a key for AES-GCM encryption
async function getAesKey(passphrase: string): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const keyMaterial = await window.crypto.subtle.importKey(
    "raw",
    enc.encode(passphrase),
    {name: "PBKDF2"},
    false,
    ["deriveKey"]
  );
  return await window.crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: enc.encode("theo-api-credentials"),
      iterations: 100000,
      hash: "SHA-256"
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

function bufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToBuffer(str: string): ArrayBuffer {
  const binary = atob(str);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

// Encrypts a JS object, returns base64 string containing IV and ciphertext
async function encryptData(data: object): Promise<string> {
  const json = JSON.stringify(data);
  const enc = new TextEncoder();
  const iv = window.crypto.getRandomValues(new Uint8Array(12));
  const key = await getAesKey(ENCRYPTION_PASSPHRASE);
  const ciphertext = await window.crypto.subtle.encrypt(
    { name: "AES-GCM", iv: iv },
    key,
    enc.encode(json)
  );
  // Store as base64 IV + ':' + base64 ciphertext
  return bufferToBase64(iv.buffer) + ":" + bufferToBase64(ciphertext);
}

// Decrypts a base64 string containing IV and ciphertext, returns JS object
async function decryptData(encrypted: string): Promise<object | null> {
  const [ivB64, ctB64] = encrypted.split(":");
  if (!ivB64 || !ctB64) return null;
  const iv = new Uint8Array(base64ToBuffer(ivB64));
  const ciphertext = base64ToBuffer(ctB64);
  const key = await getAesKey(ENCRYPTION_PASSPHRASE);
  try {
    const decrypted = await window.crypto.subtle.decrypt(
      { name: "AES-GCM", iv: iv },
      key,
      ciphertext
    );
    const dec = new TextDecoder();
    return JSON.parse(dec.decode(decrypted));
  } catch {
    return null;
  }
}

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

// Returns a promise for credentials; must be awaited by caller!
export async function readCredentialsFromStorage(): Promise<ApiCredentials | null> {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    // DECRYPT before parsing
    const parsed = await decryptData(raw) as Partial<ApiCredentials> | null;
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

// Returns a promise; must be awaited if caller cares about completion!
export async function writeCredentialsToStorage(credentials: ApiCredentials): Promise<void> {
  if (typeof window === "undefined") {
    return;
  }
  const normalized = normalizeCredentials(credentials);
  if (!normalized.authorization && !normalized.apiKey) {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }
  try {
    const encrypted = await encryptData(normalized);
    window.localStorage.setItem(STORAGE_KEY, encrypted);
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
