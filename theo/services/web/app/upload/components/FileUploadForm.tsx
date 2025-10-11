"use client";

import { FormEvent, useRef, useState } from "react";

interface FileUploadFormProps {
  onUpload: (file: File, frontmatter: string) => Promise<void>;
  isUploading: boolean;
}

export default function FileUploadForm({
  onUpload,
  isUploading,
}: FileUploadFormProps): JSX.Element {
  const [frontmatter, setFrontmatter] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const fileInput = event.currentTarget.elements.namedItem("file") as HTMLInputElement | null;
    const file = fileInput?.files?.[0];

    if (!file) {
      return;
    }

    await onUpload(file, frontmatter);
    formRef.current?.reset();
    setFrontmatter("");
  };

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="card">
      <h3 className="panel__title mb-3">Upload File</h3>
      <fieldset disabled={isUploading} className="stack-md" style={{ border: "none", padding: 0 }}>
        <div className="form-field">
          <label htmlFor="file-upload" className="form-label">
            Source file
          </label>
          <input
            id="file-upload"
            type="file"
            name="file"
            required
            className="form-input"
          />
        </div>

        <div className="form-field">
          <label htmlFor="file-frontmatter" className="form-label">
            Frontmatter (JSON)
          </label>
          <textarea
            id="file-frontmatter"
            name="frontmatter"
            value={frontmatter}
            onChange={(e) => setFrontmatter(e.target.value)}
            placeholder='{"collection":"Gospels","author":"Unknown"}'
            className="form-textarea"
            rows={4}
          />
          <p className="form-hint">
            Optional metadata in JSON format
          </p>
        </div>

        <button type="submit" className="btn btn-primary" disabled={isUploading}>
          {isUploading ? <><span className="spinner" /> Uploading…</> : "Upload file"}
        </button>
      </fieldset>
    </form>
  );
}
