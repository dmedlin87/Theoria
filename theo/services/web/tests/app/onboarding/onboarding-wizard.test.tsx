/** @jest-environment jsdom */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { OnboardingOverlay } from "../../../app/components/onboarding/OnboardingOverlay";
import { emitTelemetry } from "../../../app/lib/telemetry";

describe("Onboarding wizard", () => {
  beforeAll(() => {
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
    });
  });

  beforeEach(() => {
    jest.clearAllMocks();
    window.localStorage.clear();
    (navigator.clipboard.writeText as jest.Mock).mockClear();
  });

  it("advances through steps, copies env commands, and persists completion", async () => {
    (emitTelemetry as jest.MockedFunction<typeof emitTelemetry>).mockResolvedValue(undefined);

    render(<OnboardingOverlay />);

    expect(
      await screen.findByRole("heading", { name: /welcome to theoria/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    expect(
      await screen.findByRole("heading", { name: /connect your api credentials/i }),
    ).toBeInTheDocument();

    const copyButton = screen.getByRole("button", { name: /copy/i });
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        expect.stringContaining("THEORIA_API_KEY"),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    expect(
      await screen.findByRole("heading", { name: /explore what you can do/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /next/i }));

    expect(
      await screen.findByRole("heading", { name: /you're all set/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /finish/i }));

    await waitFor(() => {
      expect(
        screen.queryByRole("heading", { name: /welcome to theoria/i }),
      ).not.toBeInTheDocument();
    });

    expect(window.localStorage.getItem("theoria.onboarding.completed")).toBe("1");
  });
});

jest.mock("../../../app/lib/telemetry", () => ({
  emitTelemetry: jest.fn(),
}));

jest.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...rest }: { children: ReactNode; href: string }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
