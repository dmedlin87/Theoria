import { Buffer } from "node:buffer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type ConsoleErrorSpy = ReturnType<typeof vi.spyOn<typeof console, "error">>;

describe("api-config-store decryptData", () => {
  const originalCryptoDescriptor = Object.getOwnPropertyDescriptor(
    window,
    "crypto",
  );
  const originalPassphraseDescriptor = Object.getOwnPropertyDescriptor(
    window,
    "THEO_API_ENCRYPTION_PASSPHRASE",
  );
  let consoleErrorSpy: ConsoleErrorSpy;

  beforeEach(() => {
    vi.resetModules();
    window.localStorage.clear();
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();

    if (originalCryptoDescriptor) {
      Object.defineProperty(window, "crypto", originalCryptoDescriptor);
    } else {
      delete (window as typeof window & { crypto?: Crypto }).crypto;
    }

    if (originalPassphraseDescriptor) {
      Object.defineProperty(
        window,
        "THEO_API_ENCRYPTION_PASSPHRASE",
        originalPassphraseDescriptor,
      );
    } else {
      delete (window as typeof window & {
        THEO_API_ENCRYPTION_PASSPHRASE?: string;
      }).THEO_API_ENCRYPTION_PASSPHRASE;
    }

    vi.restoreAllMocks();
  });

  it("returns null when AES-GCM decryption fails", async () => {
    const decryptError = new Error("failed to decrypt");
    const mockCryptoKey = {} as CryptoKey;

    const importKey = vi.fn().mockResolvedValue({});
    const deriveKey = vi.fn().mockResolvedValue(mockCryptoKey);
    const decrypt = vi.fn().mockRejectedValue(decryptError);

    Object.defineProperty(window, "crypto", {
      value: {
        subtle: {
          importKey,
          deriveKey,
          decrypt,
        } as unknown as SubtleCrypto,
        getRandomValues: vi.fn((array: Uint8Array) => array),
      } as Crypto,
      configurable: true,
      writable: true,
    });

    Object.defineProperty(window, "THEO_API_ENCRYPTION_PASSPHRASE", {
      value: "0123456789ab",
      configurable: true,
      writable: true,
    });

    const { readCredentialsFromStorage, STORAGE_KEY } = await import(
      "../../app/lib/api-config-store"
    );

    const iv = Buffer.alloc(12).toString("base64");
    const ciphertext = Buffer.alloc(16).toString("base64");
    window.localStorage.setItem(STORAGE_KEY, `enc-v1:${iv}:${ciphertext}`);

    await expect(readCredentialsFromStorage()).resolves.toBeNull();
    expect(decrypt).toHaveBeenCalled();
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      "Failed to decrypt API credentials:",
      decryptError,
    );
  });
});
