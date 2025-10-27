/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Fragment } from "react";
import { useRouter } from "next/navigation";

import { ModeProvider, useMode } from "../../app/mode-context";
import {
  DEFAULT_MODE_ID,
  MODE_COOKIE_KEY,
  MODE_STORAGE_KEY,
  type ResearchModeId,
} from "../../app/mode-config";

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

const useRouterMock = useRouter as unknown as jest.Mock;
const refreshMock = jest.fn();

type OptionalModeConsumerProps = {
  nextMode?: ResearchModeId;
};

function OptionalModeConsumer({ nextMode }: OptionalModeConsumerProps) {
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

describe("ModeProvider storage resilience", () => {
  beforeEach(() => {
    refreshMock.mockReset();
    useRouterMock.mockReturnValue({ refresh: refreshMock });
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
        <OptionalModeConsumer />
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
        <OptionalModeConsumer nextMode="critic" />
      </ModeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Change mode" }));

    expect(refreshMock).not.toHaveBeenCalled();
  });
});

describe("ModeProvider", () => {
  beforeEach(() => {
    useRouterMock.mockReturnValue({ refresh: jest.fn() });
    localStorage.clear();
    document.cookie = `${MODE_COOKIE_KEY}=; Max-Age=0`;
  });

  function renderWithProvider(initialMode?: ResearchModeId) {
    const providerProps: { initialMode?: ResearchModeId } = initialMode
      ? { initialMode }
      : {};

    return render(
      <ModeProvider {...providerProps}>
        <ModeConsumer nextMode="critic" />
      </ModeProvider>,
    );
  }

  it("falls back to the default mode when the provided mode id is invalid", async () => {
    renderWithProvider("toString" as ResearchModeId);

    await waitFor(() => {
      expect(screen.getByTestId("mode-id")).toHaveTextContent(DEFAULT_MODE_ID);
    });
  });

  it("uses the provided mode when it is valid", async () => {
    const validMode: ResearchModeId = "apologist";
    renderWithProvider(validMode);

    await waitFor(() => {
      expect(screen.getByTestId("mode-id")).toHaveTextContent(validMode);
    });
  });

  it("persists the selected mode to storage and cookies", async () => {
    renderWithProvider(DEFAULT_MODE_ID);

    fireEvent.click(screen.getByRole("button", { name: "Change mode" }));

    await waitFor(() => {
      expect(localStorage.getItem(MODE_STORAGE_KEY)).toBe("critic");
    });

    await waitFor(() => {
      expect(document.cookie).toContain(`${MODE_COOKIE_KEY}=critic`);
    });
  });

  it("updates the mode and refreshes the router when the user selects a new mode", async () => {
    const refresh = jest.fn();
    useRouterMock.mockReturnValue({ refresh });

    renderWithProvider(DEFAULT_MODE_ID);

    fireEvent.click(screen.getByRole("button", { name: "Change mode" }));

    await waitFor(() => {
      expect(screen.getByTestId("mode-id")).toHaveTextContent("critic");
    });

    expect(refresh).toHaveBeenCalled();
  });
});

