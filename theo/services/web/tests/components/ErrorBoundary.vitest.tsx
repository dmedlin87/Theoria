import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { useState } from "react";

import ErrorBoundary from "../../app/components/ErrorBoundary";

function Explosive(): JSX.Element {
  throw new Error("Boom");
}

describe("ErrorBoundary", () => {
  it("renders the default fallback when a child throws", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Explosive />
      </ErrorBoundary>,
    );

    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    expect(screen.getByText("Boom")).toBeInTheDocument();

    errorSpy.mockRestore();
  });

  it("supports a custom fallback that can reset the boundary", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const user = userEvent.setup();

    function Example(): JSX.Element {
      const [shouldThrow, setShouldThrow] = useState(true);
      return (
        <ErrorBoundary
          fallback={(error, reset) => (
            <div>
              <p role="alert">{error.message}</p>
              <button
                type="button"
                onClick={() => {
                  setShouldThrow(false);
                  reset();
                }}
              >
                Recover
              </button>
            </div>
          )}
        >
          {shouldThrow ? <Explosive /> : <p>Recovered</p>}
        </ErrorBoundary>
      );
    }

    render(<Example />);

    await user.click(screen.getByRole("button", { name: "Recover" }));
    expect(screen.getByText("Recovered")).toBeInTheDocument();

    errorSpy.mockRestore();
  });
});
