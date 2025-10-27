/** @jest-environment jsdom */

import { act, renderHook } from "@testing-library/react";

import type { TheoApiClient } from "../../app/lib/api-client";
import {
  useCitationExporter,
  useCollaborationWorkflow,
  useComparativeWorkflow,
  useCurationWorkflow,
  useDevotionalWorkflow,
  useExportWorkflow,
  useSermonWorkflow,
  useVerseWorkflow,
} from "../../app/copilot/components/workflow-hooks";
import type { CollaborationResponse, DevotionalResponse, ExportPresetResult, VerseResponse } from "../../app/copilot/components/types";

type MockApi = Pick<
  TheoApiClient,
  | "runVerseWorkflow"
  | "runSermonWorkflow"
  | "runComparativeWorkflow"
  | "runMultimediaWorkflow"
  | "runDevotionalWorkflow"
  | "runCollaborationWorkflow"
  | "runCurationWorkflow"
  | "runSermonExport"
  | "runTranscriptExport"
  | "exportCitations"
>;

function createMockApi(): jest.Mocked<MockApi> {
  return {
    runVerseWorkflow: jest.fn(),
    runSermonWorkflow: jest.fn(),
    runComparativeWorkflow: jest.fn(),
    runMultimediaWorkflow: jest.fn(),
    runDevotionalWorkflow: jest.fn(),
    runCollaborationWorkflow: jest.fn(),
    runCurationWorkflow: jest.fn(),
    runSermonExport: jest.fn(),
    runTranscriptExport: jest.fn(),
    exportCitations: jest.fn(),
  };
}

