import { spawnSync } from "child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "fs";
import os from "os";
import path from "path";

const repoRoot = path.resolve(__dirname, "../../../../../..");
const generatedFile = path.join(repoRoot, "theo/services/web/app/lib/generated/api.ts");

function normalize(value: string): string {
  return value.replace(/\r\n/g, "\n").trim();
}

function generateOpenAPISchema(): string {
  const code = `from fastapi.openapi.utils import get_openapi\nfrom theo.services.api.app.main import create_app\nimport json\napp = create_app()\nprint(json.dumps(get_openapi(title=app.title, version=app.version, routes=app.routes)))`;
  const env = {
    ...process.env,
    PYTHONPATH: [repoRoot, process.env.PYTHONPATH ?? ""].filter(Boolean).join(path.delimiter),
    THEO_DISABLE_AI_SETTINGS: "1",
    SETTINGS_SECRET_KEY: process.env.SETTINGS_SECRET_KEY ?? "test-secret-key",
  };
  const result = spawnSync("python", ["-c", code], {
    cwd: repoRoot,
    env,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(result.stderr || "Unable to generate OpenAPI schema");
  }
  return result.stdout;
}

describe("generated API types", () => {
  it("match the FastAPI OpenAPI schema", async () => {
    const schemaJson = generateOpenAPISchema();
    const schema = JSON.parse(schemaJson);
    const tempDir = mkdtempSync(path.join(os.tmpdir(), "openapi-types-"));
    const schemaPath = path.join(tempDir, "schema.json");
    writeFileSync(schemaPath, JSON.stringify(schema));
    const cli = spawnSync("npx", ["openapi-typescript", schemaPath, "--output", "-"], {
      cwd: repoRoot,
      env: {
        ...process.env,
        FORCE_COLOR: "0",
      },
      encoding: "utf8",
    });
    if (cli.status !== 0) {
      throw new Error(cli.stderr || "openapi-typescript CLI failed");
    }
    const regenerated = cli.stdout;
    const existing = readFileSync(generatedFile, "utf8");
    expect(normalize(existing)).toBe(normalize(regenerated));
  });
});
