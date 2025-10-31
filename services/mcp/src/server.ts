import 'dotenv/config';
import { createServer, Tool } from '@modelcontextprotocol/sdk/server';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/transport/stdio';
import { z } from 'zod';
import { ulid } from 'ulid';
import { promises as fs } from 'fs';
import path from 'path';
import { execFile } from 'child_process';
import { promisify } from 'util';
import simpleGit from 'simple-git';

const execFileAsync = promisify(execFile);

// ---------- ENV / PATHS ----------
const REPO = requirePath('THEORIA_REPO_PATH');
const CARDS = path.join(REPO, 'evidence/cards/cards.jsonl');
const BUILD_SCRIPT = path.join(REPO, 'evidence/scripts/build_markdown.py');
const CLI_SCRIPT = path.join(REPO, 'evidence/scripts/theoria_cli.py');

function requirePath(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing env: ${name}`);
  }
  return value;
}

// ---------- HELPERS ----------
async function appendJsonl(lineObj: unknown) {
  await fs.mkdir(path.dirname(CARDS), { recursive: true });
  await fs.appendFile(CARDS, JSON.stringify(lineObj) + '\n', 'utf8');
}

async function runValidateAndBuild() {
  try {
    await execFileAsync('python', [CLI_SCRIPT, 'validate'], { cwd: REPO });
  } catch (error) {
    throw error;
  }
  await execFileAsync('python', [BUILD_SCRIPT], { cwd: REPO });
}

async function readAllCards(): Promise<any[]> {
  try {
    const text = await fs.readFile(CARDS, 'utf8');
    return text
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line));
  } catch (error: any) {
    if (error.code === 'ENOENT') {
      return [];
    }
    throw error;
  }
}

// ---------- SCHEMAS ----------
const AddCardInput = z.object({
  title: z.string(),
  claim: z.string(),
  scope: z.string(),
  mode: z.enum(['Skeptical', 'Neutral', 'Apologetic']),
  stability: z.enum(['Low', 'Medium', 'High']),
  confidence: z.number().min(0).max(1),
  sources: z
    .object({
      primary: z.array(z.string()).default([]),
      secondary: z.array(z.string()).default([]),
    })
    .default({ primary: [], secondary: [] }),
  quotes: z.array(z.string()).default([]),
  arguments_for: z.array(z.string()).default([]),
  counterpoints: z.array(z.string()).default([]),
  open_questions: z.array(z.string()).default([]),
  tags: z.array(z.string()).default([]),
  provenance: z
    .object({
      kind: z.string().default('mcp'),
      details: z.string().default(''),
    })
    .default({ kind: 'mcp', details: '' }),
});

const SearchInput = z.object({
  query: z.string().min(1),
});

const SyncInput = z.object({
  branch: z
    .string()
    .default(() =>
      `evidence-sync/${new Date().toISOString().replace(/[:.]/g, '-')}`,
    ),
  commitMessage: z.string().default('chore(evidence): sync cards & mirrors'),
  push: z.boolean().default(true),
});

const addCardInputSchema = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    claim: { type: 'string' },
    scope: { type: 'string' },
    mode: { type: 'string', enum: ['Skeptical', 'Neutral', 'Apologetic'] },
    stability: { type: 'string', enum: ['Low', 'Medium', 'High'] },
    confidence: { type: 'number', minimum: 0, maximum: 1 },
    sources: {
      type: 'object',
      properties: {
        primary: { type: 'array', items: { type: 'string' } },
        secondary: { type: 'array', items: { type: 'string' } },
      },
    },
    quotes: { type: 'array', items: { type: 'string' } },
    arguments_for: { type: 'array', items: { type: 'string' } },
    counterpoints: { type: 'array', items: { type: 'string' } },
    open_questions: { type: 'array', items: { type: 'string' } },
    tags: { type: 'array', items: { type: 'string' } },
    provenance: {
      type: 'object',
      properties: {
        kind: { type: 'string' },
        details: { type: 'string' },
      },
    },
  },
  required: ['title', 'claim', 'scope', 'mode', 'stability', 'confidence'],
} as const;

// ---------- TOOLS ----------
const addCardTool: Tool = {
  name: 'evidence.add_card',
  description:
    'Append a new Evidence Card to evidence/cards/cards.jsonl and rebuild mirrors.',
  inputSchema: addCardInputSchema,
  handler: async ({ input }) => {
    const data = AddCardInput.parse(input);
    const now = new Date().toISOString();
    const card = {
      id: ulid(),
      ...data,
      created_at: now,
      updated_at: now,
    };
    await appendJsonl(card);
    await runValidateAndBuild();
    return { content: [{ type: 'text', text: JSON.stringify(card) }] };
  },
};

const searchCardsTool: Tool = {
  name: 'evidence.search_cards',
  description: 'Search cards by substring over title/claim/scope/tags.',
  inputSchema: {
    type: 'object',
    properties: {
      query: { type: 'string' },
    },
    required: ['query'],
  },
  handler: async ({ input }) => {
    const { query } = SearchInput.parse(input);
    const q = query.toLowerCase();
    const all = await readAllCards();
    const hits = all
      .filter((card: any) => {
        const haystack = [
          card.title ?? '',
          card.claim ?? '',
          card.scope ?? '',
          ...(Array.isArray(card.tags) ? card.tags : []),
        ]
          .join(' ')
          .toLowerCase();
        return q
          .split(/\s+/)
          .every((token) => token && haystack.includes(token));
      })
      .slice(0, 50);
    return { content: [{ type: 'text', text: JSON.stringify(hits) }] };
  },
};

const validateTool: Tool = {
  name: 'evidence.validate_cards',
  description:
    'Run CLI validator over cards.jsonl (uses existing Python script).',
  inputSchema: { type: 'object', properties: {}, required: [] },
  handler: async () => {
    const { stdout, stderr } = await execFileAsync(
      'python',
      [CLI_SCRIPT, 'validate'],
      { cwd: REPO },
    );
    return {
      content: [{ type: 'text', text: `${stdout ?? ''}${stderr ?? ''}` }],
    };
  },
};

const buildMdTool: Tool = {
  name: 'evidence.build_markdown',
  description: 'Regenerate Markdown mirrors from cards.jsonl.',
  inputSchema: { type: 'object', properties: {}, required: [] },
  handler: async () => {
    const { stdout, stderr } = await execFileAsync(
      'python',
      [BUILD_SCRIPT],
      { cwd: REPO },
    );
    return {
      content: [{ type: 'text', text: `${stdout ?? ''}${stderr ?? ''}` }],
    };
  },
};

const syncGitTool: Tool = {
  name: 'evidence.sync_git',
  description:
    'Commit changes in evidence/* and optionally push to remote on a new branch.',
  inputSchema: {
    type: 'object',
    properties: {
      branch: { type: 'string' },
      commitMessage: { type: 'string' },
      push: { type: 'boolean' },
    },
  },
  handler: async ({ input }) => {
    const { branch, commitMessage, push } = SyncInput.parse(input);
    const git = simpleGit(REPO);
    await git.addConfig('user.name', process.env.GIT_USER_NAME || 'theoria-mcp');
    await git.addConfig(
      'user.email',
      process.env.GIT_USER_EMAIL || 'theoria-mcp@local',
    );

    const status = await git.status();
    const baseBranch = process.env.GIT_BRANCH_BASE || 'main';
    if (status.current !== branch) {
      const branches = await git.branchLocal();
      if (branches.all.includes(branch)) {
        await git.checkout(branch);
      } else {
        if (status.current !== baseBranch) {
          const baseExists = branches.all.includes(baseBranch);
          if (baseExists) {
            await git.checkout(baseBranch);
          } else {
            await git.checkoutLocalBranch(baseBranch);
          }
        }
        await git.checkoutLocalBranch(branch);
      }
    }

    await git.add(['evidence/cards/cards.jsonl', 'evidence/cards_md']);
    const commitResult = await git
      .commit(commitMessage)
      .catch(() => ({ commit: '' } as { commit: string }));

    let pushed = false;
    if (push) {
      const remote = process.env.GIT_REMOTE || 'origin';
      await git.push(remote, branch);
      pushed = true;
    }

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({ branch, commit: commitResult.commit, pushed }),
        },
      ],
    };
  },
};

// ---------- SERVER BOOT ----------
const transport = new StdioServerTransport();
const server = createServer(
  { name: 'theoria-mcp', version: '0.1.0' },
  { capabilities: { tools: {} } },
  transport,
);

server.tool(addCardTool);
server.tool(searchCardsTool);
server.tool(validateTool);
server.tool(buildMdTool);
server.tool(syncGitTool);

await server.start();
