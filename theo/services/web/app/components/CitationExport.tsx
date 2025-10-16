'use client';

import { ChangeEvent, useCallback } from 'react';
import styles from './CitationExport.module.css';
import {
  useCitationExport,
  type CitationStyleOption,
  type CitationExportFormat,
  type UseCitationExportOptions,
} from './useCitationExport';

type CitationExportProps = UseCitationExportOptions & {
  title?: string;
  description?: string;
};

const FORMAT_LABELS: Record<CitationExportFormat, string> = {
  markdown: 'Markdown (.md)',
  json: 'JSON (.json)',
  ndjson: 'NDJSON (.ndjson)',
  csv: 'CSV (.csv)',
};

const STYLE_OPTIONS: Array<{ value: CitationStyleOption; label: string }> = [
  { value: 'apa', label: 'APA' },
  { value: 'chicago', label: 'Chicago' },
  { value: 'sbl', label: 'SBL' },
  { value: 'bibtex', label: 'BibTeX' },
  { value: 'csl-json', label: 'CSL JSON' },
];

export default function CitationExport({
  title = 'Citation exports',
  description = 'Generate formatted citations for selected documents or verse mentions. Provide document identifiers (one per line) or an OSIS reference to collect matching passages from the Verse Aggregator.',
  ...options
}: CitationExportProps): JSX.Element {
  const {
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
    previewCitations,
    downloadCitations,
    resetFeedback,
  } = useCitationExport(options);

  const handleFieldChange = useCallback(
    (setter: (value: string) => void) =>
      (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        resetFeedback();
        setter(event.target.value);
      },
    [resetFeedback],
  );

  const handleStyleChange = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      resetFeedback();
      setStyle(event.target.value as CitationStyleOption);
    },
    [resetFeedback, setStyle],
  );

  const handleFormatChange = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      resetFeedback();
      setDownloadFormat(event.target.value as CitationExportFormat);
    },
    [resetFeedback, setDownloadFormat],
  );

  return (
    <div className={styles.container}>
      <h1 className={styles.pageTitle}>{title}</h1>
      <p className={styles.pageDescription}>{description}</p>

      <section className={styles.formSection}>
        <label className={styles.formLabel}>
          <span>Document identifiers</span>
          <textarea
            value={documentIds}
            onChange={handleFieldChange(setDocumentIds)}
            rows={4}
            placeholder="doc-123\ndoc-456"
            className={styles.textarea}
          />
        </label>

        <label className={styles.formLabel}>
          <span>OSIS reference</span>
          <input
            value={osis}
            onChange={handleFieldChange(setOsis)}
            placeholder="John.1.1"
            className={styles.input}
          />
        </label>

        <div className={styles.filterGrid}>
          <label className={styles.formLabelTight}>
            <span>Collection</span>
            <input
              value={collection}
              onChange={handleFieldChange(setCollection)}
              placeholder="sermons"
              className={styles.input}
            />
          </label>
          <label className={styles.formLabelTight}>
            <span>Author filter</span>
            <input
              value={author}
              onChange={handleFieldChange(setAuthor)}
              placeholder="Jane Doe"
              className={styles.input}
            />
          </label>
          <label className={styles.formLabelTight}>
            <span>Source type</span>
            <input
              value={sourceType}
              onChange={handleFieldChange(setSourceType)}
              placeholder="sermon"
              className={styles.input}
            />
          </label>
          <label className={styles.formLabelTight}>
            <span>Verse mention limit</span>
            <input
              value={limit}
              onChange={handleFieldChange(setLimit)}
              placeholder="100"
              className={styles.input}
            />
          </label>
        </div>

        <label className={styles.formLabel}>
          <span>Citation style</span>
          <select value={style} onChange={handleStyleChange} className={styles.select}>
            {STYLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.formLabel}>
          <span>Download format</span>
          <select
            value={downloadFormat}
            onChange={handleFormatChange}
            className={styles.select}
          >
            {Object.entries(FORMAT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </section>

      <div className={styles.buttonGroup}>
        <button
          type="button"
          onClick={previewCitations}
          disabled={loading}
          className={styles.primaryButton}
        >
          {loading ? 'Working…' : 'Preview citations'}
        </button>
        <button
          type="button"
          onClick={downloadCitations}
          disabled={loading}
          className={styles.secondaryButton}
        >
          Download {FORMAT_LABELS[downloadFormat] ?? downloadFormat.toUpperCase()}
        </button>
      </div>

      {error && (
        <p role="alert" className={styles.errorMessage}>
          {error}
        </p>
      )}
      {success && (
        <p role="status" className={styles.successMessage}>
          {success}
        </p>
      )}

      <section className={styles.previewSection}>
        <h2 className={styles.sectionTitle}>Preview</h2>
        {manifest && (
          <pre className={styles.manifestPre}>{JSON.stringify(manifest, null, 2)}</pre>
        )}
        {preview.length > 0 ? (
          <ol className={styles.previewList}>
            {preview.map((item, index) => (
              <li key={`${index}-${item.slice(0, 12)}`} className={styles.previewItem}>
                {item}
              </li>
            ))}
          </ol>
        ) : (
          <p className={styles.emptyState}>
            {loading ? 'Generating preview…' : 'Provide selection criteria and choose “Preview citations” to view formatted output.'}
          </p>
        )}
      </section>
    </div>
  );
}
