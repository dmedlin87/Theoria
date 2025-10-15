"use client";

import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { getApiBaseUrl } from "./api";
import {
  type ApiCredentials,
  STORAGE_KEY,
  buildAuthorizationHeaders,
  clearCredentialsStorage,
  getCachedCredentials,
  normalizeCredentials,
  readCredentialsFromStorage,
  resolveAuthHeaders,
  setCachedCredentials,
  writeCredentialsToStorage,
} from "./api-config-store";

type ApiConfigContextValue = {
  credentials: ApiCredentials;
  setCredentials: (credentials: ApiCredentials) => void;
  updateCredentials: (credentials: Partial<ApiCredentials>) => void;
  clearCredentials: () => void;
};

const ApiConfigContext = createContext<ApiConfigContextValue | undefined>(undefined);

function getDefaultCredentials(): ApiCredentials {
  const cached = getCachedCredentials();
  if (cached) {
    return cached;
  }
  const stored = typeof window !== "undefined" ? readCredentialsFromStorage() : null;
  if (stored) {
    setCachedCredentials(stored);
    return stored;
  }
  return { authorization: null, apiKey: null };
}

export function ApiConfigProvider({ children }: { children: ReactNode }): JSX.Element {
  const [credentials, setCredentialsState] = useState<ApiCredentials>(() => getDefaultCredentials());
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (!hasHydrated) {
      const stored = readCredentialsFromStorage();
      if (stored) {
        setCredentialsState(stored);
        setCachedCredentials(stored);
      }
      setHasHydrated(true);
    }

    const handleStorage = (event: StorageEvent) => {
      if (event.key && event.key !== STORAGE_KEY) {
        return;
      }
      const storedCredentials = readCredentialsFromStorage();
      if (storedCredentials) {
        setCredentialsState(storedCredentials);
        setCachedCredentials(storedCredentials);
      } else {
        setCredentialsState({ authorization: null, apiKey: null });
        setCachedCredentials(null);
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, [hasHydrated]);

  useEffect(() => {
    setCachedCredentials(credentials);
    if (!hasHydrated || typeof window === "undefined") {
      return;
    }
    writeCredentialsToStorage(credentials);
  }, [credentials, hasHydrated]);

  const setCredentials = useCallback((next: ApiCredentials) => {
    const normalized = normalizeCredentials(next);
    setCredentialsState(normalized);
  }, []);

  const updateCredentials = useCallback((updates: Partial<ApiCredentials>) => {
    setCredentialsState((current) => normalizeCredentials({ ...current, ...updates }));
  }, []);

  const clearCredentials = useCallback(() => {
    setCredentialsState({ authorization: null, apiKey: null });
    clearCredentialsStorage();
    setCachedCredentials(null);
  }, []);

  const value = useMemo<ApiConfigContextValue>(
    () => ({ credentials, setCredentials, updateCredentials, clearCredentials }),
    [credentials, setCredentials, updateCredentials, clearCredentials],
  );

  return <ApiConfigContext.Provider value={value}>{children}</ApiConfigContext.Provider>;
}

export function useApiConfig(): ApiConfigContextValue {
  const context = useContext(ApiConfigContext);
  if (!context) {
    throw new Error("useApiConfig must be used within an ApiConfigProvider");
  }
  return context;
}

export function useApiHeaders(): Record<string, string> {
  const { credentials } = useApiConfig();
  return useMemo(() => resolveAuthHeaders(credentials), [credentials]);
}

type ConnectionStatus =
  | { status: "idle"; message: string | null }
  | { status: "pending"; message: string | null }
  | { status: "success"; message: string | null }
  | { status: "error"; message: string };

const SUCCESS_MESSAGE = "Connection successful";

export function useApiConnectionTester() {
  const { credentials } = useApiConfig();
  const [state, setState] = useState<ConnectionStatus>({ status: "idle", message: null });

  const testConnection = useCallback(
    async (overrides?: Partial<ApiCredentials>) => {
      setState({ status: "pending", message: "Checking connection…" });
      try {
        const resolved = overrides
          ? normalizeCredentials({ ...credentials, ...overrides })
          : credentials;
        const headers = {
          Accept: "application/json",
          ...resolveAuthHeaders(resolved),
        };
        const response = await fetch(`${getApiBaseUrl().replace(/\/$/, "")}/health`, {
          method: "GET",
          headers,
          cache: "no-store",
        });
        if (!response.ok) {
          const bodyText = await response.text();
          const detail = bodyText.trim() ? `: ${bodyText.trim()}` : "";
          throw new Error(`Healthcheck failed (${response.status})${detail}`);
        }
        setState({ status: "success", message: SUCCESS_MESSAGE });
        return true;
      } catch (error) {
        const message =
          error instanceof Error && error.message
            ? error.message
            : "Connection test failed";
        setState({ status: "error", message });
        return false;
      }
    },
    [credentials],
  );

  const reset = useCallback(() => {
    setState({ status: "idle", message: null });
  }, []);

  return { state, testConnection, reset, headers: buildAuthorizationHeaders(credentials) };
}

export { type ApiCredentials };
