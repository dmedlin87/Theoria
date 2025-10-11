"use client";

import type { VerseFormState } from "./workflow-hooks";

interface VerseWorkflowFormProps {
  form: VerseFormState;
  onChange: (updates: Partial<VerseFormState>) => void;
  onCommand?: (input: string) => boolean;
}

export default function VerseWorkflowForm({
  form,
  onChange,
  onCommand,
}: VerseWorkflowFormProps): JSX.Element {
  const handleQuestionChange = (value: string) => {
    if (onCommand && onCommand(value)) {
      return;
    }
    onChange({ question: value });
  };

  return (
    <div className="stack-md">
      {!form.useAdvanced ? (
        <div className="form-field">
          <label htmlFor="verse-passage" className="form-label">
            Passage
          </label>
          <input
            id="verse-passage"
            type="text"
            value={form.passage}
            onChange={(e) => onChange({ passage: e.target.value })}
            placeholder="e.g., John 1:1-5"
            className="form-input"
            required
          />
          <p className="form-hint">
            Enter a readable passage reference. We'll convert it to OSIS for you.
          </p>
        </div>
      ) : (
        <div className="form-field">
          <label htmlFor="verse-osis" className="form-label">
            OSIS Reference
          </label>
          <input
            id="verse-osis"
            type="text"
            value={form.osis}
            onChange={(e) => onChange({ osis: e.target.value })}
            placeholder="e.g., John.1.1-John.1.5"
            className="form-input"
            required
          />
          <p className="form-hint">
            Enter a precise OSIS reference for advanced querying.
          </p>
        </div>
      )}

      <div className="form-field">
        <label htmlFor="verse-question" className="form-label">
          Question
        </label>
        <textarea
          id="verse-question"
          value={form.question}
          onChange={(e) => handleQuestionChange(e.target.value)}
          placeholder="What would you like to know about this passage?"
          className="form-textarea"
          rows={3}
          required
        />
        <p className="form-hint">
          Tip: Use <code>/research</code> or <code>/r</code> to open research panels.
        </p>
      </div>

      <div className="cluster-sm">
        <label className="cluster-sm" style={{ cursor: "pointer", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={form.useAdvanced}
            onChange={(e) => onChange({ useAdvanced: e.target.checked })}
          />
          <span className="text-sm">Use advanced OSIS mode</span>
        </label>
      </div>
    </div>
  );
}
