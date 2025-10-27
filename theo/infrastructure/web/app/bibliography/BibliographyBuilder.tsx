"use client";

import { useState, useEffect, useMemo } from "react";
import styles from "./bibliography.module.css";

type CitationStyle = "apa" | "chicago" | "sbl" | "bibtex";

type Document = {
  id: string;
  title: string;
  authors?: string[];
  year?: number;
  venue?: string;
  collection?: string;
};

type CitationRecord = {
  document_id: string;
  citation: string;
  title?: string;
  authors?: string[];
  year?: number;
};

export default function BibliographyBuilder() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [style, setStyle] = useState<CitationStyle>("apa");
  const [citations, setCitations] = useState<CitationRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [zoteroKey, setZoteroKey] = useState("");
  const [zoteroLoading, setZoteroLoading] = useState(false);
  const [exportStatus, setExportStatus] = useState<string | null>(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  useEffect(() => {
    if (selectedIds.size > 0) {
      generateCitations();
    } else {
      setCitations([]);
    }
  }, [selectedIds, style]);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/documents");
      if (!response.ok) throw new Error("Failed to load documents");
      const data = await response.json();
      setDocuments(data.documents || []);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load documents";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const generateCitations = async () => {
    if (selectedIds.size === 0) return;

    try {
      setLoading(true);
      const response = await fetch("/api/export/citations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_ids: Array.from(selectedIds),
          style,
        }),
      });

      if (!response.ok) throw new Error("Failed to generate citations");
      const data = await response.json();
      setCitations(data.records || []);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to generate citations";
      setError(message);
      setCitations([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleDocument = (id: string) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedIds(newSet);
  };

  const selectAll = () => {
    setSelectedIds(new Set(filteredDocuments.map((d) => d.id)));
  };

  const clearAll = () => {
    setSelectedIds(new Set());
  };

  const copyToClipboard = async () => {
    const text = citations.map((c) => c.citation).join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      setExportStatus("Copied to clipboard!");
      setTimeout(() => setExportStatus(null), 3000);
    } catch (err) {
      setError("Failed to copy to clipboard");
    }
  };

  const downloadFile = () => {
    const text = citations.map((c) => c.citation).join("\n\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bibliography-${style}-${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setExportStatus("Downloaded!");
    setTimeout(() => setExportStatus(null), 3000);
  };

  const exportToZotero = async () => {
    if (!zoteroKey.trim()) {
      setError("Zotero API key is required");
      return;
    }

    if (selectedIds.size === 0) {
      setError("No documents selected");
      return;
    }

    try {
      setZoteroLoading(true);
      setError(null);
      const response = await fetch("/api/export/zotero", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_ids: Array.from(selectedIds),
          api_key: zoteroKey,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to export to Zotero");
      }

      const data = await response.json();
      setExportStatus(`Exported ${data.exported_count || selectedIds.size} items to Zotero!`);
      setTimeout(() => setExportStatus(null), 5000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to export to Zotero";
      setError(message);
    } finally {
      setZoteroLoading(false);
    }
  };

  const filteredDocuments = useMemo(() => {
    if (!searchQuery.trim()) return documents;
    const query = searchQuery.toLowerCase();
    return documents.filter(
      (doc) =>
        doc.title.toLowerCase().includes(query) ||
        doc.authors?.some((author) => author.toLowerCase().includes(query)) ||
        doc.venue?.toLowerCase().includes(query)
    );
  }, [documents, searchQuery]);

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Bibliography Builder</h1>
        <p className={styles.subtitle}>
          Select documents, choose a citation style, and export your bibliography.
        </p>
      </header>

      <div className={styles.layout}>
        {/* Document Selector */}
        <section className={styles.selector}>
          <div className={styles.selectorHeader}>
            <h2 className={styles.sectionTitle}>Select Documents</h2>
            <div className={styles.selectorActions}>
              <button
                type="button"
                className={styles.actionButton}
                onClick={selectAll}
                disabled={filteredDocuments.length === 0}
              >
                Select All
              </button>
              <button
                type="button"
                className={styles.actionButton}
                onClick={clearAll}
                disabled={selectedIds.size === 0}
              >
                Clear
              </button>
            </div>
          </div>

          <input
            type="search"
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={styles.searchInput}
          />

          <div className={styles.documentList}>
            {loading && documents.length === 0 ? (
              <div className={styles.emptyState}>Loading documents...</div>
            ) : filteredDocuments.length === 0 ? (
              <div className={styles.emptyState}>
                {searchQuery ? "No documents match your search" : "No documents available"}
              </div>
            ) : (
              filteredDocuments.map((doc) => (
                <label key={doc.id} className={styles.documentItem}>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(doc.id)}
                    onChange={() => toggleDocument(doc.id)}
                    className={styles.checkbox}
                  />
                  <div className={styles.documentInfo}>
                    <div className={styles.documentTitle}>{doc.title}</div>
                    <div className={styles.documentMeta}>
                      {doc.authors && doc.authors.length > 0 && (
                        <span>{doc.authors.join(", ")}</span>
                      )}
                      {doc.year && <span>• {doc.year}</span>}
                      {doc.venue && <span>• {doc.venue}</span>}
                    </div>
                  </div>
                </label>
              ))
            )}
          </div>

          <div className={styles.selectionSummary}>
            {selectedIds.size} document{selectedIds.size !== 1 ? "s" : ""} selected
          </div>
        </section>

        {/* Preview & Export */}
        <section className={styles.preview}>
          <div className={styles.previewHeader}>
            <h2 className={styles.sectionTitle}>Preview & Export</h2>
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value as CitationStyle)}
              className={styles.styleSelect}
            >
              <option value="apa">APA 7th Edition</option>
              <option value="chicago">Chicago 17th Edition</option>
              <option value="sbl">SBL 2nd Edition</option>
              <option value="bibtex">BibTeX</option>
            </select>
          </div>

          {error && <div className={styles.error}>{error}</div>}
          {exportStatus && <div className={styles.success}>{exportStatus}</div>}

          <div className={styles.citationList}>
            {selectedIds.size === 0 ? (
              <div className={styles.emptyState}>
                Select documents to preview citations
              </div>
            ) : loading ? (
              <div className={styles.emptyState}>Generating citations...</div>
            ) : citations.length === 0 ? (
              <div className={styles.emptyState}>No citations generated</div>
            ) : (
              <ol className={styles.citations}>
                {citations.map((citation, index) => (
                  <li key={citation.document_id} className={styles.citation}>
                    <div className={styles.citationText}>{citation.citation}</div>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className={styles.exportActions}>
            <button
              type="button"
              className={styles.primaryButton}
              onClick={copyToClipboard}
              disabled={citations.length === 0}
            >
              📋 Copy to Clipboard
            </button>
            <button
              type="button"
              className={styles.primaryButton}
              onClick={downloadFile}
              disabled={citations.length === 0}
            >
              💾 Download File
            </button>
          </div>

          {/* Zotero Export */}
          <div className={styles.zoteroSection}>
            <h3 className={styles.zoteroTitle}>Export to Zotero</h3>
            <p className={styles.zoteroDescription}>
              Enter your Zotero API key to export selected documents directly to your library.
              Get your API key from{" "}
              <a
                href="https://www.zotero.org/settings/keys"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.link}
              >
                Zotero Settings
              </a>
              .
            </p>
            <div className={styles.zoteroForm}>
              <input
                type="password"
                placeholder="Zotero API Key"
                value={zoteroKey}
                onChange={(e) => setZoteroKey(e.target.value)}
                className={styles.zoteroInput}
              />
              <button
                type="button"
                className={styles.zoteroButton}
                onClick={exportToZotero}
                disabled={zoteroLoading || selectedIds.size === 0 || !zoteroKey.trim()}
              >
                {zoteroLoading ? "Exporting..." : "📚 Export to Zotero"}
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
