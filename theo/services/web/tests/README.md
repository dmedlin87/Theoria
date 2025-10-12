# Chat Workspace Test Scenarios

This directory now exercises the chat workspace across unit-style hooks and full component integrations.

## Vitest hook coverage

The Vitest suite (`npm run test:vitest`) validates the behaviour of the session management hooks in
[`app/chat/useSessionRestoration.ts`](../app/chat/useSessionRestoration.ts):

- Restores a saved session and rebuilds the transcript when `localStorage` contains a session id.
- Retries with exponential backoff when the API rejects and `canRetry` remains true.
- Clears corrupted sessions and stops retrying when invalid data is returned.
- Persists and clears the stored session id as the active session changes.

## Jest component coverage

Running `npm run test` covers the end-to-end chat workflow in
[`tests/app/chat/chat-workspace.test.tsx`](./app/chat/chat-workspace.test.tsx):

- Streams partial answer fragments, renders guardrail callouts, and persists session ids after success.
- Exercises guardrail violation events as well as API validation errors to ensure actionable messaging and fallback suggestions.
- Confirms network failures fall back to error callouts instead of leaving orphaned transcript rows.
- Verifies feedback buttons handle both success and failure paths without getting stuck disabled.
- Validates "Reset session" and "Fork conversation" behaviours, including clearing the shared `localStorage` entry to keep multiple tabs in sync.

Run both suites after changes to confirm resiliency across mocked API responses:

```sh
cd theo/services/web
npm run test
npm run test:vitest
```
