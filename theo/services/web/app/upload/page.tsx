"use client";

import { useState } from "react";

export default function UploadPage() {
  const [status, setStatus] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus("Queued (stub)");
  };

  return (
    <section>
      <h2>Upload</h2>
      <form onSubmit={handleSubmit}>
        <input type="file" name="file" />
        <button type="submit">Upload</button>
      </form>
      {status && <p>{status}</p>}
    </section>
  );
}
