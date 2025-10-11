'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const FORMAT_LABELS: Record<string, string> = {
  markdown: 'Markdown (.md)',
  json: 'JSON (.json)',
  ndjson: 'NDJSON (.ndjson)',
  csv: 'CSV (.csv)',
};

function parseFilename(disposition: string | null, fallback: string): string {
  if (!disposition) {
    return fallback;
  }
  const match = /filename\s*=\s*"?([^";]+)"?/i.exec(disposition);
  if (match && match[1]) {
    return match[1];
  }
  return fallback;
}

function normaliseDocumentIds(input: string): string[] {
  return input
    .split(/\r?\n|,/)
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
}

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException) {
    return error.name === 'AbortError';
  }
  if (error instanceof Error) {
    return error.name === 'AbortError';
  }
  return false;
}

export default function CitationExportPage(): JSX.Element {
  const [style, setStyle] = useState<string>('apa');
  const [downloadFormat, setDownloadFormat] = useState<string>('markdown');
  const [documentIds, setDocumentIds] = useState<string>('');
  const [osis, setOsis] = useState<string>('');
  const [collection, setCollection] = useState<string>('');
  const [author, setAuthor] = useState<string>('');
  const [sourceType, setSourceType] = useState<string>('');
  const [limit, setLimit] = useState<string>('');
  const [preview, setPreview] = useState<string[]>([]);
  const [manifest, setManifest] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const requestController = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (requestController.current) {
        requestController.current.abort();
        requestController.current = null;
      }
    };
  }, []);

  const formatExtension = useMemo(() => {
    switch (downloadFormat) {
      case 'json':
        return 'json';
      case 'ndjson':
        return 'ndjson';
      case 'csv':
        return 'csv';
      default:
        return 'md';
    }
  }, [downloadFormat]);

  const buildPayload = useCallback(
    (format: string) => {
      const payload: Record<string, unknown> = {
        style,
        format,
        document_ids: normaliseDocumentIds(documentIds),
        osis: osis.trim() || null,
        filters: {
          collection: collection.trim() || null,
          author: author.trim() || null,
          source_type: sourceType.trim() || null,
        },
      };
      const limitValue = limit.trim();
      if (limitValue) {
        const parsed = Number.parseInt(limitValue, 10);
        if (!Number.isNaN(parsed) && parsed > 0) {
          payload.limit = parsed;
        }
      }
      if (Array.isArray(payload.document_ids) && payload.document_ids.length === 0) {
        payload.document_ids = null;
      }
      if (!payload.osis && !payload.document_ids) {
        throw new Error('Provide at least one document ID or an OSIS reference.');
      }
      return payload;
    },
    [style, documentIds, osis, collection, author, sourceType, limit],
  );

  const handlePreview = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    let controller: AbortController | null = null;
    try {
      const payload = buildPayload('json');
      if (requestController.current) {
        requestController.current.abort();
      }
      controller = new AbortController();
      requestController.current = controller;
      const response = await fetch('/export/citations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Unable to preview citations.');
      }
      const data = await response.json();
      const records = Array.isArray(data.records) ? data.records : [];
      setPreview(
        records.map((record) => {
          if (record && typeof record === 'object' && 'citation' in record && typeof record.citation === 'string') {
            return record.citation;
          }
          return JSON.stringify(record);
        }),
      );
      setManifest(data.manifest ?? null);
    } catch (previewError: unknown) {
      if (isAbortError(previewError)) {
        return;
      }
      const message = previewError instanceof Error ? previewError.message : 'Unable to preview citations.';
      setError(message);
      setPreview([]);
      setManifest(null);
    } finally {
      if (!controller) {
        setLoading(false);
        return;
      }
      if (requestController.current === controller) {
        requestController.current = null;
        setLoading(false);
      }
    }
  }, [buildPayload]);

  const handleDownload = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    let controller: AbortController | null = null;
    try {
      const payload = buildPayload(downloadFormat);
      if (requestController.current) {
        requestController.current.abort();
      }
      controller = new AbortController();
      requestController.current = controller;
      const response = await fetch('/export/citations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Unable to download citation bundle.');
      }
      const blob = await response.blob();
      const fallbackName = `theo-citations.${formatExtension}`;
      const filename = parseFilename(response.headers.get('Content-Disposition'), fallbackName);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setSuccess(`Downloaded ${filename}`);
    } catch (downloadError: unknown) {
      if (isAbortError(downloadError)) {
        return;
      }
      const message = downloadError instanceof Error ? downloadError.message : 'Unable to download citation bundle.';
      setError(message);
    } finally {
      if (!controller) {
        setLoading(false);
        return;
      }
      if (requestController.current === controller) {
        requestController.current = null;
        setLoading(false);
      }
    }
  }, [buildPayload, downloadFormat, formatExtension]);

  return (
    <div className="export-page" style={{ maxWidth: 960, margin: '0 auto', padding: '2rem 1.5rem' }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 600, marginBottom: '1rem' }}>Citation exports</h1>
      <p style={{ marginBottom: '1.5rem' }}>
        Generate formatted citations for selected documents or verse mentions. Provide document identifiers (one per line)
        or an OSIS reference to collect matching passages from the Verse Aggregator.
      </p>

      <section style={{ display: 'grid', gap: '1rem', marginBottom: '2rem' }}>
        <label style={{ display: 'grid', gap: '0.5rem' }}>
          <span>Document identifiers</span>
          <textarea
            value={documentIds}
            onChange={(event) => setDocumentIds(event.target.value)}
            rows={4}
            placeholder="doc-123\ndoc-456"
            style={{ fontFamily: 'var(--font-mono)', padding: '0.75rem', borderRadius: 8, border: '1px solid var(--border)' }}
          />
        </label>

        <label style={{ display: 'grid', gap: '0.5rem' }}>
          <span>OSIS reference</span>
          <input
            value={osis}
            onChange={(event) => setOsis(event.target.value)}
            placeholder="John.1.1"
            style={{ padding: '0.65rem 0.75rem', borderRadius: 8, border: '1px solid var(--border)' }}
          />
        </label>

        <div style={{ display: 'grid', gap: '0.5rem', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
          <label style={{ display: 'grid', gap: '0.25rem' }}>
            <span>Collection</span>
            <input
              value={collection}
              onChange={(event) => setCollection(event.target.value)}
              placeholder="sermons"
              style={{ padding: '0.65rem 0.75rem', borderRadius: 8, border: '1px solid var(--border)' }}
            />
          </label>
          <label style={{ display: 'grid', gap: '0.25rem' }}>
            <span>Author filter</span>
            <input
              value={author}
              onChange={(event) => setAuthor(event.target.value)}
              placeholder="Jane Doe"
              style={{ padding: '0.65rem 0.75rem', borderRadius: 8, border: '1px solid var(--border)' }}
            />
          </label>
          <label style={{ display: 'grid', gap: '0.25rem' }}>
            <span>Source type</span>
            <input
              value={sourceType}
              onChange={(event) => setSourceType(event.target.value)}
              placeholder="sermon"
              style={{ padding: '0.65rem 0.75rem', borderRadius: 8, border: '1px solid var(--border)' }}
            />
          </label>
          <label style={{ display: 'grid', gap: '0.25rem' }}>
            <span>Verse mention limit</span>
            <input
              value={limit}
              onChange={(event) => setLimit(event.target.value)}
              placeholder="100"
              style={{ padding: '0.65rem 0.75rem', borderRadius: 8, border: '1px solid var(--border)' }}
            />
          </label>
        </div>

        <label style={{ display: 'grid', gap: '0.5rem' }}>
          <span>Citation style</span>
          <select
            value={style}
            onChange={(event) => setStyle(event.target.value)}
            style={{ padding: '0.65rem 0.75rem', borderRadius: 8, border: '1px solid var(--border)' }}
          >
            <option value="apa">APA</option>
            <option value="chicago">Chicago</option>
            <option value="csl-json">CSL JSON</option>
          </select>
        </label>

        <label style={{ display: 'grid', gap: '0.5rem' }}>
          <span>Download format</span>
          <select
            value={downloadFormat}
            onChange={(event) => setDownloadFormat(event.target.value)}
            style={{ padding: '0.65rem 0.75rem', borderRadius: 8, border: '1px solid var(--border)' }}
          >
            {Object.entries(FORMAT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </section>

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
        <button
          type="button"
          onClick={handlePreview}
          disabled={loading}
          style={{
            padding: '0.75rem 1.5rem',
            borderRadius: 999,
            border: 'none',
            backgroundColor: 'var(--accent)',
            color: 'white',
            cursor: 'pointer',
          }}
        >
          {loading ? 'Working…' : 'Preview citations'}
        </button>
        <button
          type="button"
          onClick={handleDownload}
          disabled={loading}
          style={{
            padding: '0.75rem 1.5rem',
            borderRadius: 999,
            border: '1px solid var(--border-strong)',
            backgroundColor: 'white',
            color: 'var(--text-strong)',
            cursor: 'pointer',
          }}
        >
          Download {FORMAT_LABELS[downloadFormat] ?? downloadFormat.toUpperCase()}
        </button>
      </div>

      {error && (
        <p role="alert" style={{ color: 'var(--danger)', marginBottom: '1.5rem' }}>
          {error}
        </p>
      )}
      {success && (
        <p role="status" style={{ color: 'var(--success)', marginBottom: '1.5rem' }}>
          {success}
        </p>
      )}

      <section style={{ display: 'grid', gap: '1rem' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>Preview</h2>
        {manifest && (
          <pre
            style={{
              fontSize: '0.9rem',
              padding: '0.75rem',
              backgroundColor: 'var(--surface-subtle)',
              borderRadius: 8,
              overflowX: 'auto',
            }}
          >
            {JSON.stringify(manifest, null, 2)}
          </pre>
        )}
        {preview.length > 0 ? (
          <ol style={{ display: 'grid', gap: '0.75rem', paddingLeft: '1.25rem' }}>
            {preview.map((item, index) => (
              <li key={`${index}-${item.slice(0, 12)}`} style={{ lineHeight: 1.5 }}>
                {item}
              </li>
            ))}
          </ol>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>
            {loading ? 'Generating preview…' : 'Provide selection criteria and choose “Preview citations” to view formatted output.'}
          </p>
        )}
      </section>
    </div>
  );
}
