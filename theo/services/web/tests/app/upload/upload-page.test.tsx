/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";

import { ToastProvider } from "../../../app/components/Toast";
import UploadPage from "../../../app/upload/page";

jest.mock("../../../app/upload/components/SimpleIngestForm", () => ({
  __esModule: true,
  default: () => <div data-testid="simple-ingest-form" />,
}));

jest.mock("../../../app/upload/components/FileUploadForm", () => ({
  __esModule: true,
  default: () => <div data-testid="file-upload-form" />,
}));

jest.mock("../../../app/upload/components/UrlIngestForm", () => ({
  __esModule: true,
  default: () => <div data-testid="url-ingest-form" />,
}));

jest.mock("../../../app/upload/components/JobsTable", () => ({
  __esModule: true,
  default: () => <div data-testid="jobs-table" />,
}));

jest.mock("../../../app/lib/api", () => ({
  getApiBaseUrl: () => "https://api.example.com",
}));

const renderWithToast = (ui: ReactElement) => render(<ToastProvider>{ui}</ToastProvider>);

describe("UploadPage trace details", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("surfaces trace information in a toast when requested", async () => {
    const fetchMock = jest.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ message: "Failed to load jobs", traceId: "trace-5678" }),
        {
          status: 500,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    renderWithToast(<UploadPage />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    const showDetailsButton = await screen.findByRole("button", { name: "Show details" });
    fireEvent.click(showDetailsButton);

    await waitFor(() => {
      expect(screen.getByText("Trace ID: trace-5678")).toBeInTheDocument();
    });
  });
});