describe("copilot workflow hooks", () => {
  it("runs verse workflow with trimmed fields", async () => {
    const api = createMockApi();
    const verseResult: VerseResponse = {
      osis: "John.1.1",
      follow_ups: [],
      answer: { summary: "Summary", citations: [] },
      question: null,
    };
    api.runVerseWorkflow.mockResolvedValueOnce(verseResult);
    const { result } = renderHook(() => useVerseWorkflow(api as unknown as TheoApiClient));
    await act(async () => {
      result.current.setForm({ passage: "  John 1:1-5  ", question: "  Why?  " });
    });
    const payload = await result.current.run("gpt");
    expect(payload).toEqual(verseResult);
    expect(api.runVerseWorkflow).toHaveBeenCalledWith({
      model: "gpt",
      osis: null,
      passage: "John 1:1-5",
      question: "Why?",
    });
  });

  it("requires a sermon topic", async () => {
    const api = createMockApi();
    const { result } = renderHook(() => useSermonWorkflow(api as unknown as TheoApiClient));
    await expect(result.current.run("gpt")).rejects.toThrow("Provide a sermon topic.");
  });

  it("enforces comparative participants", async () => {
    const api = createMockApi();
    const { result } = renderHook(() => useComparativeWorkflow(api as unknown as TheoApiClient));
    await act(async () => {
      result.current.setForm({ osis: "John.1.1", participants: "Solo" });
    });
    await expect(result.current.run("gpt")).rejects.toThrow("Add at least two participants to compare.");
  });

  it("runs devotional workflow when required fields are present", async () => {
    const api = createMockApi();
    const devotional: DevotionalResponse = {
      osis: "John.1.1-5",
      focus: "Focus",
      reflection: "Reflection",
      prayer: "Prayer",
      answer: { summary: "Summary", citations: [] },
    };
    api.runDevotionalWorkflow.mockResolvedValueOnce(devotional);
    const { result } = renderHook(() => useDevotionalWorkflow(api as unknown as TheoApiClient));
    await act(async () => {
      result.current.setForm({ osis: "  John.1.1-5  ", focus: "  Grace  " });
    });
    const payload = await result.current.run("gpt");
    expect(payload).toEqual(devotional);
    expect(api.runDevotionalWorkflow).toHaveBeenCalledWith({
      model: "gpt",
      osis: "John.1.1-5",
      focus: "Grace",
    });
  });

  it("rejects invalid curation timestamp", async () => {
    const api = createMockApi();
    const { result } = renderHook(() => useCurationWorkflow(api as unknown as TheoApiClient));
    await act(async () => {
      result.current.setForm({ since: "invalid-date" });
    });
    await expect(result.current.run("gpt")).rejects.toThrow(
      "Provide an ISO 8601 timestamp (YYYY-MM-DD or similar).",
    );
  });

  it("supports collaboration workflow validation", async () => {
    const api = createMockApi();
    const collaboration: CollaborationResponse = {
      thread: "thread",
      synthesized_view: "View",
      answer: { summary: "Summary", citations: [] },
    };
    api.runCollaborationWorkflow.mockResolvedValueOnce(collaboration);
    const { result } = renderHook(() => useCollaborationWorkflow(api as unknown as TheoApiClient));
    await act(async () => {
      result.current.setForm({ thread: "t", osis: "John.1.1", viewpoints: "One, Two" });
    });
    await result.current.run("gpt");
    expect(api.runCollaborationWorkflow).toHaveBeenCalledWith({
      model: "gpt",
      thread: "t",
      osis: "John.1.1",
      viewpoints: ["One", "Two"],
    });
  });

  it("routes export requests to sermon and transcript endpoints", async () => {
    const api = createMockApi();
    const sermonExport: ExportPresetResult = {
      preset: "sermon-markdown",
      format: "markdown",
      filename: "sermon.md",
      mediaType: "text/markdown",
      content: "sermon export",
    };
    api.runSermonExport.mockResolvedValueOnce(sermonExport);
    const { result: sermonResult } = renderHook(() => useExportWorkflow(api as unknown as TheoApiClient));
    await act(async () => {
      sermonResult.current.setForm({ topic: "Hope", osis: "John.1.1" });
    });
    await sermonResult.current.run("gpt");
    expect(api.runSermonExport).toHaveBeenCalledWith({
      model: "gpt",
      topic: "Hope",
      osis: "John.1.1",
      format: "markdown",
    });

    const transcriptExport: ExportPresetResult = {
      ...sermonExport,
      preset: "transcript-csv",
      format: "csv",
      filename: "transcript.csv",
      mediaType: "text/csv",
      content: "transcript export",
    };
    api.runTranscriptExport.mockResolvedValueOnce(transcriptExport);
    const { result: transcriptResult } = renderHook(() => useExportWorkflow(api as unknown as TheoApiClient));
    await act(async () => {
      transcriptResult.current.setForm({ preset: "transcript-csv", documentId: "doc-1" });
    });
    await transcriptResult.current.run("gpt");
    expect(api.runTranscriptExport).toHaveBeenCalledWith({ documentId: "doc-1", format: "csv" });
  });

  it("surfaces export errors for missing transcripts", async () => {
    const api = createMockApi();
    api.runTranscriptExport.mockRejectedValueOnce(new Error("Transcript not found"));
    const { result } = renderHook(() => useExportWorkflow(api as unknown as TheoApiClient));
    await act(async () => {
      result.current.setForm({ preset: "transcript-csv", documentId: "missing" });
    });
    await expect(result.current.run("gpt")).rejects.toThrow("Transcript not found");
  });

  it("exports citations", async () => {
    const api = createMockApi();
    api.exportCitations.mockResolvedValueOnce({
      manifest: {
        export_id: "abc",
        schema_version: "1",
        created_at: "2024-01-01T00:00:00Z",
        type: "search",
        filters: {},
        totals: { records: 0 },
      },
      records: [],
      csl: [],
      manager_payload: {},
    });
    const { result } = renderHook(() => useCitationExporter(api as unknown as TheoApiClient));
    await result.current.exportCitations([
      {
        index: 1,
        osis: "John",
        anchor: "a",
        snippet: "s",
        document_id: "d",
        passage_id: "john.1.1",
      },
    ]);
    expect(api.exportCitations).toHaveBeenCalledWith({
      citations: [
        {
          index: 1,
          osis: "John",
          anchor: "a",
          snippet: "s",
          document_id: "d",
          passage_id: "john.1.1",
        },
      ],
    });
  });
});
