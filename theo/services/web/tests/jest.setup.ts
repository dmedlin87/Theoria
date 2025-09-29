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
if (!globalThis.fetch) {
  const { fetch } = require("undici");
  globalThis.fetch = fetch as typeof globalThis.fetch;
}
if (!globalThis.Headers) {
  const { Headers } = require("undici");
  globalThis.Headers = Headers as typeof globalThis.Headers;
}
if (!globalThis.Request) {
  const { Request } = require("undici");
  globalThis.Request = Request as unknown as typeof globalThis.Request;
}
if (!globalThis.Response) {
  const { Response } = require("undici");
  globalThis.Response = Response as unknown as typeof globalThis.Response;
}
