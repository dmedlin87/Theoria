"use client";

import type { ReactNode } from "react";

import ChatWorkspace from "./ChatWorkspace";
import type { ChatWorkflowClient, ChatWorkflowResult, ChatWorkflowStreamEvent } from "../lib/api-client";
import { DEFAULT_MODE_ID } from "../mode-config";
import { ModeProvider } from "../mode-context";

type StoryMeta = { title: string; component: typeof ChatWorkspace };

const meta = { title: "App/ChatWorkspace", component: ChatWorkspace } satisfies StoryMeta;
export default meta;

function StoryShell({ children }: { children: ReactNode }): JSX.Element {
  return <ModeProvider initialMode={DEFAULT_MODE_ID}>{children}</ModeProvider>;
}

const sampleAnswer = {
  summary: "John situates the Logos alongside the Genesis creation narrative, emphasising divine pre-existence.",
  citations: [
    {
      index: 0,
      osis: "John.1.1",
      anchor: "John 1:1",
      passage_id: "passage-1",
      document_id: "doc-1",
      document_title: "Gospel of John",
      snippet: "In the beginning was the Word, and the Word was with God.",
      source_url: null,
    },
  ],
  model_name: null,
  model_output: null,
  guardrail_profile: null,
} satisfies import("../copilot/components/types").RAGAnswer;

function createStoryClient(
  events: ChatWorkflowStreamEvent[],
  result: ChatWorkflowResult,
): ChatWorkflowClient {
  return {
    async runChatWorkflow(_payload, options) {
      events.forEach((event) => options?.onEvent?.(event));
      return result;
    },
    async getChatSession() {
      return null;
    },
  };
}

export function Loading(): JSX.Element {
  const client: ChatWorkflowClient = {
    async runChatWorkflow(_payload, _options) {
      return new Promise(() => {
        // Intentionally unresolved to showcase loading state.
      });
    },
    async getChatSession() {
      return null;
    },
  };
  return (
    <StoryShell>
      <ChatWorkspace client={client} initialPrompt="How does John 1 mirror Genesis 1?" autoSubmit />
    </StoryShell>
  );
}

export function Success(): JSX.Element {
  const client = createStoryClient(
    [
      { type: "answer_fragment", content: "The Logos language evokes creation motifs." },
      { type: "complete", response: { sessionId: "story-session", answer: sampleAnswer } },
    ],
    { kind: "success", sessionId: "story-session", answer: sampleAnswer },
  );
  return (
    <StoryShell>
      <ChatWorkspace client={client} initialPrompt="Summarise John 1:1" autoSubmit />
    </StoryShell>
  );
}

export function Guardrail(): JSX.Element {
  const client = createStoryClient(
    [{ type: "guardrail_violation", message: "This request was blocked by policy safeguards.", traceId: "guard-42" }],
    { kind: "guardrail", message: "This request was blocked by policy safeguards.", traceId: "guard-42" },
  );
  return (
    <StoryShell>
      <ChatWorkspace client={client} initialPrompt="List controversial conspiracies" autoSubmit />
    </StoryShell>
  );
}
