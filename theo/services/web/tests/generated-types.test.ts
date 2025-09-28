import { execFileSync } from "child_process";
import path from "path";

describe("Generated API types", () => {
  test("openapi-typescript output is in sync", () => {
    const projectRoot = path.resolve(__dirname, "..", "");
    const cliName = process.platform === "win32" ? "openapi-typescript.cmd" : "openapi-typescript";
    const cliPath = path.resolve(projectRoot, "node_modules", ".bin", cliName);
    const schemaPath = path.resolve(projectRoot, "..", "..", "..", "openapi.json");
    const outputPath = path.resolve(projectRoot, "app", "lib", "generated", "api.ts");

    expect(() =>
      execFileSync(cliPath, [schemaPath, "-o", outputPath, "--check"], {
        cwd: projectRoot,
        stdio: "pipe",
      })
    ).not.toThrow();
  });
});
