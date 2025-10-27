/** @jest-environment jsdom */

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import CitationList from "../../app/copilot/components/CitationList";
import QuickStartPresets from "../../app/copilot/components/QuickStartPresets";
import RAGAnswer from "../../app/copilot/components/RAGAnswer";
import WorkflowFormFields from "../../app/copilot/components/WorkflowFormFields";
import WorkflowResultPanel from "../../app/copilot/components/WorkflowResultPanel";
import WorkflowSelector from "../../app/copilot/components/WorkflowSelector";
import type { ExportPreset, QuickStartPreset } from "../../app/copilot/components/types";
import type {
  CollaborationFormState,
  ComparativeFormState,
  CurationFormState,
  DevotionalFormState,
  ExportFormState,
  MultimediaFormState,
  SermonFormState,
  VerseFormState,
} from "../../app/copilot/components/workflow-hooks";

const EXPORT_PRESETS: ExportPreset[] = [
  {
    id: "sermon-markdown",
    label: "Sermon",
    description: "Desc",
    type: "sermon",
    format: "markdown",
  },
  {
    id: "transcript-csv",
    label: "Transcript",
    description: "Desc",
    type: "transcript",
    format: "csv",
  },
];

beforeEach(() => {
  (globalThis as typeof globalThis & { fetch: jest.Mock }).fetch = jest
    .fn()
    .mockResolvedValue({
      ok: true,
      json: async () => [],
    });
});

afterEach(() => {
  jest.resetAllMocks();
});

describe("copilot components", () => {
  it("renders workflow selector and triggers selection", () => {
    const onSelect = jest.fn();
    render(
      <WorkflowSelector
        options={[{ id: "verse", label: "Verse", description: "Desc" }]}
        selected="sermon"
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByText("Verse").closest("button")!);
    expect(onSelect).toHaveBeenCalledWith("verse");
  });

  it("renders quick start presets", () => {
    const preset: QuickStartPreset = {
      id: "preset",
      title: "Title",
      description: "Description",
      workflow: "verse",
    };
    const onSelect = jest.fn();
    render(<QuickStartPresets presets={[preset]} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /title/i }));
    expect(onSelect).toHaveBeenCalledWith(preset);
  });

  it("renders workflow form fields for verse workflow", () => {
    const verse: VerseFormState = { osis: "", passage: "", question: "", useAdvanced: false };
    const sermon: SermonFormState = { topic: "", osis: "" };
    const comparative: ComparativeFormState = { osis: "", participants: "" };
    const multimedia: MultimediaFormState = { collection: "" };
    const devotional: DevotionalFormState = { osis: "", focus: "" };
    const collaboration: CollaborationFormState = { thread: "", osis: "", viewpoints: "" };
    const curation: CurationFormState = { since: "" };
    const exportPreset: ExportFormState = { preset: "sermon-markdown", topic: "", osis: "", documentId: "" };
    render(
      <WorkflowFormFields
        workflow="verse"
        exportPresets={EXPORT_PRESETS}
        verse={{ form: verse, onChange: () => undefined }}
        sermon={{ form: sermon, onChange: () => undefined }}
        comparative={{ form: comparative, onChange: () => undefined }}
        multimedia={{ form: multimedia, onChange: () => undefined }}
        devotional={{ form: devotional, onChange: () => undefined }}
        collaboration={{ form: collaboration, onChange: () => undefined }}
        curation={{ form: curation, onChange: () => undefined }}
        exportPreset={{ form: exportPreset, onChange: () => undefined }}
      />,
    );
    expect(screen.getByLabelText(/Passage/i)).toBeInTheDocument();
  });

  it("renders workflow result panel summary", () => {
    render(
      <WorkflowResultPanel
        summary="Summary"
        exporting={false}
        status={null}
        onExport={jest.fn()}
        workflowId="verse"
        result={{
          kind: "verse",
          payload: {
            osis: "John.1.1",
            follow_ups: ["Follow"],
            question: null,
            answer: { summary: "Answer", citations: [] },
          },
        }}
      />,
    );
    expect(screen.getByText(/Verse brief for/)).toBeInTheDocument();
    expect(screen.getByText(/Verse brief/)).toBeInTheDocument();
  });

  it("renders citation list and triggers export", async () => {
    const onExport = jest.fn();
    await act(async () => {
      render(
        <CitationList
          citations={[
            {
              index: 1,
              osis: "John",
              anchor: "1",
              snippet: "Snippet",
              document_id: "doc",
              passage_id: "John.1.1",
              document_title: "Document",
              source_url: "https://example.com",
            },
          ]}
          summaryText="Summary"
          workflowId="verse"
          onExport={onExport}
        />,
      );
    });
    fireEvent.click(screen.getByRole("button", { name: /export/i }));
    expect(onExport).toHaveBeenCalled();
  });

  it("does not refetch annotations when citation identities are unchanged", async () => {
    const citations = [
      {
        index: 1,
        osis: "John",
        anchor: "1",
        snippet: "Snippet",
        document_id: "doc",
        passage_id: "John.1.1",
        document_title: "Document",
        source_url: "https://example.com",
      },
    ] satisfies Parameters<typeof CitationList>[0]["citations"];

    const { rerender } = render(
      <CitationList
        citations={citations}
        summaryText="Summary"
        workflowId="verse"
        onExport={jest.fn()}
      />,
    );

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });

    (globalThis.fetch as jest.Mock).mockClear();

    rerender(
      <CitationList
        citations={citations.map((citation) => ({ ...citation }))}
        summaryText="Summary"
        workflowId="verse"
        onExport={jest.fn()}
      />,
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("renders RAG answer with follow ups", () => {
    render(
      <RAGAnswer
        answer={{ summary: "Summary", citations: [] }}
        followUps={["Next"]}
      />,
    );
    expect(screen.getByRole("heading", { name: /Summary/ })).toBeInTheDocument();
    expect(screen.getByText(/Next/)).toBeInTheDocument();
  });
});
/** @jest-environment jsdom */
