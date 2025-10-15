/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { render, waitFor } from "@testing-library/react";

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

describe("UploadPage empty state hero", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    jest.useRealTimers();
  });

  it("highlights supported formats before any jobs exist", async () => {
    jest.useFakeTimers();
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ jobs: [] }),
    } as Response);
    global.fetch = fetchMock as unknown as typeof fetch;

    const { asFragment } = render(
      <ToastProvider>
        <UploadPage />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    expect(asFragment()).toMatchSnapshot();
    jest.runOnlyPendingTimers();
  });
});
