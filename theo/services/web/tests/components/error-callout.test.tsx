/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

import ErrorCallout from "../../app/components/ErrorCallout";

describe("ErrorCallout", () => {
  it("renders retry and detail actions when callbacks are provided", () => {
    const handleRetry = jest.fn();
    const handleDetails = jest.fn();

    render(
      <ErrorCallout
        message="Something went wrong"
        traceId="trace-123"
        onRetry={handleRetry}
        onShowDetails={handleDetails}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(handleRetry).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Details…" }));
    expect(handleDetails).toHaveBeenCalledTimes(1);
    expect(handleDetails).toHaveBeenCalledWith("trace-123");

    expect(screen.getByText(/Support code:/i)).toHaveTextContent("Support code: trace-123");
  });

  it("omits optional controls when callbacks are not provided", () => {
    render(<ErrorCallout message="Upload failed" />);

    expect(screen.getByText("Upload failed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Details…" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Support code:/i)).not.toBeInTheDocument();
  });
});
