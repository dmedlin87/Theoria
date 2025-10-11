import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useRouter } from "next/navigation";

import { ModeProvider, useMode } from "../../app/mode-context";
import { DEFAULT_MODE_ID, MODE_COOKIE_KEY } from "../../app/mode-config";
import type { ResearchModeId } from "../../app/mode-config";

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

describe("ModeProvider", () => {
  const useRouterMock = useRouter as unknown as jest.Mock;

  function ModeConsumer({ nextMode }: { nextMode: ResearchModeId }) {
    const { mode, setMode } = useMode();

    return (
      <div>
        <span data-testid="mode-id">{mode.id}</span>
        <button type="button" onClick={() => setMode(nextMode)}>
          Change mode
        </button>
      </div>
    );
  }

  function renderWithProvider(initialMode?: string) {
    const providerProps: { initialMode?: ResearchModeId } = initialMode
      ? { initialMode: initialMode as ResearchModeId }
      : {};

    return render(
      <ModeProvider {...providerProps}>
        <ModeConsumer nextMode="investigative" />
      </ModeProvider>,
    );
  }

  beforeEach(() => {
    useRouterMock.mockReturnValue({ refresh: jest.fn() });
    localStorage.clear();
    document.cookie = `${MODE_COOKIE_KEY}=; Max-Age=0`;
  });

  it("falls back to the default mode when the provided mode id is invalid", async () => {
    renderWithProvider("toString");

    await waitFor(() => {
      expect(screen.getByTestId("mode-id")).toHaveTextContent(DEFAULT_MODE_ID);
    });
  });

  it("uses the provided mode when it is valid", async () => {
    const validMode: ResearchModeId = "devotional";
    renderWithProvider(validMode);

    await waitFor(() => {
      expect(screen.getByTestId("mode-id")).toHaveTextContent(validMode);
    });
  });

  it("updates the mode and refreshes the router when the user selects a new mode", async () => {
    const refresh = jest.fn();
    useRouterMock.mockReturnValue({ refresh });

    renderWithProvider(DEFAULT_MODE_ID);

    fireEvent.click(screen.getByRole("button", { name: "Change mode" }));

    await waitFor(() => {
      expect(screen.getByTestId("mode-id")).toHaveTextContent("investigative");
    });

    expect(refresh).toHaveBeenCalled();
  });
});
