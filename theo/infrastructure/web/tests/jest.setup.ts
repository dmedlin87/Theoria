import "@testing-library/jest-dom";
import { ReadableStream } from "stream/web";
import { MessageChannel, MessagePort } from "worker_threads";
import { TextDecoder, TextEncoder } from "util";

if (!globalThis.TextEncoder) {
  globalThis.TextEncoder = TextEncoder as typeof globalThis.TextEncoder;
}
if (!globalThis.TextDecoder) {
  globalThis.TextDecoder = TextDecoder as typeof globalThis.TextDecoder;
}
if (!globalThis.ReadableStream) {
  globalThis.ReadableStream = ReadableStream as typeof globalThis.ReadableStream;
}
if (!globalThis.MessageChannel) {
  globalThis.MessageChannel = MessageChannel as unknown as typeof globalThis.MessageChannel;
}
if (!globalThis.MessagePort) {
  globalThis.MessagePort = MessagePort as unknown as typeof globalThis.MessagePort;
}
if (!globalThis.fetch || !globalThis.Headers || !globalThis.Request || !globalThis.Response) {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { fetch: undiciFetch, Headers: UndiciHeaders, Request: UndiciRequest, Response: UndiciResponse } = require("undici");
  if (!globalThis.fetch) {
    globalThis.fetch = undiciFetch as typeof globalThis.fetch;
  }
  if (!globalThis.Headers) {
    globalThis.Headers = UndiciHeaders as typeof globalThis.Headers;
  }
  if (!globalThis.Request) {
    globalThis.Request = UndiciRequest as unknown as typeof globalThis.Request;
  }
  if (!globalThis.Response) {
    globalThis.Response = UndiciResponse as unknown as typeof globalThis.Response;
  }
}

if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserver {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).ResizeObserver = ResizeObserver;
}
