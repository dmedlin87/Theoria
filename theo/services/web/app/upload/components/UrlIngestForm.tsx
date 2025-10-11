"use client";

import { FormEvent, useRef, useState } from "react";

interface UrlIngestFormProps {
  onIngest: (url: string, sourceType: string, frontmatter: string) => Promise<void>;
  isSubmitting: boolean;
}

export default function UrlIngestForm({
  onIngest,
  isSubmitting,
}: UrlIngestFormProps): JSX.Element {
  const [url, setUrl] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [frontmatter, setFrontmatter] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    
    if (!url.trim()) {
      return;
    }

    await onIngest(url, sourceType, frontmatter);
    formRef.current?.reset();
    setUrl("");
    setSourceType("");
    setFrontmatter("");
  };

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="card">
      <h3 className="panel__title mb-3">Ingest URL</h3>
      <fieldset disabled={isSubmitting} className="stack-md" style={{ border: "none", padding: 0 }}>
        <div className="form-field">
          <label htmlFor="url-input" className="form-label">
            URL
          </label>
          <input
            id="url-input"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/article"
            className="form-input"
            required
          />
        </div>

        <div className="form-field">
          <label htmlFor="url-source-type" className="form-label">
            Source type
          </label>
          <select
            id="url-source-type"
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            className="form-select"
          >
            <option value="">Detect automatically</option>
            <option value="youtube">YouTube</option>
            <option value="html">Web page</option>
          </select>
          <p className="form-hint">
            Leave blank for automatic detection
          </p>
        </div>

        <div className="form-field">
          <label htmlFor="url-frontmatter" className="form-label">
            Frontmatter (JSON)
          </label>
          <textarea
            id="url-frontmatter"
            value={frontmatter}
            onChange={(e) => setFrontmatter(e.target.value)}
            placeholder='{"collection":"Patristics"}'
            className="form-textarea"
            rows={4}
          />
          <p className="form-hint">
            Optional metadata in JSON format
          </p>
        </div>

        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting ? <><span className="spinner" /> Submitting…</> : "Submit URL"}
        </button>
      </fieldset>
    </form>
  );
}
