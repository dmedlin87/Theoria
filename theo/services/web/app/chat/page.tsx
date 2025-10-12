import type { Metadata } from "next";

import ChatWorkspace from "./ChatWorkspace";

export const metadata: Metadata = {
  title: "Theoria — Chat",
  description: "Research chat with grounded theological citations.",
};

export default function ChatPage(): JSX.Element {
  return (
    <section className="chat-page" aria-labelledby="chat-title">
      <header className="page-header">
        <h1 id="chat-title">Chat</h1>
        <p>
          Investigate questions with stance-aware answers grounded in scripture, commentary, and your corpus.
        </p>
      </header>
      <ChatWorkspace />
    </section>
  );
}
