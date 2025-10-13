import "@testing-library/jest-dom";
import { ReadableStream } from "stream/web";
import { MessageChannel, MessagePort } from "worker_threads";
import { TextDecoder, TextEncoder } from "util";
import {
  fetch as undiciFetch,
  Headers as UndiciHeaders,
  Request as UndiciRequest,
  Response as UndiciResponse,
} from "undici";

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
