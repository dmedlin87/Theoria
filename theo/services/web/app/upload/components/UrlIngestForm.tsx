"use client";

import { FormEvent, useRef, useState } from "react";

import { HelpTooltip, TooltipList, TooltipParagraph } from "../../components/help/HelpTooltip";

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
    <form ref={formRef} onSubmit={handleSubmit} className="card fade-in">
      <h3 className="panel__title mb-3">Ingest URL</h3>
      <fieldset disabled={isSubmitting} className="stack-md form-fieldset">
        <div className="form-field">
          <label htmlFor="url-input" className="form-label">
            URL
            <HelpTooltip
              label="Supported URLs"
              description={
                <>
                  <TooltipParagraph>
                    Provide a public HTTP(S) URL. Private intranet addresses and unsupported protocols are rejected.
                  </TooltipParagraph>
                  <TooltipParagraph>
                    For PDF downloads, use the direct file link when possible so ingestion retains the original filename.
                  </TooltipParagraph>
                </>
              }
            />
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
            <HelpTooltip
              label="Override detection"
              description={
                <>
                  <TooltipParagraph>
                    Choose this when automatic detection picks the wrong parser. Options map to the ingest pipeline:
                  </TooltipParagraph>
                  <TooltipList items={["YouTube – Captures transcripts and metadata", "Web page – Scrapes readable HTML"]} />
                  <TooltipParagraph>
                    Leave on automatic detection for most URLs.
                  </TooltipParagraph>
                </>
              }
            />
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
            <HelpTooltip
              label="Frontmatter format"
              description={
                <>
                  <TooltipParagraph>
                    Attach optional JSON metadata. Keep values simple strings or arrays to ensure ingest succeeds.
                  </TooltipParagraph>
                  <TooltipList items={["collection", "author", "tags", "language"]} />
                  <TooltipParagraph>
                    If left blank, metadata is inferred from the source when available.
                  </TooltipParagraph>
                </>
              }
            />
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

        <button type="submit" className="btn btn-primary scale-in" disabled={isSubmitting}>
          {isSubmitting ? <><span className="spinner spin" /> Submitting…</> : "Submit URL"}
        </button>
      </fieldset>
    </form>
  );
}
