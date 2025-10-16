'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

type CitationStyleOption = 'apa' | 'chicago' | 'sbl' | 'bibtex' | 'csl-json';
type CitationExportFormat = 'markdown' | 'json' | 'ndjson' | 'csv';

type UseCitationExportOptions = {
  defaultStyle?: CitationStyleOption;
  defaultFormat?: CitationExportFormat;
  onZoteroItems?: (items: unknown[]) => void;
};

type CitationExportPayload = {
  style: string;
  format: string;
  document_ids: string[] | null;
  osis: string | null;
  filters: {
    collection: string | null;
    author: string | null;
    source_type: string | null;
  };
  limit?: number;
};

type ManifestShape = Record<string, unknown> | null;

type UseCitationExportReturn = {
  style: CitationStyleOption;
  setStyle: (value: CitationStyleOption) => void;
  downloadFormat: CitationExportFormat;
  setDownloadFormat: (value: CitationExportFormat) => void;
  documentIds: string;
  setDocumentIds: (value: string) => void;
  osis: string;
  setOsis: (value: string) => void;
  collection: string;
  setCollection: (value: string) => void;
  author: string;
  setAuthor: (value: string) => void;
  sourceType: string;
  setSourceType: (value: string) => void;
  limit: string;
  setLimit: (value: string) => void;
  preview: string[];
  manifest: ManifestShape;
  loading: boolean;
  error: string | null;
  success: string | null;
  formatExtension: string;
  previewCitations: () => Promise<void>;
  downloadCitations: () => Promise<void>;
  resetFeedback: () => void;
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

function buildFormatExtension(format: CitationExportFormat): string {
  switch (format) {
    case 'json':
      return 'json';
    case 'ndjson':
      return 'ndjson';
    case 'csv':
      return 'csv';
    default:
      return 'md';
  }
}

function sanitiseText(input: string): string | null {
  const trimmed = input.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function useCitationExport(options: UseCitationExportOptions = {}): UseCitationExportReturn {
  const [style, setStyleState] = useState<CitationStyleOption>(options.defaultStyle ?? 'apa');
  const [downloadFormat, setDownloadFormatState] = useState<CitationExportFormat>(
    options.defaultFormat ?? 'markdown',
  );
  const [documentIds, setDocumentIds] = useState<string>('');
  const [osis, setOsis] = useState<string>('');
  const [collection, setCollection] = useState<string>('');
  const [author, setAuthor] = useState<string>('');
  const [sourceType, setSourceType] = useState<string>('');
  const [limit, setLimit] = useState<string>('');
  const [preview, setPreview] = useState<string[]>([]);
  const [manifest, setManifest] = useState<ManifestShape>(null);
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

  const formatExtension = useMemo(() => buildFormatExtension(downloadFormat), [downloadFormat]);

  const resetFeedback = useCallback(() => {
    setError(null);
    setSuccess(null);
  }, []);

  const buildPayload = useCallback(
    (format: string): CitationExportPayload => {
      const payload: CitationExportPayload = {
        style,
        format,
        document_ids: normaliseDocumentIds(documentIds),
        osis: sanitiseText(osis),
        filters: {
          collection: sanitiseText(collection),
          author: sanitiseText(author),
          source_type: sanitiseText(sourceType),
        },
      };
      const limitValue = sanitiseText(limit);
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

  const previewCitations = useCallback(async () => {
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
        records.map((record: unknown) => {
          if (
            record &&
            typeof record === 'object' &&
            'citation' in record &&
            typeof (record as { citation?: unknown }).citation === 'string'
          ) {
            return (record as { citation: string }).citation;
          }
          return JSON.stringify(record);
        }),
      );
      setManifest(data.manifest ?? null);
      const zoteroItems = data?.manager_payload?.zotero?.items;
      if (Array.isArray(zoteroItems) && options.onZoteroItems) {
        options.onZoteroItems(zoteroItems);
      }
    } catch (previewError: unknown) {
      if (isAbortError(previewError)) {
        return;
      }
      const message = previewError instanceof Error ? previewError.message : 'Unable to preview citations.';
      setError(message);
      setPreview([]);
      setManifest(null);
    } finally {
      if (controller && requestController.current === controller) {
        requestController.current = null;
      }
      setLoading(false);
    }
  }, [buildPayload, options.onZoteroItems]);

  const downloadCitations = useCallback(async () => {
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
      const contentEncoding = response.headers.get('Content-Encoding');
      const resolvedFilename =
        contentEncoding && /gzip/i.test(contentEncoding) ? filename.replace(/\.gz$/i, '') || fallbackName : filename;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = resolvedFilename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setSuccess(`Downloaded ${resolvedFilename}`);
    } catch (downloadError: unknown) {
      if (isAbortError(downloadError)) {
        return;
      }
      const message =
        downloadError instanceof Error ? downloadError.message : 'Unable to download citation bundle.';
      setError(message);
    } finally {
      if (controller && requestController.current === controller) {
        requestController.current = null;
      }
      setLoading(false);
    }
  }, [buildPayload, downloadFormat, formatExtension]);

  const setStyle = useCallback((value: CitationStyleOption) => {
    setStyleState(value);
  }, []);

  const setDownloadFormat = useCallback((value: CitationExportFormat) => {
    setDownloadFormatState(value);
  }, []);

  return {
    style,
    setStyle,
    downloadFormat,
    setDownloadFormat,
    documentIds,
    setDocumentIds,
    osis,
    setOsis,
    collection,
    setCollection,
    author,
    setAuthor,
    sourceType,
    setSourceType,
    limit,
    setLimit,
    preview,
    manifest,
    loading,
    error,
    success,
    formatExtension,
    previewCitations,
    downloadCitations,
    resetFeedback,
  };
}

export type { CitationStyleOption, CitationExportFormat, UseCitationExportOptions };
