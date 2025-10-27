import { cookies } from "next/headers";

import { DEFAULT_MODE_ID, RESEARCH_MODES } from "../../app/mode-config";
import { getActiveMode } from "../../app/mode-server";

jest.mock("next/headers", () => ({
  cookies: jest.fn(),
}));

describe("getActiveMode", () => {
  const cookiesMock = cookies as unknown as jest.Mock;

  beforeEach(() => {
    cookiesMock.mockReset();
  });

  it("returns the default mode when the cookie value is not a research mode id", () => {
    cookiesMock.mockReturnValue({
      get: () => ({ value: "toString" }),
    });

    expect(getActiveMode()).toBe(RESEARCH_MODES[DEFAULT_MODE_ID]);
  });

  it("returns the requested mode when the cookie contains a valid id", () => {
    cookiesMock.mockReturnValue({
      get: () => ({ value: "critic" }),
    });

    expect(getActiveMode()).toBe(RESEARCH_MODES.critic);
  });
});
