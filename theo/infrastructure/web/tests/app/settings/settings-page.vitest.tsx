import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "../../../app/settings/page";
import { ApiConfigProvider } from "../../../app/lib/api-config";

const listProvidersMock = vi.fn();
const upsertProviderSettingsMock = vi.fn();

vi.mock("../../../app/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../app/lib/api-client")>();
  return {
    ...actual,
    createTheoApiClient: vi.fn(() => ({
      listProviderSettings: listProvidersMock,
      upsertProviderSettings: upsertProviderSettingsMock,
    })),
  };
});

const fetchMock = vi.fn();

describe("SettingsPage", () => {
  beforeEach(() => {
    listProvidersMock.mockReset();
    upsertProviderSettingsMock.mockReset();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("allows editing provider credentials and testing API connection", async () => {
    listProvidersMock.mockResolvedValueOnce([
      {
        provider: "openai",
        base_url: "https://api.openai.com",
        default_model: "gpt-4o",
        extra_headers: null,
        has_api_key: false,
      },
    ]);

    upsertProviderSettingsMock.mockResolvedValue({
      provider: "openai",
      base_url: "https://api.openai.com/v1",
      default_model: "gpt-4o-mini",
      extra_headers: { "X-Test": "1" },
      has_api_key: true,
    });

    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(
      <ApiConfigProvider>
        <SettingsPage />
      </ApiConfigProvider>,
    );

    const providerCard = await screen.findByRole("article", { name: /openai/i });

    const apiKeyInput = screen.getByLabelText(/API key \(used when Authorization is empty\)/i);
    await userEvent.clear(apiKeyInput);
    await userEvent.type(apiKeyInput, "demo-key");

    const testButton = screen.getByRole("button", { name: /test connection/i });
    await userEvent.click(testButton);

    await screen.findByText(/connection successful/i);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/health$/);
    expect(options?.headers).toMatchObject({ "X-API-Key": "demo-key" });

    const baseUrlField = within(providerCard).getByLabelText(/base url/i);
    await userEvent.clear(baseUrlField);
    await userEvent.type(baseUrlField, "https://api.openai.com/v1");

    const modelField = within(providerCard).getByLabelText(/default model/i);
    await userEvent.clear(modelField);
    await userEvent.type(modelField, "gpt-4o-mini");

    const headersField = within(providerCard).getByLabelText(/extra headers/i);
    await userEvent.clear(headersField);
    fireEvent.input(headersField, { target: { value: '{"X-Test": "1"}' } });

    const providerApiKey = within(providerCard).getByLabelText(/API key \(new value\)/i);
    await userEvent.type(providerApiKey, "super-secret");

    const saveButton = within(providerCard).getByRole("button", { name: /save provider/i });
    await userEvent.click(saveButton);

    await within(providerCard).findByText(/provider settings saved/i);

    expect(upsertProviderSettingsMock).toHaveBeenCalledWith("openai", {
      base_url: "https://api.openai.com/v1",
      default_model: "gpt-4o-mini",
      extra_headers: { "X-Test": "1" },
      api_key: "super-secret",
    });
  });
});
