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

    fireEvent.click(screen.getByRole("button", { name: "Change mode" }));

    await waitFor(() => {
      expect(screen.getByText("mode:investigative")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(refreshMock).not.toHaveBeenCalled();
    });
  });
});
