import type { Metadata } from "next";

import ChatWorkspace from "./ChatWorkspace";
import { RESEARCH_MODES } from "../mode-config";

const MODE_PREVIEWS = Object.values(RESEARCH_MODES);

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
        <ul className="chat-mode-intro" aria-label="Reasoning modes">
          {MODE_PREVIEWS.map((mode) => (
            <li key={mode.id} className="chat-mode-intro__item">
              <span className="chat-mode-intro__icon" aria-hidden="true">
                {mode.icon}
              </span>
              <div>
                <p className="chat-mode-intro__label">{mode.label}</p>
                <p className="chat-mode-intro__tagline">{mode.tagline}</p>
              </div>
            </li>
          ))}
        </ul>
      </header>
      <ChatWorkspace />
    </section>
  );
}
