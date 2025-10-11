/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Fragment } from "react";

import { ModeProvider, useMode } from "../../app/mode-context";
import type { ResearchModeId } from "../../app/mode-config";
import { DEFAULT_MODE_ID } from "../../app/mode-config";

const refreshMock = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: refreshMock,
  }),
}));

type ModeConsumerProps = {
  nextMode?: ResearchModeId;
};

function ModeConsumer({ nextMode }: ModeConsumerProps) {
  const { mode, setMode } = useMode();

  return (
    <Fragment>
      <span>mode:{mode.id}</span>
      {nextMode ? (
        <button type="button" onClick={() => setMode(nextMode)}>
          Change mode
        </button>
      ) : null}
    </Fragment>
  );
}

describe("ModeProvider storage resilience", () => {
  beforeEach(() => {
    refreshMock.mockClear();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("falls back to the default mode when storage reads throw", async () => {
    jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage unavailable");
    });

    jest.spyOn(document, "cookie", "get").mockImplementation(() => {
      throw new Error("cookies unavailable");
    });

    render(
      <ModeProvider>
        <ModeConsumer />
      </ModeProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText(`mode:${DEFAULT_MODE_ID}`)).toBeInTheDocument();
    });
  });

  it("does not refresh the router when storage writes throw", async () => {
    jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("storage unavailable");
    });

    jest.spyOn(document, "cookie", "set").mockImplementation(() => {
      throw new Error("cookies unavailable");
    });

    render(
      <ModeProvider>
        <ModeConsumer nextMode="investigative" />
      </ModeProvider>,
    );
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
      expect(screen.getByText("mode:investigative")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(refreshMock).not.toHaveBeenCalled();
    });
      expect(screen.getByTestId("mode-id")).toHaveTextContent("investigative");
    });

    expect(refresh).toHaveBeenCalled();
  });
});
