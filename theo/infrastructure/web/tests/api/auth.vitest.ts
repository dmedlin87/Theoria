import { describe, expect, it } from "vitest";

import { forwardAuthHeaders } from "../../app/api/auth";

describe("forwardAuthHeaders", () => {
  it("copies only non-empty values and trims whitespace", () => {
    const source = new Headers({
      authorization: "  Bearer secret  ",
      "x-api-key": "   ",
      cookie: "   session=value  ",
    });
    const target = new Headers();

    forwardAuthHeaders(source, target);

    expect(target.get("authorization")).toBe("Bearer secret");
    expect(target.get("cookie")).toBe("session=value");
    expect(target.has("x-api-key")).toBe(false);
  });
});
