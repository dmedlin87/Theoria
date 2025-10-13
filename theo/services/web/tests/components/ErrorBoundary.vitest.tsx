import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import ErrorBoundary from "../../app/components/ErrorBoundary";
import { useState } from "react";

function ProblemChild({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error("Boom");
  }
  return <p>All good</p>;
}

describe("ErrorBoundary", () => {
  let consoleSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    consoleSpy.mockRestore();
    cleanup();
  });

  it("renders children when no error occurs", () => {
    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("All good")).toBeInTheDocument();
  });

  it("shows the default fallback UI when an error is thrown", () => {
    render(
      <ErrorBoundary>
        <ProblemChild shouldThrow={true} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Boom")).toBeInTheDocument();
  });

  it("invokes the reset callback provided by a custom fallback", async () => {
    function Harness() {
      const [shouldThrow, setShouldThrow] = useState(false);
      return (
        <div>
          <button type="button" onClick={() => setShouldThrow(true)}>
            Trigger
          </button>
          <ErrorBoundary
            fallback={(error, reset) => (
              <div role="alert">
                <p>{error.message}</p>
                <button
                  type="button"
                  onClick={() => {
                    setShouldThrow(false);
                    reset();
                  }}
                >
                  Try again
                </button>
              </div>
            )}
          >
            <ProblemChild shouldThrow={shouldThrow} />
          </ErrorBoundary>
        </div>
      );
    }

    const user = userEvent.setup();
    render(<Harness />);

    expect(screen.getByText("All good")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Trigger" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Boom");

    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.getByText("All good")).toBeInTheDocument();
  });
});
